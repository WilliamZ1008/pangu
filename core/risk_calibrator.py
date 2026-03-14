"""
Transparent calibrated risk scoring for the final 1B -> 7B cascade.
"""
import re
from typing import Optional

from core.schemas import NormalizedSample, RiskFeatures, RouterOutput


class RiskCalibrator:
    """Deterministic weighted risk scorer."""

    TASK_PRIORS = {
        "Q&A": 0.15,
        "EC": 0.25,
        "IP": 0.20,
        "AG": 0.45,
        "PCC": 0.50,
        "PLS": 0.50,
        "QG": 0.55,
        "TMG": 0.55,
    }

    THRESHOLDS = {
        "reasoning": 0.45,
        "assessment": 0.35,
        "planning": 0.40,
    }

    UNCERTAINTY_PATTERNS = [
        r"\bmaybe\b",
        r"\bnot sure\b",
        r"\bperhaps\b",
        r"\bi think\b",
        r"可能",
        r"不确定",
        r"也许",
        r"大概",
    ]

    def __init__(self, output_parser: Optional[object] = None):
        self.output_parser = output_parser

    def extract_features(self, sample: NormalizedSample, router_output: RouterOutput) -> RiskFeatures:
        format_error_flag = False
        if self.output_parser is not None:
            format_valid, _ = self.output_parser.validate_prediction(sample, router_output.draft_answer)
            format_error_flag = not format_valid
        elif isinstance(router_output.format_signals, dict):
            format_error_flag = not bool(router_output.format_signals.get("contract_ok", False))

        draft_text = router_output.draft_answer if isinstance(router_output.draft_answer, str) else str(router_output.draft_answer)
        normalized_predicted_subject = (router_output.predicted_subject or "").strip().lower()
        normalized_subject = (sample.subject or "").strip().lower()

        return RiskFeatures(
            confidence_score=router_output.confidence_score,
            low_confidence_flag=router_output.confidence_score < 0.65 or router_output.confidence_label in {"low", "uncertain"},
            format_error_flag=format_error_flag,
            length_anomaly_flag=len(draft_text.strip()) < 12 or len(draft_text) > 4000,
            uncertainty_phrase_flag=any(re.search(pattern, draft_text.lower()) for pattern in self.UNCERTAINTY_PATTERNS),
            task_prior=self.TASK_PRIORS.get(sample.task_key, 0.35),
            subject_mismatch_flag=bool(normalized_subject and normalized_predicted_subject and normalized_subject != normalized_predicted_subject),
        )

    def score(self, features: RiskFeatures) -> float:
        risk = (
            0.35 * float(features.low_confidence_flag)
            + 0.20 * float(features.format_error_flag)
            + 0.15 * float(features.uncertainty_phrase_flag)
            + 0.10 * float(features.length_anomaly_flag)
            + 0.20 * float(features.task_prior)
        )
        if features.subject_mismatch_flag:
            risk += 0.05
        return max(0.0, min(1.0, risk))

    def should_escalate(self, sample: NormalizedSample, features: RiskFeatures, score: float) -> bool:
        threshold = self.THRESHOLDS.get(self._family_to_specialist(sample.task_key, sample.task_family), 0.45)
        return score >= threshold

    def threshold_for(self, specialist_name: str) -> float:
        return self.THRESHOLDS.get(specialist_name, 0.45)

    def _family_to_specialist(self, task_key: str, task_family: str) -> str:
        if task_key == "AG":
            return "assessment"
        if task_key in {"PCC", "PLS", "QG", "TMG"}:
            return "planning"
        return "reasoning"
