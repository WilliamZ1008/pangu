"""
Inference orchestration for baseline and diagnostic experiment systems.
"""
import json
import re
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, Optional, Tuple

import requests

from config import (
    DEFAULT_EXPLANATION_LEVEL,
    MAX_NEW_TOKENS_FAST,
    MAX_NEW_TOKENS_SELF_EVAL,
    MAX_NEW_TOKENS_SLOW,
    MODEL_NAME_1B,
    MODEL_NAME_7B,
    TEMPERATURE_FAST,
    TEMPERATURE_SELF_EVAL,
    TEMPERATURE_SLOW,
    TOP_P,
    VLLM_API_URL_1B,
    VLLM_API_URL_7B,
    VLLM_MODELS_URL_1B,
    VLLM_MODELS_URL_7B,
)
from core.prompts import render_refine_prompt, render_self_eval_prompt, render_task_prompt
from difficulty_decision import DifficultyDecision


SUPPORTED_SYSTEMS = (
    "rule_v2",
    "current_v3",
    "1b_only",
    "7b_only",
    "cascade_final",
)

VALID_SELF_EVAL_LABELS = ("confident", "uncertain", "incorrect")


@dataclass
class StageResult:
    stage: str
    tier: str
    mode: str
    model_name: str
    api_url: str
    prompt_template: str
    prompt: str
    raw_text: str
    final_text: str
    format_valid: bool
    structured_prediction: Optional[Any] = None
    parse_note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "tier": self.tier,
            "mode": self.mode,
            "model_name": self.model_name,
            "api_url": self.api_url,
            "prompt_template": self.prompt_template,
            "prompt": self.prompt,
            "raw_text": self.raw_text,
            "final_text": self.final_text,
            "format_valid": self.format_valid,
            "structured_prediction": self.structured_prediction,
            "parse_note": self.parse_note,
        }


