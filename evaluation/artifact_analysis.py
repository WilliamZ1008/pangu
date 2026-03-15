"""
Helpers for post-hoc analysis on saved prediction and trace artifacts.
"""
import json
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Sequence


FORMAT_ONLY_TASK_KEYS = {"IP", "PCC", "PLS", "QG", "TMG"}


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_joined_rows(prediction_path: Path, trace_path: Path | None = None) -> List[Dict[str, Any]]:
    predictions = [normalize_prediction_row(row) for row in read_jsonl(prediction_path)]
    traces_by_id = {}
    if trace_path is not None and trace_path.exists():
        traces_by_id = {row["sample_id"]: row for row in read_jsonl(trace_path)}
    for row in predictions:
        row["_trace"] = traces_by_id.get(row["sample_id"], {})
    return predictions


def normalize_prediction_row(row: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(row)
    format_valid = bool(enriched.get("format_validity", enriched.get("format_valid")))
    enriched["format_validity"] = format_valid

    if "task_match" not in enriched or enriched.get("task_match") is None:
        enriched["task_match"] = _task_match(enriched)
    if "deterministic_quality" not in enriched or enriched.get("deterministic_quality") is None:
        enriched["deterministic_quality"] = _deterministic_quality(
            enriched.get("task_key", ""),
            enriched.get("task_match"),
            format_valid,
        )

    seven_b_invoked = enriched.get("seven_b_invoked")
    if seven_b_invoked is None:
        seven_b_invoked = enriched.get("7b_invocation")
    if seven_b_invoked is None:
        seven_b_invoked = enriched.get("accepted_by_1b") is False or int(enriched.get("tokens_7b", 0) or 0) > 0
    enriched["seven_b_invoked"] = bool(seven_b_invoked)
    return enriched


def quality_value(row: Dict[str, Any]) -> float | None:
    if row.get("judge_score") is not None:
        return float(row["judge_score"])
    if row.get("deterministic_quality") is not None:
        return float(row["deterministic_quality"])
    return None


def mean_or_none(values: Iterable[float | None]) -> float | None:
    materialized = [float(value) for value in values if value is not None]
    return mean(materialized) if materialized else None


def seven_b_invoked(row: Dict[str, Any]) -> bool:
    return bool(row.get("seven_b_invoked"))


def extract_1b_draft(row: Dict[str, Any]) -> Any:
    trace = row.get("_trace", {}) or {}
    router_output = trace.get("router_output", {}) or {}
    draft_answer = router_output.get("draft_answer")
    if draft_answer not in (None, "", {}, []):
        return draft_answer

    raw_outputs = trace.get("raw_outputs", {}) or {}
    router_stage = raw_outputs.get("1b", {}) or {}
    router_output = router_stage.get("router_output", {}) or {}
    draft_answer = router_output.get("draft_answer")
    if draft_answer not in (None, "", {}, []):
        return draft_answer

    fallback_text = router_stage.get("text")
    if fallback_text not in (None, ""):
        return fallback_text

    model_outputs = row.get("raw_model_outputs", {}) or {}
    one_b = model_outputs.get("1b", {}) or {}
    router_output = one_b.get("router_output", {}) or {}
    draft_answer = router_output.get("draft_answer")
    if draft_answer not in (None, "", {}, []):
        return draft_answer
    return one_b.get("text", "")


def route_decision(row: Dict[str, Any]) -> str:
    route = str(row.get("route", "") or "")
    if route:
        return route
    if row.get("accepted_by_1b") is True:
        return "1b_accept"
    if row.get("accepted_by_1b") is False:
        return "1b_to_7b"
    return "unknown"


def diverse_select(rows: Sequence[Dict[str, Any]], count: int, *, key: str = "task_key", seed: int = 42) -> List[Dict[str, Any]]:
    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(key, ""))].append(row)

    randomizer = random.Random(seed)
    keys = sorted(buckets)
    randomizer.shuffle(keys)

    selected: List[Dict[str, Any]] = []
    while keys and len(selected) < count:
        next_keys: List[str] = []
        for bucket_key in keys:
            bucket = buckets[bucket_key]
            if bucket:
                selected.append(bucket.pop(0))
                if len(selected) >= count:
                    break
            if bucket:
                next_keys.append(bucket_key)
        keys = next_keys
    return selected


def _task_match(row: Dict[str, Any]) -> bool | None:
    task_key = str(row.get("task_key", ""))
    prediction = row.get("prediction")
    ground_truth = row.get("ground_truth")

    if task_key == "Q&A" and isinstance(prediction, dict):
        direct_answer = str(prediction.get("direct_answer", "")).strip().lower()
        gold = str(ground_truth).strip().lower()
        return direct_answer == gold

    if task_key == "AG" and isinstance(prediction, dict) and isinstance(ground_truth, dict):
        return str(prediction.get("score")) == str(ground_truth.get("score"))

    if task_key == "EC" and isinstance(prediction, dict) and isinstance(ground_truth, dict):
        return str(prediction.get("corrected_answer")) == str(ground_truth.get("corrected_answer"))

    return None


def _deterministic_quality(task_key: str, task_match: bool | None, format_validity: bool) -> float | None:
    if task_match is not None:
        return 1.0 if task_match else 0.0
    if task_key in FORMAT_ONLY_TASK_KEYS:
        return 1.0 if format_validity else 0.0
    return None
