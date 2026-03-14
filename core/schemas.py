"""
Core data structures for the final offline experiment system.
"""
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class NormalizedSample:
    sample_id: str
    task_key: str
    task_type: str
    task_family: str
    subject: str
    education_level: str
    lang: str
    question: str
    prompt_text: str
    expected_output_format: str
    ground_truth: Any
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RouterOutput:
    predicted_task_family: str
    predicted_subject: str
    draft_answer: Any
    confidence_label: str
    confidence_score: float
    format_signals: Dict[str, Any]
    tool_hint: str
    raw_text: str
    parse_ok: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RiskFeatures:
    confidence_score: float
    low_confidence_flag: bool
    format_error_flag: bool
    length_anomaly_flag: bool
    uncertainty_phrase_flag: bool
    task_prior: float
    subject_mismatch_flag: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RouteTrace:
    sample_id: str
    system_name: str
    accepted_by_1b: Optional[bool]
    risk_score: float
    risk_threshold: float
    specialist_name: str
    format_valid: bool
    latency_1b: float
    latency_7b: float
    tokens_1b: int
    tokens_7b: int
    notes: List[str] = field(default_factory=list)
    router_output: Dict[str, Any] = field(default_factory=dict)
    risk_features: Dict[str, Any] = field(default_factory=dict)
    raw_outputs: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InferenceResult:
    sample_id: str
    system_name: str
    task_key: str
    task_type: str
    task_family: str
    subject: str
    lang: str
    route: str
    accepted_by_1b: Optional[bool]
    specialist_name: str
    risk_score: Optional[float]
    prediction: Any
    ground_truth: Any
    format_valid: bool
    latency_seconds: float
    tokens_1b: int
    tokens_7b: int
    raw_model_outputs: Dict[str, Any] = field(default_factory=dict)
    judge_score: Optional[float] = None
    route_reason: str = ""
    expected_output_format: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