class InferenceEngine:
    """Run baseline and diagnostic experiment systems with traceable outputs."""

    def __init__(self):
        self.headers = {"Content-Type": "application/json"}
        self.router = DifficultyDecision()
        self._checked_tiers = set()
        self._service_check_lock = Lock()
        self._tier_config = {
            "1b": {
                "api_url": VLLM_API_URL_1B,
                "models_url": VLLM_MODELS_URL_1B,
                "model_name": MODEL_NAME_1B,
            },
            "7b": {
                "api_url": VLLM_API_URL_7B,
                "models_url": VLLM_MODELS_URL_7B,
                "model_name": MODEL_NAME_7B,
            },
        }

    def run_system(self, system_name: str, data_item: Any) -> Dict[str, Any]:
        if system_name not in SUPPORTED_SYSTEMS:
            raise ValueError(f"Unsupported system: {system_name}")
        return getattr(self, f"run_{system_name}")(data_item)

    def run_rule_v2(self, data_item: Any) -> Dict[str, Any]:
        route_info = self.router.decide(data_item)
        stages: Dict[str, Dict[str, Any]] = {}
        start_time = time.perf_counter()

        if route_info["route"] == "fast":
            final_stage = self._run_task_stage(data_item, tier="7b", stage="fast", mode="fast")
            stages["fast"] = final_stage.to_dict()
            seven_b_refine_invoked = False
        elif route_info["route"] == "slow":
            final_stage = self._run_task_stage(data_item, tier="7b", stage="slow", mode="slow")
            stages["slow"] = final_stage.to_dict()
            seven_b_refine_invoked = True
        else:
            slow_stage = self._run_task_stage(data_item, tier="7b", stage="slow", mode="slow")
            refine_stage = self._run_refine_stage(data_item, draft_answer=slow_stage.final_text, tier="7b")
            stages["slow"] = slow_stage.to_dict()
            stages["refine"] = refine_stage.to_dict()
            final_stage = refine_stage
            seven_b_refine_invoked = True

        latency_seconds = time.perf_counter() - start_time
        return self._build_result(
            system_name="rule_v2",
            route=route_info["route"],
            route_reason=route_info["reason"],
            final_stage=final_stage,
            latency_seconds=latency_seconds,
            stages=stages,
            accepted_by_1b=None,
            seven_b_refine_invoked=seven_b_refine_invoked,
            self_eval=None,
        )

    def run_current_v3(self, data_item: Any) -> Dict[str, Any]:
        stages: Dict[str, Dict[str, Any]] = {}
        start_time = time.perf_counter()

        fast_stage = self._run_task_stage(data_item, tier="7b", stage="fast", mode="fast")
        stages["fast"] = fast_stage.to_dict()

        self_eval = self.self_evaluate(data_item, fast_stage.final_text, tier="7b")
        stages["self_eval"] = self_eval

        if self_eval["label"] == "confident" and self_eval["parse_ok"] and fast_stage.format_valid:
            final_stage = fast_stage
            route = "7b_fast_accept"
            route_reason = "7B self-eval accepted the fast answer"
            seven_b_refine_invoked = False
        else:
            slow_stage = self._run_task_stage(data_item, tier="7b", stage="slow", mode="slow")
            refine_stage = self._run_refine_stage(data_item, draft_answer=slow_stage.final_text, tier="7b")
            stages["slow"] = slow_stage.to_dict()
            stages["refine"] = refine_stage.to_dict()
            final_stage = refine_stage
            route = "7b_fast_to_7b_slow_then_fast"
            route_reason = (
                f"7B self-eval escalated fast answer; label={self_eval['label']}; parse_ok={self_eval['parse_ok']}"
            )
            seven_b_refine_invoked = True

        latency_seconds = time.perf_counter() - start_time
        return self._build_result(
            system_name="current_v3",
            route=route,
            route_reason=route_reason,
            final_stage=final_stage,
            latency_seconds=latency_seconds,
            stages=stages,
            accepted_by_1b=None,
            seven_b_refine_invoked=seven_b_refine_invoked,
            self_eval=self_eval,
        )

    def run_1b_only(self, data_item: Any) -> Dict[str, Any]:
        start_time = time.perf_counter()
        fast_stage = self._run_task_stage(data_item, tier="1b", stage="fast", mode="fast")
        latency_seconds = time.perf_counter() - start_time
        return self._build_result(
            system_name="1b_only",
            route="1b_fast",
            route_reason="single-tier 1B fast baseline",
            final_stage=fast_stage,
            latency_seconds=latency_seconds,
            stages={"fast": fast_stage.to_dict()},
            accepted_by_1b=None,
            seven_b_refine_invoked=False,
            self_eval=None,
        )

    def run_7b_only(self, data_item: Any) -> Dict[str, Any]:
        start_time = time.perf_counter()
        slow_stage = self._run_task_stage(data_item, tier="7b", stage="slow", mode="slow")
        latency_seconds = time.perf_counter() - start_time
        return self._build_result(
            system_name="7b_only",
            route="7b_slow",
            route_reason="single-tier 7B slow baseline",
            final_stage=slow_stage,
            latency_seconds=latency_seconds,
            stages={"slow": slow_stage.to_dict()},
            accepted_by_1b=None,
            seven_b_refine_invoked=True,
            self_eval=None,
        )

    def run_cascade_final(self, data_item: Any) -> Dict[str, Any]:
        stages: Dict[str, Dict[str, Any]] = {}
        start_time = time.perf_counter()

        draft_stage = self._run_task_stage(data_item, tier="1b", stage="draft_fast", mode="fast")
        stages["draft_fast"] = draft_stage.to_dict()

        accepted, accept_reason = self._should_accept_1b(data_item, draft_stage)
        if accepted:
            final_stage = draft_stage
            route = "1b_fast_accept"
            route_reason = accept_reason
            seven_b_refine_invoked = False
            accepted_by_1b = True
        else:
            refine_stage = self._run_refine_stage(data_item, draft_answer=draft_stage.final_text, tier="7b")
            stages["refine"] = refine_stage.to_dict()
            final_stage = refine_stage
            route = "1b_fast_to_7b_refine"
            route_reason = accept_reason
            seven_b_refine_invoked = True
            accepted_by_1b = False

        latency_seconds = time.perf_counter() - start_time
        return self._build_result(
            system_name="cascade_final",
            route=route,
            route_reason=route_reason,
            final_stage=final_stage,
            latency_seconds=latency_seconds,
            stages=stages,
            accepted_by_1b=accepted_by_1b,
            seven_b_refine_invoked=seven_b_refine_invoked,
            self_eval=None,
        )

    def infer_dynamic(self, data_item: Any) -> Dict[str, Any]:
        """Backward-compatible alias for the diagnostic pipeline."""
        result = self.run_current_v3(data_item)
        self_eval = result.get("self_eval") or {}
        return {
            "final_answer": result["prediction"],
            "fast_response": (result["raw_model_outputs"].get("fast") or {}).get("final_text"),
            "slow_thinking": (result["raw_model_outputs"].get("slow") or {}).get("raw_text"),
            "eval_label": self_eval.get("label"),
            "eval_reason": self_eval.get("reason"),
            "is_slow_triggered": "slow" in result["raw_model_outputs"] or "refine" in result["raw_model_outputs"],
        }

    def self_evaluate(self, data_item: Any, candidate_answer: str, tier: str = "7b") -> Dict[str, Any]:
        prompt = render_self_eval_prompt(data_item.prompt, candidate_answer, lang=data_item.lang)
        raw_output = self._call_vllm(
            tier=tier,
            prompt=prompt,
            max_tokens=MAX_NEW_TOKENS_SELF_EVAL,
            temperature=TEMPERATURE_SELF_EVAL,
        )
        label, parse_ok = self._parse_self_eval_label(raw_output)
        reason_match = re.search(r"reason\s*:\s*(.*)", raw_output, re.IGNORECASE | re.DOTALL)
        reason = reason_match.group(1).strip() if reason_match else raw_output.strip()
        return {
            "stage": "self_eval",
            "tier": tier,
            "prompt_template": f"self_eval:{data_item.lang}",
            "prompt": prompt,
            "raw_output": raw_output,
            "label": label,
            "reason": reason,
            "parse_ok": parse_ok,
        }

    def _should_accept_1b(self, data_item: Any, draft_stage: StageResult) -> Tuple[bool, str]:
        if not draft_stage.format_valid:
            return False, "1B draft rejected because output format is invalid"
        if draft_stage.final_text.startswith("[ERROR:"):
            return False, "1B draft rejected because the model call failed"
        if data_item.task_type not in {
            "question_answering",
            "error_correction",
            "idea_prompting",
        }:
            return False, f"task_type={data_item.task_type} reserved for 7B refinement"
        if len(draft_stage.final_text.strip()) < 12:
            return False, "1B draft rejected because the answer is too short"
        return True, "1B draft accepted by deterministic cascade gate"

    def _run_task_stage(self, data_item: Any, tier: str, stage: str, mode: str) -> StageResult:
        prompt_text, template_name = render_task_prompt(
            data_item,
            mode=mode,
            explanation_level=DEFAULT_EXPLANATION_LEVEL,
        )
        return self._run_generation_stage(
            data_item=data_item,
            tier=tier,
            stage=stage,
            mode=mode,
            prompt_text=prompt_text,
            prompt_template=template_name,
        )

    def _run_refine_stage(self, data_item: Any, draft_answer: str, tier: str) -> StageResult:
        prompt_text, template_name = render_refine_prompt(data_item, draft_answer=draft_answer)
        return self._run_generation_stage(
            data_item=data_item,
            tier=tier,
            stage="refine",
            mode="slow",
            prompt_text=prompt_text,
            prompt_template=template_name,
        )

    def _run_generation_stage(
        self,
        data_item: Any,
        tier: str,
        stage: str,
        mode: str,
        prompt_text: str,
        prompt_template: str,
    ) -> StageResult:
        raw_text = self._call_vllm(
            tier=tier,
            prompt=prompt_text,
            max_tokens=MAX_NEW_TOKENS_FAST if mode == "fast" else MAX_NEW_TOKENS_SLOW,
            temperature=TEMPERATURE_FAST if mode == "fast" else TEMPERATURE_SLOW,
        )
        candidate_text = self._extract_final_answer(raw_text) if mode == "slow" else raw_text.strip()
        format_valid, final_text, structured_prediction, parse_note = self._normalize_prediction(
            data_item.expected_output_format,
            candidate_text,
        )
        tier_config = self._tier_config[tier]
        return StageResult(
            stage=stage,
            tier=tier,
            mode=mode,
            model_name=tier_config["model_name"],
            api_url=tier_config["api_url"],
            prompt_template=prompt_template,
            prompt=prompt_text,
            raw_text=raw_text,
            final_text=final_text,
            format_valid=format_valid,
            structured_prediction=structured_prediction,
            parse_note=parse_note,
        )

    def _call_vllm(self, tier: str, prompt: str, max_tokens: int, temperature: float) -> str:
        tier_config = self._tier_config[tier]
        self._ensure_service_ready(tier)
        payload = {
            "model": tier_config["model_name"],
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": TOP_P,
        }
        try:
            response = requests.post(
                tier_config["api_url"],
                headers=self.headers,
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["text"].strip()
        except requests.exceptions.Timeout:
            return "[ERROR: Request timeout]"
        except Exception as error:
            return f"[ERROR: {error}]"

    def _ensure_service_ready(self, tier: str) -> None:
        with self._service_check_lock:
            if tier in self._checked_tiers:
                return
            tier_config = self._tier_config[tier]
            response = requests.get(tier_config["models_url"], timeout=5)
            response.raise_for_status()
            self._checked_tiers.add(tier)

    def _extract_final_answer(self, raw_text: str) -> str:
        matches = re.findall(r"final answer\s*:\s*(.*)", raw_text, re.IGNORECASE | re.DOTALL)
        if matches:
            return matches[-1].strip()
        return raw_text.strip()

    def _normalize_prediction(
        self,
        expected_output_format: str,
        candidate_text: str,
    ) -> Tuple[bool, str, Optional[Any], str]:
        cleaned = candidate_text.strip()
        if expected_output_format == "text_answer":
            if not cleaned or cleaned.startswith("[ERROR:"):
                return False, cleaned, None, "empty_or_error_text"
            return True, cleaned, None, ""

        json_payload = self._extract_json_payload(cleaned)
        if not json_payload:
            return False, cleaned, None, "json_payload_not_found"

        try:
            parsed = json.loads(json_payload)
        except json.JSONDecodeError as error:
            return False, cleaned, None, f"json_decode_error:{error}"

        normalized = json.dumps(parsed, ensure_ascii=False, sort_keys=True)
        return True, normalized, parsed, ""

    def _extract_json_payload(self, text: str) -> Optional[str]:
        fenced_match = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
        if fenced_match:
            return fenced_match.group(1).strip()

        object_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if object_match:
            return object_match.group(1).strip()

        array_match = re.search(r"(\[.*\])", text, re.DOTALL)
        if array_match:
            return array_match.group(1).strip()

        return None

    def _parse_self_eval_label(self, raw_output: str) -> Tuple[str, bool]:
        normalized = raw_output.lower()
        found_labels = []
        for label in re.findall(r"\b(confident|uncertain|incorrect)\b", normalized):
            if label not in found_labels:
                found_labels.append(label)

        if len(found_labels) == 1:
            return found_labels[0], True
        if len(found_labels) > 1:
            return "uncertain", False
        return "uncertain", False

    def _build_result(
        self,
        system_name: str,
        route: str,
        route_reason: str,
        final_stage: StageResult,
        latency_seconds: float,
        stages: Dict[str, Dict[str, Any]],
        accepted_by_1b: Optional[bool],
        seven_b_refine_invoked: bool,
        self_eval: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "system_name": system_name,
            "route": route,
            "route_reason": route_reason,
            "prediction": final_stage.final_text,
            "format_valid": final_stage.format_valid,
            "latency_seconds": latency_seconds,
            "raw_model_outputs": stages,
            "prompt_templates": [stage["prompt_template"] for stage in stages.values()],
            "final_stage": final_stage.to_dict(),
            "accepted_by_1b": accepted_by_1b,
            "seven_b_refine_invoked": seven_b_refine_invoked,
            "self_eval": self_eval,
        }


if __name__ == "__main__":
    from data_loader import DataItem

    sample = DataItem(
        sample_id="demo",
        task_key="Q&A",
        task_type="question_answering",
        task_family="answering",
        expected_output_format="text_answer",
        prompt="1+1等于多少？",
        question="1+1等于多少？",
        ground_truth="2",
        subject="数学",
        education_level="小学",
        question_type="单选题",
    )

    engine = InferenceEngine()
    print(engine.run_system("rule_v2", sample))
