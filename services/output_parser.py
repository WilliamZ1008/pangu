"""
Structured parsing and validation for router outputs and final predictions.
"""
import json
import re
from typing import Any, Dict, Tuple

from core.prompting.output_contracts import get_output_contract
from core.schemas import RouterOutput


class OutputParser:
    """Parse router JSON and normalize task-specific predictions."""

    ROUTER_FAMILY_ALIASES = {
        "reasoning": "reasoning",
        "assessment": "assessment",
        "planning": "planning",
        "grading": "assessment",
        "generation": "planning",
    }

    CONFIDENCE_ALIASES = {
        "high": "high",
        "medium": "medium",
        "low": "low",
        "confident": "high",
        "uncertain": "low",
        "incorrect": "low",
    }

    def parse_router_output(self, text: str) -> RouterOutput:
        payload = self._extract_json_payload(text)
        if not payload:
            return RouterOutput(
                predicted_task_family="reasoning",
                predicted_subject="",
                draft_answer=text.strip(),
                confidence_label="low",
                confidence_score=0.0,
                format_signals={"contract_ok": False, "notes": ["router_json_not_found"]},
                tool_hint="",
                raw_text=text,
                parse_ok=False,
            )

        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return RouterOutput(
                predicted_task_family="reasoning",
                predicted_subject="",
                draft_answer=text.strip(),
                confidence_label="low",
                confidence_score=0.0,
                format_signals={"contract_ok": False, "notes": ["router_json_decode_error"]},
                tool_hint="",
                raw_text=text,
                parse_ok=False,
            )

        family = self.ROUTER_FAMILY_ALIASES.get(str(parsed.get("predicted_task_family", "")).strip().lower(), "reasoning")
        confidence_label = self.CONFIDENCE_ALIASES.get(
            str(parsed.get("confidence_label", "low")).strip().lower(),
            "low",
        )
        confidence_score = self._coerce_confidence(parsed.get("confidence_score", 0.0), confidence_label)
        format_signals = parsed.get("format_signals", {})
        if not isinstance(format_signals, dict):
            format_signals = {"contract_ok": False, "notes": [str(format_signals)]}

        return RouterOutput(
            predicted_task_family=family,
            predicted_subject=str(parsed.get("predicted_subject", "")).strip(),
            draft_answer=parsed.get("draft_answer", ""),
            confidence_label=confidence_label,
            confidence_score=confidence_score,
            format_signals=format_signals,
            tool_hint=str(parsed.get("tool_hint", "")).strip(),
            raw_text=text,
            parse_ok=True,
        )

    def validate_prediction(self, sample, prediction) -> tuple[bool, dict]:
        normalized = self.repair_or_normalize(sample, prediction)
        errors = normalized.get("errors", [])
        return not errors, normalized

    def repair_or_normalize(self, sample, prediction) -> dict:
        contract = get_output_contract(sample.task_key)
        if contract["type"] == "json":
            payload = prediction
            if isinstance(payload, str):
                payload = self._extract_json_payload(payload) or payload
                try:
                    payload = json.loads(payload)
                except Exception:
                    return {
                        "normalized_prediction": prediction,
                        "errors": ["json_parse_failed"],
                    }
            if not isinstance(payload, dict):
                return {
                    "normalized_prediction": prediction,
                    "errors": ["json_root_not_object"],
                }

            normalized = self._normalize_task_payload(sample.task_key, payload)
            missing = [key for key in contract["required_keys"] if key not in normalized]
            return {
                "normalized_prediction": normalized,
                "errors": [f"missing_key:{key}" for key in missing],
            }

        text = prediction if isinstance(prediction, str) else str(prediction)
        text = text.strip()
        if not text:
            return {"normalized_prediction": text, "errors": ["empty_text"]}
        return {"normalized_prediction": text, "errors": []}

    def _normalize_task_payload(self, task_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if task_key == "AG":
            return {
                "score": payload.get("score", payload.get("评分")),
                "evidence": payload.get("evidence", payload.get("score_detail", payload.get("评分细节"))),
                "feedback": payload.get("feedback", payload.get("personalized_feedback", payload.get("个性化反馈"))),
            }
        if task_key == "EC":
            return {
                "error_list": payload.get("error_list", payload.get("errors", [])),
                "corrected_answer": payload.get("corrected_answer", payload.get("纠错后答案")),
                "explanation": payload.get("explanation", payload.get("correction_explanation", payload.get("纠错说明"))),
            }
        if task_key == "IP":
            hints = payload.get("hints", payload.get("guidance", payload.get("提供的思路")))
            return {"hints": hints}
        if task_key == "PCC":
            return {
                "learning_path": payload.get("learning_path", payload.get("learning_path_planning", payload.get("学习路径规划建议"))),
                "personalized_suggestions": payload.get(
                    "personalized_suggestions",
                    payload.get("personalized_recommendations", payload.get("个性化意见生成")),
                ),
            }
        if task_key == "PLS":
            return {
                "personalized_learning_content": payload.get(
                    "personalized_learning_content",
                    payload.get("个性化学习内容/任务"),
                )
            }
        if task_key == "QG":
            return {
                "generated_question": payload.get("generated_question", payload.get("question", payload.get("问题"))),
                "answer": payload.get("answer", payload.get("答案")),
                "rationale": payload.get("rationale", payload.get("guidance", payload.get("提供的思路"))),
            }
        if task_key == "TMG":
            teaching_materials = payload.get("teaching_materials", payload.get("教学素材"))
            if isinstance(teaching_materials, dict):
                return {
                    "objectives": teaching_materials.get("objectives", teaching_materials.get("教学目标")),
                    "key_points": teaching_materials.get("key_points", teaching_materials.get("重点难点")),
                    "classroom_activity_design": teaching_materials.get(
                        "classroom_activity_design",
                        teaching_materials.get("课堂活动设计"),
                    ),
                }
            return {
                "objectives": payload.get("objectives"),
                "key_points": payload.get("key_points"),
                "classroom_activity_design": payload.get("classroom_activity_design"),
            }
        if task_key == "Q&A":
            return {
                "direct_answer": payload.get("direct_answer", payload.get("answer", payload.get("答案"))),
                "short_explanation": payload.get(
                    "short_explanation",
                    payload.get("explanation", payload.get("reasoning", "")),
                ),
            }
        return payload

    def _extract_json_payload(self, text: str) -> str | None:
        fenced = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
        if fenced:
            return fenced.group(1).strip()
        object_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if object_match:
            return object_match.group(1).strip()
        return None

    def _coerce_confidence(self, value: Any, label: str) -> float:
        try:
            numeric = float(value)
        except Exception:
            numeric = {"high": 0.85, "medium": 0.60, "low": 0.25}.get(label, 0.25)
        return max(0.0, min(1.0, numeric))
