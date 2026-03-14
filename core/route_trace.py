"""
Route tracing helpers for saved per-sample debugging artifacts.
"""
from typing import Optional

from core.schemas import NormalizedSample, RouteTrace


class RouteTracer:
    """Collect all routing decisions for one sample in a JSON-safe structure."""

    def start(self, sample: NormalizedSample, system_name: str) -> "RouteTracer":
        self.trace = RouteTrace(
            sample_id=sample.sample_id,
            system_name=system_name,
            accepted_by_1b=None,
            risk_score=0.0,
            risk_threshold=0.0,
            specialist_name="",
            format_valid=False,
            latency_1b=0.0,
            latency_7b=0.0,
            tokens_1b=0,
            tokens_7b=0,
            notes=[],
            router_output={},
            risk_features={},
            raw_outputs={},
        )
        return self

    def record_1b(self, *, latency_seconds: float, tokens: int, router_output: dict, raw_output: dict) -> None:
        self.trace.latency_1b = latency_seconds
        self.trace.tokens_1b = tokens
        self.trace.router_output = router_output
        self.trace.raw_outputs["1b"] = raw_output

    def record_risk(
        self,
        *,
        risk_score: float,
        risk_threshold: float,
        specialist_name: str,
        accepted_by_1b: Optional[bool],
        features: dict,
        note: str = "",
    ) -> None:
        self.trace.risk_score = risk_score
        self.trace.risk_threshold = risk_threshold
        self.trace.specialist_name = specialist_name
        self.trace.accepted_by_1b = accepted_by_1b
        self.trace.risk_features = features
        if note:
            self.trace.notes.append(note)

    def record_7b(self, *, latency_seconds: float, tokens: int, raw_output: dict, note: str = "") -> None:
        self.trace.latency_7b += latency_seconds
        self.trace.tokens_7b += tokens
        self.trace.raw_outputs.setdefault("7b", []).append(raw_output)
        if note:
            self.trace.notes.append(note)

    def finalize(self, *, format_valid: bool, note: str = "") -> RouteTrace:
        self.trace.format_valid = format_valid
        if note:
            self.trace.notes.append(note)
        return self.trace
