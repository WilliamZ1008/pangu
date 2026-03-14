"""
Deterministic CPU-side metrics for saved prediction rows.
"""
from statistics import mean, median
from typing import Any, Dict, List, Sequence


class MetricSuite:
    """Compute simple deterministic metrics and aggregates."""

    def score_prediction(self, sample, prediction, trace) -> Dict[str, Any]:
        task_match = None
        if sample.task_key == "Q&A" and isinstance(prediction, dict):
            direct_answer = str(prediction.get("direct_answer", "")).strip().lower()
            gold = str(sample.ground_truth).strip().lower()
            task_match = direct_answer == gold
        elif sample.task_key == "AG" and isinstance(prediction, dict):
            task_match = str(prediction.get("score")) == str(sample.ground_truth.get("score"))
        elif sample.task_key == "EC" and isinstance(prediction, dict):
            gold = sample.ground_truth.get("corrected_answer")
            task_match = str(prediction.get("corrected_answer")) == str(gold)

        return {
            "sample_id": sample.sample_id,
            "task_key": sample.task_key,
            "route": trace.get("route"),
            "format_validity": bool(trace.get("format_valid")),
            "task_match": task_match,
            "latency_seconds": float(trace.get("latency_seconds", 0.0)),
            "accepted_by_1b": trace.get("accepted_by_1b"),
            "7b_invocation": bool(trace.get("seven_b_invoked")),
        }

    def aggregate(self, rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(rows)
        latencies = [float(row.get("latency_seconds", 0.0)) for row in rows]
        format_valid = sum(1 for row in rows if row.get("format_validity"))
        accepted_by_1b_denominator = sum(1 for row in rows if row.get("accepted_by_1b") is not None)
        accepted_by_1b_numerator = sum(1 for row in rows if row.get("accepted_by_1b"))
        seven_b_invocations = sum(1 for row in rows if row.get("7b_invocation"))
        comparable_rows = [row for row in rows if row.get("task_match") is not None]
        judge_scores = [float(row.get("judge_score")) for row in rows if row.get("judge_score") is not None]
        task_match_rate = (
            sum(1 for row in comparable_rows if row.get("task_match")) / len(comparable_rows)
            if comparable_rows
            else None
        )
        return {
            "total_items": total,
            "format_validity": (format_valid / total) if total else 0.0,
            "task_match_rate": task_match_rate,
            "latency_avg": mean(latencies) if latencies else 0.0,
            "latency_p50": median(latencies) if latencies else 0.0,
            "latency_p90": self._percentile(latencies, 0.90),
            "accepted_by_1b_rate": (
                accepted_by_1b_numerator / accepted_by_1b_denominator if accepted_by_1b_denominator else None
            ),
            "7b_invocation_rate": (seven_b_invocations / total) if total else 0.0,
            "judge_score_avg": mean(judge_scores) if judge_scores else None,
        }

    def _percentile(self, values: Sequence[float], ratio: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = int((len(ordered) - 1) * ratio)
        return ordered[index]
