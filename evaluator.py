"""
Optional post-hoc judge and CPU-side summary recomputation from saved predictions.
"""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, Iterable, List, Optional, Sequence

import requests

from config import GPT5_API_BASE, GPT5_API_KEY, GPT5_MODEL_NAME, OUTPUT_EVAL_CACHE_DIR
from core.prompts import GPT5_JUDGE_PROMPT_ZH


class GPT5Judge:
    """Thin wrapper around the optional GPT judge endpoint."""

    def __init__(self, api_key: str = GPT5_API_KEY, api_base: str = GPT5_API_BASE):
        self.api_key = api_key
        self.api_base = api_base
        self.model = GPT5_MODEL_NAME
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def judge_answer(self, task_type: str, question: str, prediction: str, ground_truth: Any) -> Dict[str, Any]:
        prompt = GPT5_JUDGE_PROMPT_ZH.format(
            task_type=task_type,
            question=question,
            prediction=prediction,
            ground_truth=ground_truth,
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是一个严谨的教育专家评估系统。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        try:
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as error:
            return {
                "Error": str(error),
                "Average": 0,
                "Reason": "judge request failed",
            }


def evaluate_prediction_rows(
    prediction_rows: Sequence[Dict[str, Any]],
    judge: Optional[GPT5Judge] = None,
    cache_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    judge = judge or GPT5Judge()
    cache_root = cache_dir or Path(OUTPUT_EVAL_CACHE_DIR)
    cache_root.mkdir(parents=True, exist_ok=True)

    evaluated_rows: List[Dict[str, Any]] = []
    for row in prediction_rows:
        cache_path = cache_root / f"{_judge_cache_key(row)}.json"
        if cache_path.exists():
            scores = json.loads(cache_path.read_text(encoding="utf-8"))
        else:
            scores = judge.judge_answer(
                task_type=row["task_type"],
                question=row.get("prompt", ""),
                prediction=row["prediction"],
                ground_truth=row["ground_truth"],
            )
            cache_path.write_text(json.dumps(scores, ensure_ascii=False, indent=2), encoding="utf-8")

        enriched = dict(row)
        enriched["scores"] = scores
        evaluated_rows.append(enriched)
    return evaluated_rows


def compute_basic_summary(
    prediction_rows: Sequence[Dict[str, Any]],
    trace_rows: Optional[Sequence[Dict[str, Any]]] = None,
    system_name: str = "",
    lang: str = "",
    split: str = "",
    warnings: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    rows = list(prediction_rows)
    trace_rows = list(trace_rows or [])
    warning_list = list(warnings or [])

    total_items = len(rows)
    latencies = [row.get("latency_seconds", 0.0) for row in rows]
    format_valid_count = sum(1 for row in rows if row.get("format_valid"))

    route_counts: Dict[str, int] = {}
    task_counts: Dict[str, int] = {}
    per_task_format_valid: Dict[str, Dict[str, int]] = {}

    accepted_by_1b_numerator = 0
    accepted_by_1b_denominator = 0
    seven_b_invocations = 0

    for row in rows:
        route = row.get("route", "unknown")
        task_key = row.get("task_key", "unknown")

        route_counts[route] = route_counts.get(route, 0) + 1
        task_counts[task_key] = task_counts.get(task_key, 0) + 1
        task_entry = per_task_format_valid.setdefault(task_key, {"valid": 0, "total": 0})
        task_entry["total"] += 1
        if row.get("format_valid"):
            task_entry["valid"] += 1

        if row.get("accepted_by_1b") is not None:
            accepted_by_1b_denominator += 1
            if row.get("accepted_by_1b"):
                accepted_by_1b_numerator += 1

        if row.get("seven_b_invoked"):
            seven_b_invocations += 1

    judge_scores = [row.get("scores", {}).get("Average", 0) for row in rows if row.get("scores")]
    judge_average = mean(judge_scores) if judge_scores else None

    return {
        "system": system_name,
        "lang": lang,
        "split": split,
        "generated_at": _iso_timestamp(),
        "total_items": total_items,
        "warnings": warning_list,
        "judge_status": "run" if judge_scores else "not_run",
        "format_valid_rate": _safe_rate(format_valid_count, total_items),
        "average_latency_seconds": mean(latencies) if latencies else 0.0,
        "latency_p50_seconds": median(latencies) if latencies else 0.0,
        "latency_p90_seconds": _percentile(latencies, 0.90),
        "route_counts": route_counts,
        "task_counts": task_counts,
        "per_task_format_validity": {
            task_key: {
                "valid": values["valid"],
                "total": values["total"],
                "rate": _safe_rate(values["valid"], values["total"]),
            }
            for task_key, values in per_task_format_valid.items()
        },
        "accepted_by_1b_rate": _safe_rate(accepted_by_1b_numerator, accepted_by_1b_denominator)
        if accepted_by_1b_denominator
        else None,
        "seven_b_invocation_rate": _safe_rate(seven_b_invocations, total_items),
        "judge_average_score": judge_average,
        "trace_rows": len(trace_rows),
    }


def recompute_from_prediction_file(
    prediction_file: Path,
    do_judge: bool = False,
    summary_out: Optional[Path] = None,
    cache_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    rows = _read_jsonl(prediction_file)
    if do_judge:
        rows = evaluate_prediction_rows(rows, cache_dir=cache_dir or Path(OUTPUT_EVAL_CACHE_DIR))

    if rows:
        system_name = rows[0].get("system", "")
        lang = rows[0].get("lang", "")
        split = rows[0].get("split", "")
    else:
        system_name = ""
        lang = ""
        split = ""

    warnings = []
    if not do_judge:
        warnings.append(
            "Summary recomputed without judge scores. This is suitable for offline analysis, not final paper tables."
        )

    summary = compute_basic_summary(
        rows,
        system_name=system_name,
        lang=lang,
        split=split,
        warnings=warnings,
    )

    if summary_out is not None:
        summary_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return summary


def _judge_cache_key(row: Dict[str, Any]) -> str:
    payload = {
        "sample_id": row.get("sample_id"),
        "system": row.get("system"),
        "task_type": row.get("task_type"),
        "prediction": row.get("prediction"),
        "ground_truth": row.get("ground_truth"),
    }
    return hashlib.sha1(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _percentile(values: Sequence[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int((len(ordered) - 1) * ratio)
    return ordered[index]


def _iso_timestamp() -> str:
    from datetime import datetime

    return datetime.now().isoformat()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recompute evaluation summaries from saved predictions.")
    parser.add_argument("--predictions", required=True, help="Path to the prediction JSONL file.")
    parser.add_argument("--summary-out", help="Optional path for the recomputed summary JSON.")
    parser.add_argument("--do-judge", action="store_true", help="Run the optional GPT judge on saved predictions.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    prediction_path = Path(args.predictions)
    summary_out = Path(args.summary_out) if args.summary_out else None
    summary = recompute_from_prediction_file(
        prediction_file=prediction_path,
        do_judge=args.do_judge,
        summary_out=summary_out,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
