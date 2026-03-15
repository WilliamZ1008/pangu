"""
Build a suite-level calibration summary from E1 per-run summaries.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from config import OUTPUT_SUMMARY_DIR
from core.risk_calibrator import RiskCalibrator


class CalibrationSummaryBuilder:
    """Aggregate the full E1 checkin suite into one calibration report."""

    EXPECTED_SYSTEMS = ("1b_only", "7b_only", "cascade_final")
    EXPECTED_LANGS = ("zh", "en")
    MIN_ACCEPT_RATE_TO_FREEZE = 0.05
    MAX_QUALITY_DROP_TO_FREEZE = 0.02

    def __init__(self, summary_dir: Path | None = None):
        self.summary_dir = Path(summary_dir or OUTPUT_SUMMARY_DIR)

    def build(self, run_tag: str) -> Dict:
        suite_records = self._load_suite_records(run_tag)
        suite_index = {
            (record["lang"], record["system_name"]): record
            for record in suite_records
        }
        missing = [
            {"lang": lang, "system_name": system_name}
            for lang in self.EXPECTED_LANGS
            for system_name in self.EXPECTED_SYSTEMS
            if (lang, system_name) not in suite_index
        ]

        suite = [
            self._compact_suite_record(record)
            for record in sorted(suite_records, key=lambda record: (record["lang"], record["system_name"]))
        ]

        cascade_deltas = []
        for lang in self.EXPECTED_LANGS:
            cascade = suite_index.get((lang, "cascade_final"))
            one_b = suite_index.get((lang, "1b_only"))
            seven_b = suite_index.get((lang, "7b_only"))
            cascade_deltas.append(
                {
                    "lang": lang,
                    "cascade_vs_1b_only": self._delta_metrics(cascade, one_b),
                    "cascade_vs_7b_only": self._delta_metrics(cascade, seven_b),
                }
            )

        threshold_review = self._build_threshold_review(suite_index, missing)

        return {
            "run_tag": run_tag,
            "generated_at": datetime.now().isoformat(),
            "summary_dir": str(self.summary_dir),
            "expected_suite_size": len(self.EXPECTED_LANGS) * len(self.EXPECTED_SYSTEMS),
            "actual_suite_size": len(suite_records),
            "complete": not missing,
            "missing": missing,
            "current_thresholds": dict(RiskCalibrator.THRESHOLDS),
            "suite": suite,
            "cascade_deltas": cascade_deltas,
            "threshold_review": threshold_review,
        }

    def save(self, run_tag: str, output_path: Path | None = None) -> Path:
        payload = self.build(run_tag)
        path = Path(output_path or (self.summary_dir / f"{run_tag}.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _load_suite_records(self, run_tag: str) -> List[Dict]:
        records = []
        for path in sorted(self.summary_dir.glob(f"*__{run_tag}__*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["_summary_path"] = str(path)
            records.append(payload)
        return records

    def _compact_suite_record(self, record: Dict) -> Dict:
        summary = record.get("overall_summary", {})
        return {
            "lang": record.get("lang", ""),
            "system_name": record.get("system_name", ""),
            "summary_file": record.get("_summary_path", ""),
            "generated_at": record.get("generated_at"),
            "warnings": list(record.get("warnings", [])),
            "metrics": self._extract_metrics(summary),
        }

    def _extract_metrics(self, summary: Dict | None) -> Dict:
        summary = summary or {}
        keys = (
            "total_items",
            "quality_score",
            "format_validity",
            "task_match_rate",
            "latency_avg",
            "latency_p50",
            "latency_p90",
            "accepted_by_1b_rate",
            "accepted_by_1b_quality",
            "escalated_quality",
            "7b_invocation_rate",
            "tokens_1b_avg",
            "tokens_7b_avg",
            "estimated_cost_proxy",
            "judge_score_avg",
        )
        return {key: summary.get(key) for key in keys}

    def _delta_metrics(self, left_record: Dict | None, right_record: Dict | None) -> Dict | None:
        if left_record is None or right_record is None:
            return None

        left = self._extract_metrics(left_record.get("overall_summary"))
        right = self._extract_metrics(right_record.get("overall_summary"))
        delta = {}
        for key, value in left.items():
            other = right.get(key)
            if isinstance(value, (int, float)) and isinstance(other, (int, float)):
                delta[key] = value - other
        return delta

    def _build_threshold_review(self, suite_index: Dict[Tuple[str, str], Dict], missing: List[Dict]) -> Dict:
        signals = []
        freeze_reasons = []
        accepted_total = 0
        sample_total = 0

        for lang in self.EXPECTED_LANGS:
            cascade = suite_index.get((lang, "cascade_final"))
            seven_b = suite_index.get((lang, "7b_only"))
            if cascade is None or seven_b is None:
                continue

            cascade_summary = self._extract_metrics(cascade.get("overall_summary"))
            seven_b_summary = self._extract_metrics(seven_b.get("overall_summary"))
            accepted_rate = cascade_summary.get("accepted_by_1b_rate")
            total_items = cascade_summary.get("total_items") or 0
            quality_delta = None
            if (
                cascade_summary.get("quality_score") is not None
                and seven_b_summary.get("quality_score") is not None
            ):
                quality_delta = cascade_summary["quality_score"] - seven_b_summary["quality_score"]

            if isinstance(accepted_rate, (int, float)):
                accepted_total += round(accepted_rate * total_items)
                sample_total += int(total_items)
                if accepted_rate < self.MIN_ACCEPT_RATE_TO_FREEZE:
                    freeze_reasons.append(
                        f"{lang}: accepted_by_1b_rate={accepted_rate:.4f} is below the {self.MIN_ACCEPT_RATE_TO_FREEZE:.2f} freeze floor."
                    )

            if (
                isinstance(quality_delta, (int, float))
                and quality_delta < -self.MAX_QUALITY_DROP_TO_FREEZE
            ):
                freeze_reasons.append(
                    f"{lang}: cascade quality drops {abs(quality_delta):.4f} vs 7b_only, beyond the {self.MAX_QUALITY_DROP_TO_FREEZE:.2f} tolerance."
                )

            signals.append(
                {
                    "lang": lang,
                    "accepted_by_1b_rate": accepted_rate,
                    "7b_invocation_rate": cascade_summary.get("7b_invocation_rate"),
                    "cascade_quality_score": cascade_summary.get("quality_score"),
                    "seven_b_quality_score": seven_b_summary.get("quality_score"),
                    "quality_delta_vs_7b_only": quality_delta,
                    "latency_delta_vs_7b_only": self._safe_delta(
                        cascade_summary.get("latency_avg"),
                        seven_b_summary.get("latency_avg"),
                    ),
                    "cost_delta_vs_7b_only": self._safe_delta(
                        cascade_summary.get("estimated_cost_proxy"),
                        seven_b_summary.get("estimated_cost_proxy"),
                    ),
                }
            )

        if missing:
            freeze_reasons.append("Not all zh/en x 1b_only/7b_only/cascade_final summaries are present.")

        weighted_accept_rate = (accepted_total / sample_total) if sample_total else None
        recommendation = "freeze" if not freeze_reasons else "hold"

        return {
            "heuristic": {
                "min_accept_rate_per_language": self.MIN_ACCEPT_RATE_TO_FREEZE,
                "max_quality_drop_vs_7b_only": self.MAX_QUALITY_DROP_TO_FREEZE,
                "note": "Freeze only when each language preserves near-7B quality while accepting a material slice of samples directly from 1B.",
            },
            "signals": signals,
            "weighted_accept_by_1b_rate": weighted_accept_rate,
            "recommendation": recommendation,
            "reasons": freeze_reasons or ["All freeze checks passed."],
        }

    def _safe_delta(self, left: object, right: object) -> float | None:
        if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
            return None
        return left - right
