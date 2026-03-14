"""
Shared offline experiment runner used by both main entrypoints.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from config import (
    OUTPUT_EVAL_CACHE_DIR,
    OUTPUT_PREDICTION_DIR,
    OUTPUT_SUMMARY_DIR,
    OUTPUT_TRACE_DIR,
)
from data_loader import DataLoader, DataItem
from evaluator import compute_basic_summary, evaluate_prediction_rows
from inference_engine import InferenceEngine, SUPPORTED_SYSTEMS

try:
    from tqdm import tqdm
except Exception:  # pragma: no cover - tqdm is optional
    tqdm = None


class ExperimentRunner:
    """Single implementation path for serial and parallel offline runs."""

    def __init__(self, data_loader: Optional[DataLoader] = None, engine: Optional[InferenceEngine] = None):
        self.data_loader = data_loader or DataLoader()
        self.engine = engine or InferenceEngine()

    def run(
        self,
        system_name: str,
        lang: str,
        split: str,
        do_judge: bool = False,
        sample_limit: Optional[int] = None,
        max_workers: int = 1,
        output_tag: str = "",
    ) -> Dict[str, Any]:
        if system_name not in SUPPORTED_SYSTEMS:
            raise ValueError(f"Unsupported system: {system_name}")

        samples = self._load_samples(lang, split)
        if sample_limit is not None:
            samples = samples[:sample_limit]

        prediction_rows, trace_rows = self._run_samples(samples, system_name, split, max_workers=max_workers)

        warnings = []
        if do_judge:
            prediction_rows = evaluate_prediction_rows(
                prediction_rows,
                cache_dir=Path(OUTPUT_EVAL_CACHE_DIR),
            )
        else:
            warnings.append(
                "Judge not run. This summary is diagnostic only and must not be presented as a paper-ready result."
            )

        summary = compute_basic_summary(
            prediction_rows,
            trace_rows=trace_rows,
            system_name=system_name,
            lang=lang,
            split=split,
            warnings=warnings,
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = self._build_base_name(system_name, lang, split, timestamp, output_tag)
        prediction_path = Path(OUTPUT_PREDICTION_DIR) / f"{base_name}.jsonl"
        trace_path = Path(OUTPUT_TRACE_DIR) / f"{base_name}.jsonl"
        summary_path = Path(OUTPUT_SUMMARY_DIR) / f"{base_name}.json"

        self._write_jsonl(prediction_path, prediction_rows)
        self._write_jsonl(trace_path, trace_rows)
        self._write_json(summary_path, summary)

        return {
            "prediction_file": str(prediction_path),
            "trace_file": str(trace_path),
            "summary_file": str(summary_path),
            "summary": summary,
        }

    def run_all(
        self,
        system_names: Sequence[str],
        split_plan: Sequence[Dict[str, str]],
        do_judge: bool = False,
        sample_limit: Optional[int] = None,
        max_workers: int = 1,
        output_tag: str = "",
    ) -> List[Dict[str, Any]]:
        runs = []
        for plan in split_plan:
            for system_name in system_names:
                runs.append(
                    self.run(
                        system_name=system_name,
                        lang=plan["lang"],
                        split=plan["split"],
                        do_judge=do_judge,
                        sample_limit=sample_limit,
                        max_workers=max_workers,
                        output_tag=output_tag,
                    )
                )
        return runs

    def _load_samples(self, lang: str, split: str) -> List[DataItem]:
        if lang == "all":
            samples: List[DataItem] = []
            for lang_name in ("zh", "en"):
                samples.extend(self.data_loader.load_primary_split(lang_name, split))
            return samples
        return self.data_loader.load_primary_split(lang, split)

    def _run_samples(
        self,
        samples: List[DataItem],
        system_name: str,
        split: str,
        max_workers: int = 1,
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        sample_order = {sample.sample_id: index for index, sample in enumerate(samples)}
        prediction_rows: List[Dict[str, Any]] = []
        trace_rows: List[Dict[str, Any]] = []

        if max_workers <= 1:
            iterator: Iterable[DataItem] = samples
            if tqdm is not None:
                iterator = tqdm(samples, desc=f"{system_name}:{split}", leave=False)
            for sample in iterator:
                prediction_row, trace_row = self._process_sample(sample, system_name, split)
                prediction_rows.append(prediction_row)
                trace_rows.append(trace_row)
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {
                    executor.submit(self._process_sample, sample, system_name, split): sample.sample_id
                    for sample in samples
                }
                future_iterator = as_completed(future_map)
                if tqdm is not None:
                    future_iterator = tqdm(
                        future_iterator,
                        total=len(samples),
                        desc=f"{system_name}:{split}:parallel",
                        leave=False,
                    )
                for future in future_iterator:
                    prediction_row, trace_row = future.result()
                    prediction_rows.append(prediction_row)
                    trace_rows.append(trace_row)

        prediction_rows.sort(key=lambda row: sample_order[row["sample_id"]])
        trace_rows.sort(key=lambda row: sample_order[row["sample_id"]])
        return prediction_rows, trace_rows

    def _process_sample(
        self,
        sample: DataItem,
        system_name: str,
        split: str,
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        try:
            result = self.engine.run_system(system_name, sample)
        except Exception as error:
            result = {
                "route": "error",
                "route_reason": f"runner exception: {error}",
                "prediction": f"[RUNNER_ERROR: {error}]",
                "latency_seconds": 0.0,
                "format_valid": False,
                "raw_model_outputs": {},
                "prompt_templates": [],
                "accepted_by_1b": None,
                "seven_b_refine_invoked": False,
                "self_eval": None,
            }

        seven_b_invoked = any(
            stage.get("tier") == "7b"
            for stage in result.get("raw_model_outputs", {}).values()
            if isinstance(stage, dict)
        )

        prediction_row = {
            "system": system_name,
            "split": split,
            "sample_id": sample.sample_id,
            "task_key": sample.task_key,
            "task_type": sample.task_type,
            "task_family": sample.task_family,
            "expected_output_format": sample.expected_output_format,
            "lang": sample.lang,
            "route": result["route"],
            "route_reason": result["route_reason"],
            "prediction": result["prediction"],
            "ground_truth": sample.ground_truth,
            "latency_seconds": result["latency_seconds"],
            "format_valid": result["format_valid"],
            "raw_model_outputs": result.get("raw_model_outputs", {}),
            "prompt": sample.prompt,
            "canonical_fields": sample.canonical_fields,
            "source_file": sample.source_file,
            "source_row": sample.source_row,
            "accepted_by_1b": result.get("accepted_by_1b"),
            "seven_b_invoked": seven_b_invoked,
        }

        self_eval = result.get("self_eval") or {}
        trace_row = {
            "system": system_name,
            "split": split,
            "sample_id": sample.sample_id,
            "task_key": sample.task_key,
            "task_type": sample.task_type,
            "task_family": sample.task_family,
            "lang": sample.lang,
            "route": result["route"],
            "route_reason": result["route_reason"],
            "prompt_templates": result.get("prompt_templates", []),
            "latency_seconds": result["latency_seconds"],
            "format_valid": result["format_valid"],
            "accepted_by_1b": result.get("accepted_by_1b"),
            "seven_b_invoked": seven_b_invoked,
            "self_eval_label": self_eval.get("label"),
            "self_eval_parse_ok": self_eval.get("parse_ok"),
            "self_eval_raw_output": self_eval.get("raw_output"),
            "source_file": sample.source_file,
            "source_row": sample.source_row,
        }
        return prediction_row, trace_row

    def _build_base_name(
        self,
        system_name: str,
        lang: str,
        split: str,
        timestamp: str,
        output_tag: str = "",
    ) -> str:
        if output_tag:
            return f"{system_name}__{lang}__{split}__{output_tag}__{timestamp}"
        return f"{system_name}__{lang}__{split}__{timestamp}"

    def _write_jsonl(self, path: Path, rows: Sequence[Dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
