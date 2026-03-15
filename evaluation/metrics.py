"""
Deterministic CPU-side metrics for saved prediction rows.
"""
from statistics import mean, median
from typing import Any, Dict, List, Sequence


class MetricSuite:
    """Compute simple deterministic metrics and aggregates."""

    def score_prediction(self, sample, prediction, trace) -> Dict[str, Any]:
        format_validity = bool(trace.get("format_valid"))
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

        deterministic_quality = self._deterministic_quality(sample.task_key, task_match, format_validity)
        return {
            "sample_id": sample.sample_id,
            "task_key": sample.task_key,
            "route": trace.get("route"),
            "format_validity": format_validity,
            "task_match": task_match,
            "deterministic_quality": deterministic_quality,
            "latency_seconds": float(trace.get("latency_seconds", 0.0)),
            "accepted_by_1b": trace.get("accepted_by_1b"),
            "7b_invocation": bool(trace.get("seven_b_invoked")),
        }

    def aggregate(self, rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(rows)
        latencies = [float(row.get("latency_seconds", 0.0)) for row in rows]
        tokens_1b = [int(row.get("tokens_1b", 0)) for row in rows]
        tokens_7b = [int(row.get("tokens_7b", 0)) for row in rows]
        format_valid = sum(1 for row in rows if row.get("format_validity"))
        accepted_by_1b_denominator = sum(1 for row in rows if row.get("accepted_by_1b") is not None)
        accepted_by_1b_numerator = sum(1 for row in rows if row.get("accepted_by_1b"))
        seven_b_invocations = sum(1 for row in rows if row.get("7b_invocation"))
        comparable_rows = [row for row in rows if row.get("task_match") is not None]
        judge_scores = [float(row.get("judge_score")) for row in rows if row.get("judge_score") is not None]
        quality_values = [self._row_quality_value(row) for row in rows if self._row_quality_value(row) is not None]
        accepted_rows = [row for row in rows if row.get("accepted_by_1b") is True]
        escalated_rows = [row for row in rows if row.get("accepted_by_1b") is False or row.get("7b_invocation")]
        task_match_rate = (
            sum(1 for row in comparable_rows if row.get("task_match")) / len(comparable_rows)
            if comparable_rows
            else None
        )
        return {
            "total_items": total,
            "quality_score": mean(quality_values) if quality_values else None,
            "format_validity": (format_valid / total) if total else 0.0,
            "task_match_rate": task_match_rate,
            "latency_avg": mean(latencies) if latencies else 0.0,
            "latency_p50": median(latencies) if latencies else 0.0,
            "latency_p90": self._percentile(latencies, 0.90),
            "accepted_by_1b_rate": (
                accepted_by_1b_numerator / accepted_by_1b_denominator if accepted_by_1b_denominator else None
            ),
            "accepted_by_1b_quality": self._mean_quality(accepted_rows),
            "escalated_quality": self._mean_quality(escalated_rows),
            "7b_invocation_rate": (seven_b_invocations / total) if total else 0.0,
            "tokens_1b_avg": mean(tokens_1b) if tokens_1b else 0.0,
            "tokens_7b_avg": mean(tokens_7b) if tokens_7b else 0.0,
            "estimated_cost_proxy": self._estimated_cost_proxy(rows),
            "judge_score_avg": mean(judge_scores) if judge_scores else None,
        }

    def _percentile(self, values: Sequence[float], ratio: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = int((len(ordered) - 1) * ratio)
        return ordered[index]

    def _deterministic_quality(self, task_key: str, task_match: Any, format_validity: bool) -> float | None:
        if task_match is not None:
            return 1.0 if task_match else 0.0
        if task_key in {"IP", "PCC", "PLS", "QG", "TMG"}:
            return 1.0 if format_validity else 0.0
        return None

    def _row_quality_value(self, row: Dict[str, Any]) -> float | None:
        if row.get("judge_score") is not None:
            return float(row["judge_score"])
        if row.get("deterministic_quality") is not None:
            return float(row["deterministic_quality"])
        return None

    def _mean_quality(self, rows: Sequence[Dict[str, Any]]) -> float | None:
        values = [self._row_quality_value(row) for row in rows if self._row_quality_value(row) is not None]
        return mean(values) if values else None

    def _estimated_cost_proxy(self, rows: Sequence[Dict[str, Any]]) -> float:
        if not rows:
            return 0.0
        weighted_tokens = []
        for row in rows:
            weighted_tokens.append(int(row.get("tokens_1b", 0)) + 7 * int(row.get("tokens_7b", 0)))
        return mean(weighted_tokens)
