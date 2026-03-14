"""
Inference orchestration layer for baseline, diagnostic, and final cascade systems.
"""
from types import SimpleNamespace
from typing import Any, Dict, Tuple

from config import (
    MAX_NEW_TOKENS_FAST,
    MAX_NEW_TOKENS_SELF_EVAL,
    MAX_NEW_TOKENS_SLOW,
    TEMPERATURE_FAST,
    TEMPERATURE_SELF_EVAL,
    TEMPERATURE_SLOW,
)
from core.expert_router import ExpertRouter
from core.prompting.prompt_manager import PromptManager
from core.request_normalizer import RequestNormalizer
from core.route_trace import RouteTracer
from core.risk_calibrator import RiskCalibrator
from core.schemas import InferenceResult, NormalizedSample, RouteTrace, RouterOutput
from difficulty_decision import DifficultyDecision
from services.model_clients import ClientRegistry
from services.output_parser import OutputParser


SUPPORTED_SYSTEMS = (
    "rule_v2",
    "current_v3",
    "1b_only",
    "7b_only",
    "cascade_final",
)


class InferenceEngine:
    """Experiment-time orchestration around prompts, model clients, parsing, and routing."""

    def __init__(self):
        self.normalizer = RequestNormalizer()
        self.prompt_manager = PromptManager()
        self.output_parser = OutputParser()
        self.expert_router = ExpertRouter()
        self.client_registry = ClientRegistry()
        self.client = self.client_registry.client()
        self.risk_calibrator = RiskCalibrator(self.output_parser)
        self.rule_router = DifficultyDecision()

    def run_system(self, system_name: str, sample: Any) -> tuple[InferenceResult, RouteTrace, NormalizedSample]:
        if system_name not in SUPPORTED_SYSTEMS:
            raise ValueError(f"Unsupported system: {system_name}")
        return getattr(self, f"run_{system_name}")(sample)

    def run_rule_v2(self, sample: Any) -> tuple[InferenceResult, RouteTrace, NormalizedSample]:
        normalized = self._normalize(sample)
        tracer = RouteTracer().start(normalized, "rule_v2")
        baseline_decision = self.rule_router.decide(self._baseline_router_view(normalized))
        specialist_name = self.expert_router.select(normalized)
        tracer.record_risk(
            risk_score=0.0,
            risk_threshold=0.0,
            specialist_name=specialist_name,
            accepted_by_1b=None,
            features={},
            note=baseline_decision["reason"],
        )

        mode = "fast" if baseline_decision["route"] == "fast" else "slow"
        prediction, format_valid, stage_records, latency_seconds, tokens = self._run_rule_prompt(
            normalized,
            tier="7b",
            mode=mode,
        )
        tracer.record_7b(
            latency_seconds=latency_seconds,
            tokens=tokens,
            raw_output=stage_records,
            note=f"baseline_route={baseline_decision['route']}",
        )
        trace = tracer.finalize(format_valid=format_valid)
        result = self._build_result(
            normalized,
            system_name="rule_v2",
            route=baseline_decision["route"],
            accepted_by_1b=None,
            specialist_name=specialist_name,
            risk_score=None,
            prediction=prediction,
            format_valid=format_valid,
            latency_seconds=latency_seconds,
            tokens_1b=0,
            tokens_7b=tokens,
            raw_model_outputs=trace.raw_outputs,
            route_reason=baseline_decision["reason"],
        )
        return result, trace, normalized

    def run_current_v3(self, sample: Any) -> tuple[InferenceResult, RouteTrace, NormalizedSample]:
        normalized = self._normalize(sample)
        tracer = RouteTracer().start(normalized, "current_v3")
        specialist_name = self.expert_router.select(normalized)
        tracer.record_risk(
            risk_score=0.0,
            risk_threshold=0.0,
            specialist_name=specialist_name,
            accepted_by_1b=None,
            features={},
            note="diagnostic legacy 7B fast -> self_check -> slow flow",
        )

        fast_prediction, fast_valid, fast_stage, fast_latency, fast_tokens = self._run_rule_prompt(
            normalized,
            tier="7b",
            mode="fast",
        )
        tracer.record_7b(
            latency_seconds=fast_latency,
            tokens=fast_tokens,
            raw_output=fast_stage,
            note="diagnostic_fast_stage",
        )

        self_check = self._run_self_check(normalized, fast_prediction)
        tracer.record_7b(
            latency_seconds=self_check["latency_seconds"],
            tokens=self_check["tokens"],
            raw_output=self_check["stage_record"],
            note=f"self_check_label={self_check['label']}",
        )

        if self_check["label"] == "confident" and fast_valid:
            final_prediction = fast_prediction
            format_valid = fast_valid
            latency_seconds = fast_latency + self_check["latency_seconds"]
            tokens_7b = fast_tokens + self_check["tokens"]
            route = "7b_fast_accept"
            route_reason = "legacy self-check accepted the fast prediction"
        else:
            slow_prediction, slow_valid, slow_stage, slow_latency, slow_tokens = self._run_rule_prompt(
                normalized,
                tier="7b",
                mode="slow",
            )
            tracer.record_7b(
                latency_seconds=slow_latency,
                tokens=slow_tokens,
                raw_output=slow_stage,
                note="diagnostic_slow_stage",
            )
            final_prediction = slow_prediction
            format_valid = slow_valid
            latency_seconds = fast_latency + self_check["latency_seconds"] + slow_latency
            tokens_7b = fast_tokens + self_check["tokens"] + slow_tokens
            route = "7b_fast_to_7b_slow"
            route_reason = f"legacy self-check escalated with label={self_check['label']}"

        trace = tracer.finalize(format_valid=format_valid)
        result = self._build_result(
            normalized,
            system_name="current_v3",
            route=route,
            accepted_by_1b=None,
            specialist_name=specialist_name,
            risk_score=None,
            prediction=final_prediction,
            format_valid=format_valid,
            latency_seconds=latency_seconds,
            tokens_1b=0,
            tokens_7b=tokens_7b,
            raw_model_outputs=trace.raw_outputs,
            route_reason=route_reason,
        )
        return result, trace, normalized

    def run_1b_only(self, sample: Any) -> tuple[InferenceResult, RouteTrace, NormalizedSample]:
        normalized = self._normalize(sample)
        tracer = RouteTracer().start(normalized, "1b_only")
        router_output, stage_record, latency_seconds, tokens = self._run_router_stage(normalized)
        tracer.record_1b(
            latency_seconds=latency_seconds,
            tokens=tokens,
            router_output=router_output.to_dict(),
            raw_output=stage_record,
        )
        normalized_prediction = self.output_parser.repair_or_normalize(normalized, router_output.draft_answer)
        prediction = normalized_prediction["normalized_prediction"]
        format_valid = not normalized_prediction["errors"]
        tracer.record_risk(
            risk_score=0.0,
            risk_threshold=0.0,
            specialist_name="",
            accepted_by_1b=True,
            features={},
            note="single-tier 1B router baseline",
        )
        trace = tracer.finalize(
            format_valid=format_valid,
            note="; ".join(normalized_prediction["errors"]),
        )
        result = self._build_result(
            normalized,
            system_name="1b_only",
            route="1b_only",
            accepted_by_1b=True,
            specialist_name="",
            risk_score=0.0,
            prediction=prediction,
            format_valid=format_valid,
            latency_seconds=latency_seconds,
            tokens_1b=tokens,
            tokens_7b=0,
            raw_model_outputs=trace.raw_outputs,
            route_reason="single-tier 1B baseline using router draft answer",
        )
        return result, trace, normalized

    def run_7b_only(self, sample: Any) -> tuple[InferenceResult, RouteTrace, NormalizedSample]:
        normalized = self._normalize(sample)
        tracer = RouteTracer().start(normalized, "7b_only")
        specialist_name = self.expert_router.select(normalized)
        placeholder_router = self._placeholder_router_output(normalized)
        prediction, format_valid, stage_records, latency_seconds, tokens = self._run_specialist_stage(
            normalized,
            placeholder_router,
            specialist_name,
        )
        tracer.record_risk(
            risk_score=0.0,
            risk_threshold=0.0,
            specialist_name=specialist_name,
            accepted_by_1b=None,
            features={},
            note="single-tier 7B specialist baseline",
        )
        tracer.record_7b(
            latency_seconds=latency_seconds,
            tokens=tokens,
            raw_output=stage_records,
            note="7b_only_specialist",
        )
        trace = tracer.finalize(format_valid=format_valid)
        result = self._build_result(
            normalized,
            system_name="7b_only",
            route=f"7b_only:{specialist_name}",
            accepted_by_1b=None,
            specialist_name=specialist_name,
            risk_score=0.0,
            prediction=prediction,
            format_valid=format_valid,
            latency_seconds=latency_seconds,
            tokens_1b=0,
            tokens_7b=tokens,
            raw_model_outputs=trace.raw_outputs,
            route_reason="single-tier 7B specialist baseline",
        )
        return result, trace, normalized

    def run_cascade_final(self, sample: Any) -> tuple[InferenceResult, RouteTrace, NormalizedSample]:
        normalized = self._normalize(sample)
        tracer = RouteTracer().start(normalized, "cascade_final")

        router_output, router_stage, latency_1b, tokens_1b = self._run_router_stage(normalized)
        tracer.record_1b(
            latency_seconds=latency_1b,
            tokens=tokens_1b,
            router_output=router_output.to_dict(),
            raw_output=router_stage,
        )

        specialist_name = self.expert_router.select(normalized, router_output)
        features = self.risk_calibrator.extract_features(normalized, router_output)
        risk_score = self.risk_calibrator.score(features)
        risk_threshold = self.risk_calibrator.threshold_for(specialist_name)
        should_escalate = self.risk_calibrator.should_escalate(normalized, features, risk_score)

        normalized_1b = self.output_parser.repair_or_normalize(normalized, router_output.draft_answer)
        if not should_escalate and normalized_1b["errors"]:
            should_escalate = True

        tracer.record_risk(
            risk_score=risk_score,
            risk_threshold=risk_threshold,
            specialist_name=specialist_name,
            accepted_by_1b=not should_escalate,
            features=features.to_dict(),
            note="deterministic calibrated routing",
        )

        if should_escalate:
            prediction, format_valid, stage_records, latency_7b, tokens_7b = self._run_specialist_stage(
                normalized,
                router_output,
                specialist_name,
            )
            tracer.record_7b(
                latency_seconds=latency_7b,
                tokens=tokens_7b,
                raw_output=stage_records,
                note="cascade_7b_refine",
            )
            route = f"1b_to_7b:{specialist_name}"
            route_reason = f"risk_score={risk_score:.3f} threshold={risk_threshold:.3f}"
            accepted_by_1b = False
        else:
            prediction = normalized_1b["normalized_prediction"]
            format_valid = not normalized_1b["errors"]
            latency_7b = 0.0
            tokens_7b = 0
            route = "1b_accept"
            route_reason = f"risk_score={risk_score:.3f} threshold={risk_threshold:.3f}"
            accepted_by_1b = True

        trace = tracer.finalize(
            format_valid=format_valid,
            note="; ".join(normalized_1b["errors"]) if normalized_1b["errors"] and accepted_by_1b else "",
        )
        result = self._build_result(
            normalized,
            system_name="cascade_final",
            route=route,
            accepted_by_1b=accepted_by_1b,
            specialist_name=specialist_name,
            risk_score=risk_score,
            prediction=prediction,
            format_valid=format_valid,
            latency_seconds=latency_1b + latency_7b,
            tokens_1b=tokens_1b,
            tokens_7b=tokens_7b,
            raw_model_outputs=trace.raw_outputs,
            route_reason=route_reason,
        )
        return result, trace, normalized

    def infer_dynamic(self, data_item: Any) -> Dict[str, Any]:
        result, trace, _ = self.run_current_v3(data_item)
        self_check_records = trace.raw_outputs.get("7b", [])
        self_check_stage = {}
        for record in self_check_records:
            if isinstance(record, dict) and record.get("stage") == "self_check":
                self_check_stage = record
                break
        return {
            "final_answer": result.prediction,
            "fast_response": self_check_stage.get("candidate_answer"),
            "slow_thinking": None,
            "eval_label": self_check_stage.get("label"),
            "eval_reason": self_check_stage.get("reason"),
            "is_slow_triggered": result.route == "7b_fast_to_7b_slow",
        }

    def _normalize(self, sample: Any) -> NormalizedSample:
        return self.normalizer.normalize_data_item(sample)

    def _run_router_stage(self, sample: NormalizedSample) -> tuple[RouterOutput, Dict[str, Any], float, int]:
        prompt, template_name = self.prompt_manager.build_1b_router_prompt(sample)
        target = self.client_registry.get("1b")
        generation = self.client.generate_text(
            prompt=prompt,
            endpoint=target["endpoint"],
            model_name=target["model_name"],
            max_tokens=MAX_NEW_TOKENS_FAST,
            temperature=TEMPERATURE_FAST,
        )
        router_output = self.output_parser.parse_router_output(generation.text)
        stage_record = {
            "stage": "router_1b",
            "tier": "1b",
            "prompt_template": template_name,
            "prompt": prompt,
            "text": generation.text,
            "latency_seconds": generation.latency_seconds,
            "tokens": generation.total_tokens,
            "router_output": router_output.to_dict(),
            "raw_response": generation.raw_response,
        }
        return router_output, stage_record, generation.latency_seconds, generation.total_tokens

    def _run_specialist_stage(
        self,
        sample: NormalizedSample,
        router_output: RouterOutput,
        specialist_name: str,
    ) -> tuple[Any, bool, Dict[str, Any], float, int]:
        prompt, template_name = self.prompt_manager.build_7b_specialist_prompt(sample, router_output, specialist_name)
        target = self.client_registry.get("7b")
        generation = self.client.generate_text(
            prompt=prompt,
            endpoint=target["endpoint"],
            model_name=target["model_name"],
            max_tokens=MAX_NEW_TOKENS_SLOW,
            temperature=TEMPERATURE_SLOW,
        )
        format_valid, normalized = self.output_parser.validate_prediction(sample, generation.text)
        stage_records = {
            "stage": "specialist_7b",
            "tier": "7b",
            "prompt_template": template_name,
            "prompt": prompt,
            "text": generation.text,
            "latency_seconds": generation.latency_seconds,
            "tokens": generation.total_tokens,
            "normalized_prediction": normalized["normalized_prediction"],
            "errors": normalized["errors"],
            "raw_response": generation.raw_response,
        }
        total_latency = generation.latency_seconds
        total_tokens = generation.total_tokens

        if not format_valid:
            repair_prompt, repair_template = self.prompt_manager.build_format_repair_prompt(sample, generation.text)
            repair_generation = self.client.generate_text(
                prompt=repair_prompt,
                endpoint=target["endpoint"],
                model_name=target["model_name"],
                max_tokens=MAX_NEW_TOKENS_FAST,
                temperature=TEMPERATURE_FAST,
            )
            repair_valid, repaired = self.output_parser.validate_prediction(sample, repair_generation.text)
            stage_records["format_repair"] = {
                "stage": "format_repair_7b",
                "tier": "7b",
                "prompt_template": repair_template,
                "prompt": repair_prompt,
                "text": repair_generation.text,
                "latency_seconds": repair_generation.latency_seconds,
                "tokens": repair_generation.total_tokens,
                "normalized_prediction": repaired["normalized_prediction"],
                "errors": repaired["errors"],
                "raw_response": repair_generation.raw_response,
            }
            total_latency += repair_generation.latency_seconds
            total_tokens += repair_generation.total_tokens
            if repair_valid:
                return repaired["normalized_prediction"], True, stage_records, total_latency, total_tokens

        return normalized["normalized_prediction"], format_valid, stage_records, total_latency, total_tokens

    def _run_rule_prompt(
        self,
        sample: NormalizedSample,
        *,
        tier: str,
        mode: str,
    ) -> tuple[Any, bool, Dict[str, Any], float, int]:
        prompt, template_name = self.prompt_manager.build_rule_baseline_prompt(sample, mode)
        target = self.client_registry.get(tier)
        generation = self.client.generate_text(
            prompt=prompt,
            endpoint=target["endpoint"],
            model_name=target["model_name"],
            max_tokens=MAX_NEW_TOKENS_FAST if mode == "fast" else MAX_NEW_TOKENS_SLOW,
            temperature=TEMPERATURE_FAST if mode == "fast" else TEMPERATURE_SLOW,
        )
        format_valid, normalized = self.output_parser.validate_prediction(sample, generation.text)
        stage_record = {
            "stage": f"rule_{mode}",
            "tier": tier,
            "prompt_template": template_name,
            "prompt": prompt,
            "text": generation.text,
            "latency_seconds": generation.latency_seconds,
            "tokens": generation.total_tokens,
            "normalized_prediction": normalized["normalized_prediction"],
            "errors": normalized["errors"],
            "raw_response": generation.raw_response,
        }
        return normalized["normalized_prediction"], format_valid, stage_record, generation.latency_seconds, generation.total_tokens

    def _run_self_check(self, sample: NormalizedSample, candidate_answer: Any) -> Dict[str, Any]:
        prompt, template_name = self.prompt_manager.build_self_check_prompt(sample, str(candidate_answer))
        target = self.client_registry.get("7b")
        generation = self.client.generate_json(
            prompt=prompt,
            endpoint=target["endpoint"],
            model_name=target["model_name"],
            max_tokens=MAX_NEW_TOKENS_SELF_EVAL,
            temperature=TEMPERATURE_SELF_EVAL,
        )
        parsed = generation.parsed_json if generation.parse_ok and isinstance(generation.parsed_json, dict) else {}
        label = str(parsed.get("label", "uncertain")).strip().lower()
        if label not in {"confident", "uncertain", "incorrect"}:
            label = "uncertain"
        reason = str(parsed.get("reason", generation.text)).strip()
        stage_record = {
            "stage": "self_check",
            "tier": "7b",
            "prompt_template": template_name,
            "prompt": prompt,
            "text": generation.text,
            "latency_seconds": generation.latency_seconds,
            "tokens": generation.total_tokens,
            "label": label,
            "reason": reason,
            "candidate_answer": candidate_answer,
            "raw_response": generation.raw_response,
        }
        return {
            "label": label,
            "reason": reason,
            "latency_seconds": generation.latency_seconds,
            "tokens": generation.total_tokens,
            "stage_record": stage_record,
        }

    def _placeholder_router_output(self, sample: NormalizedSample) -> RouterOutput:
        return RouterOutput(
            predicted_task_family=sample.task_family,
            predicted_subject=sample.subject,
            draft_answer="",
            confidence_label="high",
            confidence_score=1.0,
            format_signals={"contract_ok": True, "notes": ["7b_only baseline"]},
            tool_hint="",
            raw_text="",
            parse_ok=True,
        )

    def _baseline_router_view(self, sample: NormalizedSample) -> SimpleNamespace:
        return SimpleNamespace(
            task_type=sample.task_type,
            subject=sample.subject,
            education_level=sample.education_level,
            question_type=sample.metadata.get("question_type", ""),
            question=sample.question,
            prompt=sample.prompt_text,
        )

    def _build_result(
        self,
        sample: NormalizedSample,
        *,
        system_name: str,
        route: str,
        accepted_by_1b,
        specialist_name: str,
        risk_score,
        prediction,
        format_valid: bool,
        latency_seconds: float,
        tokens_1b: int,
        tokens_7b: int,
        raw_model_outputs: Dict[str, Any],
        route_reason: str,
    ) -> InferenceResult:
        metadata = {
            "source_file": sample.metadata.get("source_file", ""),
            "source_row": sample.metadata.get("source_row", 0),
            "prompt": sample.prompt_text,
            "question": sample.question,
            "expected_output_format": sample.expected_output_format,
        }
        return InferenceResult(
            sample_id=sample.sample_id,
            system_name=system_name,
            task_key=sample.task_key,
            task_type=sample.task_type,
            task_family=sample.task_family,
            subject=sample.subject,
            lang=sample.lang,
            route=route,
            accepted_by_1b=accepted_by_1b,
            specialist_name=specialist_name,
            risk_score=risk_score,
            prediction=prediction,
            ground_truth=sample.ground_truth,
            format_valid=format_valid,
            latency_seconds=latency_seconds,
            tokens_1b=tokens_1b,
            tokens_7b=tokens_7b,
            raw_model_outputs=raw_model_outputs,
            route_reason=route_reason,
            expected_output_format=sample.expected_output_format,
            metadata=metadata,
        )
