"""
Shared batch runner for serial and parallel offline experiments.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from math import ceil
from typing import Dict, Iterable, List, Optional, Sequence

from core.request_normalizer import RequestNormalizer
from data_loader import DataLoader
from evaluation.judge import JudgeRunner
from evaluation.metrics import MetricSuite
from evaluation.summarize import SummaryBuilder
from inference_engine import InferenceEngine, SUPPORTED_SYSTEMS
from services.result_store import ResultStore

try:
    from tqdm import tqdm
except Exception:  # pragma: no cover
    tqdm = None


class ExperimentRunner:
    """Run one or more offline experiment configurations with shared semantics."""

    def __init__(
        self,
        data_loader: Optional[DataLoader] = None,
        engine: Optional[InferenceEngine] = None,
        result_store: Optional[ResultStore] = None,
    ):
        self.data_loader = data_loader or DataLoader()
        self.engine = engine or InferenceEngine()
        self.result_store = result_store or ResultStore()
        self.normalizer = RequestNormalizer()
        self.metric_suite = MetricSuite()
        self.summary_builder = SummaryBuilder(self.metric_suite)

    def run(
        self,
        system_name: str,
        lang: str,
        split: str,
        do_judge: bool = False,
        sample_limit: Optional[int] = None,
        sample_fraction: Optional[float] = None,
        max_workers: int = 1,
        output_tag: str = "",
    ) -> Dict[str, object]:
        if system_name not in SUPPORTED_SYSTEMS:
            raise ValueError(f"Unsupported system: {system_name}")

        samples = self._load_samples(lang, split)
        if sample_fraction is not None:
            samples = self._subset_samples(samples, sample_fraction)
        if sample_limit is not None:
            samples = samples[:sample_limit]

        prediction_rows, trace_rows = self._run_samples(samples, system_name, split, max_workers=max_workers)

        warnings: List[str] = []
        if sample_fraction is not None:
            warnings.append(
                f"Deterministic stratified subset used for speed: sample_fraction={sample_fraction:.4f} per task."
            )
        if do_judge:
            prediction_rows = JudgeRunner().evaluate_rows(prediction_rows)
        else:
            warnings.append(
                "Judge not run. This summary is diagnostic only and must not be presented as a paper-ready result."
            )

        summary = self.summary_builder.build(
            prediction_rows,
            system_name=system_name,
            lang=lang,
            split=split,
            warnings=warnings,
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_name = self._build_run_name(system_name, lang, split, timestamp, output_tag)
        prediction_file = self.result_store.save_predictions(run_name, prediction_rows)
        trace_file = self.result_store.save_traces(run_name, trace_rows)
        summary_file = self.result_store.save_summary(run_name, summary)
        per_task_summary_file = self.result_store.save_per_task_summary(run_name, summary["per_task_summary"])
        per_route_summary_file = self.result_store.save_per_route_summary(run_name, summary["per_route_summary"])

        return {
            "prediction_file": prediction_file,
            "trace_file": trace_file,
            "summary_file": summary_file,
            "per_task_summary_file": per_task_summary_file,
            "per_route_summary_file": per_route_summary_file,
            "summary": summary,
        }

    def run_all(
        self,
        system_names: Sequence[str],
        split_plan: Sequence[Dict[str, str]],
        do_judge: bool = False,
        sample_limit: Optional[int] = None,
        sample_fraction: Optional[float] = None,
        max_workers: int = 1,
        output_tag: str = "",
    ) -> List[Dict[str, object]]:
        outputs = []
        for plan in split_plan:
            for system_name in system_names:
                outputs.append(
                    self.run(
                        system_name=system_name,
                        lang=plan["lang"],
                        split=plan["split"],
                        do_judge=do_judge,
                        sample_limit=sample_limit,
                        sample_fraction=sample_fraction,
                        max_workers=max_workers,
                        output_tag=output_tag,
                    )
                )
        return outputs

    def _load_samples(self, lang: str, split: str):
        if lang == "all":
            samples = []
            for lang_name in ("zh", "en"):
                samples.extend(self.data_loader.load_primary_split(lang_name, split))
            return samples
        return self.data_loader.load_primary_split(lang, split)

    def _subset_samples(self, samples, sample_fraction: float):
        if sample_fraction <= 0 or sample_fraction > 1:
            raise ValueError(f"sample_fraction must be in (0, 1], got {sample_fraction}")
        if sample_fraction >= 1:
            return list(samples)

        per_task = {}
        task_order: List[str] = []
        for sample in samples:
            if sample.task_key not in per_task:
                per_task[sample.task_key] = []
                task_order.append(sample.task_key)
            per_task[sample.task_key].append(sample)

        subset = []
        for task_key in task_order:
            task_samples = per_task[task_key]
            keep = max(1, ceil(len(task_samples) * sample_fraction))
            subset.extend(task_samples[:keep])
        return subset

    def _run_samples(self, samples, system_name: str, split: str, max_workers: int = 1):
        sample_order = {sample.sample_id: index for index, sample in enumerate(samples)}
        prediction_rows = []
        trace_rows = []

        if max_workers <= 1:
            iterator: Iterable = samples
            if tqdm is not None:
                iterator = tqdm(samples, desc=system_name, leave=False)
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
                    future_iterator = tqdm(future_iterator, total=len(samples), desc=f"{system_name}:parallel", leave=False)
                for future in future_iterator:
                    prediction_row, trace_row = future.result()
                    prediction_rows.append(prediction_row)
                    trace_rows.append(trace_row)

        prediction_rows.sort(key=lambda row: sample_order[row["sample_id"]])
        trace_rows.sort(key=lambda row: sample_order[row["sample_id"]])
        return prediction_rows, trace_rows

    def _process_sample(self, sample, system_name: str, split: str):
        normalized = self.normalizer.normalize_data_item(sample)
        try:
            result, trace, normalized = self.engine.run_system(system_name, normalized)
            prediction_row = result.to_dict()
            trace_row = trace.to_dict()
        except Exception as error:
            prediction_row = {
                "sample_id": normalized.sample_id,
                "system_name": system_name,
                "task_key": normalized.task_key,
                "task_type": normalized.task_type,
                "task_family": normalized.task_family,
                "subject": normalized.subject,
                "lang": normalized.lang,
                "route": "error",
                "accepted_by_1b": None,
                "specialist_name": "",
                "risk_score": None,
                "prediction": f"[RUNNER_ERROR: {error}]",
                "ground_truth": normalized.ground_truth,
                "format_valid": False,
                "latency_seconds": 0.0,
                "tokens_1b": 0,
                "tokens_7b": 0,
                "raw_model_outputs": {"error": str(error)},
                "judge_score": None,
                "route_reason": str(error),
                "expected_output_format": normalized.expected_output_format,
                "metadata": normalized.metadata,
            }
            trace_row = {
                "sample_id": normalized.sample_id,
                "system_name": system_name,
                "accepted_by_1b": None,
                "risk_score": 0.0,
                "risk_threshold": 0.0,
                "specialist_name": "",
                "format_valid": False,
                "latency_1b": 0.0,
                "latency_7b": 0.0,
                "tokens_1b": 0,
                "tokens_7b": 0,
                "notes": [str(error)],
                "router_output": {},
                "risk_features": {},
                "raw_outputs": {},
            }

        prediction_row.update(
            {
                "split": split,
                "prompt": normalized.prompt_text,
                "question": normalized.question,
                "source_file": normalized.metadata.get("source_file", ""),
                "source_row": normalized.metadata.get("source_row", 0),
            }
        )

        trace_row.update(
            {
                "split": split,
                "task_key": normalized.task_key,
                "task_type": normalized.task_type,
                "task_family": normalized.task_family,
                "subject": normalized.subject,
                "lang": normalized.lang,
                "route": prediction_row["route"],
                "route_reason": prediction_row.get("route_reason", ""),
                "latency_seconds": prediction_row["latency_seconds"],
                "seven_b_invoked": prediction_row["tokens_7b"] > 0,
            }
        )

        router_stage = trace_row.get("raw_outputs", {}).get("1b", {})
        seven_b_stages = trace_row.get("raw_outputs", {}).get("7b", [])
        final_stage = seven_b_stages[-1] if seven_b_stages else router_stage
        trace_row.update(
            {
                "router_output_raw": router_stage.get("text", "") if isinstance(router_stage, dict) else "",
                "router_output_parsed": trace_row.get("router_output", {}),
                "escalated": prediction_row["tokens_7b"] > 0,
                "final_output_raw": final_stage.get("text", "") if isinstance(final_stage, dict) else "",
                "validation_report": {
                    "format_valid": prediction_row["format_valid"],
                    "errors": final_stage.get("errors", []) if isinstance(final_stage, dict) else [],
                    "notes": trace_row.get("notes", []),
                },
                "final_output_normalized": prediction_row["prediction"],
            }
        )

        metric_row = self.metric_suite.score_prediction(normalized, prediction_row["prediction"], trace_row)
        prediction_row.update(metric_row)
        prediction_row["seven_b_invoked"] = prediction_row["tokens_7b"] > 0
        prediction_row.setdefault("judge_score", None)
        return prediction_row, trace_row

    def _build_run_name(self, system_name: str, lang: str, split: str, timestamp: str, output_tag: str) -> str:
        if output_tag:
            return f"{system_name}__{lang}__{split}__{output_tag}__{timestamp}"
        return f"{system_name}__{lang}__{split}__{timestamp}"
