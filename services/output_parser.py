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

    ROUTER_PLACEHOLDERS = {
        "reasoning | assessment | planning",
        "string",
        "字符串",
        "draft answer",
        "tool hint",
        "additional notes if needed",
    }

    GENERIC_PLACEHOLDER_PATTERNS = (
        "draft answer",
        "your draft answer",
        "your answer here",
        "[your answer]",
        "placeholder",
        "tries to satisfy the target contract",
    )

    SCAFFOLD_PATTERNS = (
        "predicted_task_",
        "format_signals",
        "output the json",
        "let's think step by step",
        "understanding the task",
        "final json output",
        "output format",
    )

    def parse_router_output(self, text: str) -> RouterOutput:
        payloads = self._extract_json_payloads(text)
        if not payloads:
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

        parsed_candidates = []
        for payload in payloads:
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                parsed_candidates.append(parsed)

        if not parsed_candidates:
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

        best_parsed = max(
            enumerate(parsed_candidates),
            key=lambda item: (self._score_router_candidate(item[1]), item[0]),
        )[1]
        recovered = self._recover_router_output(text)
        parsed_score = self._score_router_candidate(best_parsed)
        recovered_score = self._score_router_candidate(recovered) if recovered is not None else -1

        chosen = recovered if recovered is not None and recovered_score > parsed_score else best_parsed
        parse_ok = self._score_router_candidate(chosen) >= 3
        return self._router_output_from_dict(chosen, text, parse_ok=parse_ok)

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
                    salvaged = self._salvage_freeform_prediction(sample, prediction)
                    if salvaged is not None:
                        return salvaged
                    return {
                        "normalized_prediction": prediction,
                        "errors": ["json_parse_failed"],
                    }
            else:
                salvaged = self._salvage_non_dict_payload(sample, payload)
                if salvaged is not None:
                    return salvaged
            if not isinstance(payload, dict):
                salvaged = self._salvage_non_dict_payload(sample, payload)
                if salvaged is not None:
                    return salvaged
                return {
                    "normalized_prediction": prediction,
                    "errors": ["json_root_not_object"],
                }

            normalized = self._normalize_task_payload(sample.task_key, payload)
            missing = self._missing_required_keys(contract["required_keys"], normalized)
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
        payloads = self._extract_json_payloads(text)
        if payloads:
            return payloads[-1]
        return None

    def _salvage_freeform_prediction(self, sample, prediction) -> dict | None:
        if not isinstance(prediction, str):
            return None
        text = prediction.strip()
        if not self._is_meaningful_output(text):
            return None

        task_key = sample.task_key
        if task_key == "Q&A":
            if self._looks_like_scaffold(text):
                return None
            direct_answer = self._extract_direct_answer(text)
            if not self._is_meaningful_value(direct_answer):
                return None
            explanation = self._build_short_explanation(text, direct_answer)
            return {
                "normalized_prediction": {
                    "direct_answer": direct_answer,
                    "short_explanation": explanation,
                },
                "errors": [],
            }

        if task_key == "EC":
            if self._looks_like_scaffold(text):
                return None
            corrected_answer = self._extract_corrected_answer(text)
            if not self._is_meaningful_output(corrected_answer):
                return None
            return {
                "normalized_prediction": {
                    "error_list": [],
                    "corrected_answer": corrected_answer,
                    "explanation": self._build_rewrite_explanation(text, corrected_answer),
                },
                "errors": [],
            }

        if task_key == "IP":
            hint_source = self._extract_embedded_field(text, "draft_answer") or text
            hints = self._coerce_hints(hint_source)
            if not self._is_meaningful_value(hints):
                return None
            return {
                "normalized_prediction": {"hints": hints},
                "errors": [],
            }

        if task_key == "PLS":
            content = self._extract_embedded_field(text, "draft_answer") or text
            if not self._is_meaningful_output(content):
                return None
            return {
                "normalized_prediction": {"personalized_learning_content": content},
                "errors": [],
            }

        if task_key == "AG":
            score_source = self._extract_embedded_field(text, "draft_answer") or text
            score = self._extract_score_value(score_source)
            if not self._is_meaningful_value(score):
                return None
            return {
                "normalized_prediction": {
                    "score": score,
                    "evidence": score_source,
                    "feedback": score_source,
                },
                "errors": [],
            }

        return None

    def _salvage_non_dict_payload(self, sample, payload) -> dict | None:
        if sample.task_key == "IP" and isinstance(payload, list) and payload:
            return {
                "normalized_prediction": {"hints": payload},
                "errors": [],
            }
        if sample.task_key == "PLS" and isinstance(payload, (list, dict)) and payload:
            return {
                "normalized_prediction": {"personalized_learning_content": payload},
                "errors": [],
            }
        return None

    def _missing_required_keys(self, required_keys: list[str], payload: Dict[str, Any]) -> list[str]:
        return [key for key in required_keys if self._is_missing_required_value(key, payload.get(key))]

    def _is_missing_required_value(self, key: str, value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return not self._is_meaningful_output(value)
        if isinstance(value, list):
            if key == "error_list":
                return False
            return not value
        if isinstance(value, dict):
            return not value
        return False

    def _is_meaningful_value(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return self._is_meaningful_output(value)
        if isinstance(value, (list, dict, tuple, set)):
            return len(value) > 0
        return True

    def _is_meaningful_output(self, text: str) -> bool:
        normalized = str(text).strip()
        if not normalized:
            return False
        lowered = normalized.lower()
        if lowered in self.ROUTER_PLACEHOLDERS:
            return False
        if any(pattern in lowered for pattern in self.GENERIC_PLACEHOLDER_PATTERNS):
            return False
        return True

    def _extract_direct_answer(self, text: str) -> Any:
        stripped = text.strip()
        candidate = (
            self._extract_embedded_field(stripped, "direct_answer")
            or self._extract_embedded_field(stripped, "draft_answer")
            or stripped
        )
        scaffold = self._looks_like_scaffold(stripped)
        option_text_match = re.match(r"^\s*([A-D])([\.\):])\s+(.+)$", candidate, re.IGNORECASE)
        if option_text_match:
            option_text = candidate.strip()
            if self._is_meaningful_output(option_text):
                return option_text
        choice_block = re.match(
            r"^\s*([A-D])(?:[\.\):]|$)(?:\s*[,/;，、]\s*([A-D])(?:[\.\):]|$))*",
            candidate,
            re.IGNORECASE,
        )
        if choice_block:
            labels = re.findall(r"([A-D])(?:[\.\):]|$)", choice_block.group(0), re.IGNORECASE)
            labels = [label.upper() for label in labels]
            if len(labels) > 1:
                return labels
            if labels:
                return labels[0]

        answer_phrase = re.search(
            r"(?:correct answer is|answer is|答案是|应选|选择|option)\s*([A-D])(?:[\.\):]|$)",
            candidate,
            re.IGNORECASE,
        )
        if answer_phrase:
            return answer_phrase.group(1).upper()

        simple_choices = re.findall(r"(?<![A-Za-z])([A-D])(?:[\.\):]|$)", candidate, re.IGNORECASE)
        if len(simple_choices) == 1 and len(candidate) <= 24:
            return simple_choices[0].upper()

        trailing_math = self._extract_rhs_tail(candidate)
        if trailing_math:
            return trailing_math

        predicate_tail = re.search(
            r"(?:is|are|was|were|equals|结果是|为)\s*([^\n。.!?]{1,80})$",
            candidate,
            re.IGNORECASE,
        )
        if predicate_tail:
            answer_candidate = predicate_tail.group(1).strip(" \"'`")
            if self._is_meaningful_output(answer_candidate):
                return answer_candidate

        if scaffold:
            return None

        first_line = candidate.splitlines()[0].strip()
        if len(candidate.splitlines()) <= 2 and len(first_line) <= 120 and self._is_meaningful_output(first_line):
            return first_line
        return None

    def _build_short_explanation(self, text: str, direct_answer: Any) -> str:
        stripped = text.strip()
        if isinstance(direct_answer, list):
            return stripped
        answer_text = str(direct_answer).strip()
        if stripped and stripped != answer_text:
            return stripped
        return f"Extracted direct answer: {answer_text}"

    def _extract_corrected_answer(self, text: str) -> str:
        stripped = text.strip()
        candidate = (
            self._extract_embedded_field(stripped, "corrected_answer")
            or self._extract_embedded_field(stripped, "draft_answer")
            or stripped
        )
        scaffold = self._looks_like_scaffold(stripped)
        if scaffold:
            return ""
        labeled = re.search(
            r"(?:corrected answer|correct answer|修正后答案|纠正后答案|答案)\s*[:：]\s*(.+)$",
            candidate,
            re.IGNORECASE | re.DOTALL,
        )
        if labeled:
            labeled_candidate = labeled.group(1).strip()
            if self._is_meaningful_output(labeled_candidate):
                return labeled_candidate

        rhs_tail = self._extract_rhs_tail(candidate)
        if rhs_tail:
            return rhs_tail

        first_line = candidate.splitlines()[0].strip()
        if len(candidate.splitlines()) <= 2 and len(first_line) <= 120 and self._is_meaningful_output(first_line):
            return first_line
        return ""

    def _build_rewrite_explanation(self, text: str, corrected_answer: str) -> str:
        stripped = text.strip()
        if stripped and stripped != corrected_answer:
            return stripped
        return f"Corrected answer extracted from 1B draft: {corrected_answer}"

    def _coerce_hints(self, text: str) -> Any:
        lines = []
        for raw_line in text.splitlines():
            cleaned = re.sub(r"^\s*(?:[-*•]|\d+[\.\)])\s*", "", raw_line).strip()
            if cleaned and self._is_meaningful_output(cleaned):
                lines.append(cleaned)
        if len(lines) >= 2:
            return lines
        if lines:
            return lines[0]
        return text.strip()

    def _extract_score_value(self, text: str) -> Any:
        score_label = re.search(
            r"(?:score|grade|评分)\s*[:：]?\s*([A-F]|[0-9]+(?:\.[0-9]+)?%?)",
            text,
            re.IGNORECASE,
        )
        if score_label:
            return score_label.group(1)

        numeric_only = re.fullmatch(r"\s*([A-F]|[0-9]+(?:\.[0-9]+)?%?)\s*", text, re.IGNORECASE)
        if numeric_only:
            return numeric_only.group(1)
        return None

    def _extract_rhs_tail(self, text: str) -> str | None:
        if "=" not in text:
            return None
        candidate = text.split("=")[-1].strip().strip("。.!? ")
        if candidate and len(candidate) <= 80 and self._is_meaningful_output(candidate):
            return candidate
        return None

    def _extract_embedded_field(self, text: str, field_name: str) -> str:
        values = re.findall(rf'"{field_name}"\s*:\s*"([^"]+)"', text, re.IGNORECASE)
        values.extend(re.findall(rf"{field_name}\s*[:：]\s*([^\n]+)", text, re.IGNORECASE))
        cleaned = []
        for value in values:
            candidate = value.strip().strip(",")
            if candidate and self._is_meaningful_output(candidate):
                cleaned.append(candidate)
        if not cleaned:
            return ""
        cleaned = sorted(cleaned, key=lambda value: (len(value), value))
        return cleaned[0]

    def _looks_like_scaffold(self, text: str) -> bool:
        lowered = text.lower()
        return any(pattern in lowered for pattern in self.SCAFFOLD_PATTERNS)

    def _extract_json_payloads(self, text: str) -> list[str]:
        payloads = []
        fenced_matches = re.findall(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
        payloads.extend(match.strip() for match in fenced_matches)
        if payloads:
            return payloads
        fenced = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
        if fenced:
            payloads.append(fenced.group(1).strip())
        object_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if object_match:
            payloads.append(object_match.group(1).strip())
        return payloads

    def _coerce_confidence(self, value: Any, label: str) -> float:
        try:
            numeric = float(value)
        except Exception:
            numeric = {"high": 0.85, "medium": 0.60, "low": 0.25}.get(label, 0.25)
        return max(0.0, min(1.0, numeric))

    def _router_output_from_dict(self, parsed: Dict[str, Any], text: str, *, parse_ok: bool) -> RouterOutput:
        raw_family = str(parsed.get("predicted_task_family", "")).strip().lower()
        family = self.ROUTER_FAMILY_ALIASES.get(raw_family, "reasoning")
        confidence_label = self.CONFIDENCE_ALIASES.get(
            str(parsed.get("confidence_label", "low")).strip().lower(),
            "low",
        )
        confidence_score = self._coerce_confidence(parsed.get("confidence_score", 0.0), confidence_label)
        format_signals = parsed.get("format_signals", {})
        if not isinstance(format_signals, dict):
            format_signals = {"contract_ok": False, "notes": [str(format_signals)]}
        notes = format_signals.get("notes", [])
        if isinstance(notes, str):
            notes = [notes]
        if not parse_ok:
            notes = list(notes) + ["router_placeholder_recovery"]
            format_signals = dict(format_signals)
            format_signals["contract_ok"] = False
            format_signals["notes"] = notes

        return RouterOutput(
            predicted_task_family=family,
            predicted_subject=str(parsed.get("predicted_subject", "")).strip(),
            draft_answer=parsed.get("draft_answer", ""),
            confidence_label=confidence_label,
            confidence_score=confidence_score,
            format_signals=format_signals,
            tool_hint=str(parsed.get("tool_hint", "")).strip(),
            raw_text=text,
            parse_ok=parse_ok,
        )

    def _score_router_candidate(self, parsed: Dict[str, Any]) -> int:
        score = 0
        family = str(parsed.get("predicted_task_family", "")).strip().lower()
        if family in self.ROUTER_FAMILY_ALIASES:
            score += 2
        if self._is_concrete_router_value(parsed.get("predicted_subject", "")):
            score += 1
        if self._is_concrete_router_value(parsed.get("draft_answer", ""), field_name="draft_answer"):
            score += 3
        confidence_label = str(parsed.get("confidence_label", "")).strip().lower()
        if confidence_label in self.CONFIDENCE_ALIASES:
            score += 1
        try:
            confidence_score = float(parsed.get("confidence_score", -1))
        except Exception:
            confidence_score = -1
        if 0.0 <= confidence_score <= 1.0:
            score += 1
        if self._is_concrete_router_value(parsed.get("tool_hint", "")):
            score += 1
        format_signals = parsed.get("format_signals", {})
        if isinstance(format_signals, dict):
            score += 1
        return score

    def _recover_router_output(self, text: str) -> Dict[str, Any] | None:
        family_candidates = re.findall(r'"predicted_task_family"\s*:\s*"([^"]+)"', text)
        subject_candidates = re.findall(r'"predicted_subject"\s*:\s*"([^"]+)"', text)
        draft_candidates = re.findall(r'"draft_answer"\s*:\s*"([^"]+)"', text)
        confidence_label_candidates = re.findall(r'"confidence_label"\s*:\s*"([^"]+)"', text)
        confidence_score_candidates = re.findall(r'"confidence_score"\s*:\s*([0-9]*\.?[0-9]+)', text)
        tool_hint_candidates = re.findall(r'"tool_hint"\s*:\s*"([^"]+)"', text)
        note_candidates = re.findall(r'"notes"\s*:\s*"([^"]+)"', text)
        contract_ok_candidates = re.findall(r'"contract_ok"\s*:\s*(true|false)', text, re.IGNORECASE)

        draft_answer = self._pick_best_router_value(draft_candidates, field_name="draft_answer")
        if not draft_answer:
            return None

        raw_family = self._pick_best_router_value(family_candidates)
        confidence_label_raw = self._pick_best_router_value(confidence_label_candidates)
        tool_hint = self._pick_best_router_value(tool_hint_candidates)
        note = self._pick_best_router_value(note_candidates)
        subject = self._pick_best_router_value(subject_candidates)

        if raw_family.lower() not in self.ROUTER_FAMILY_ALIASES:
            raw_family = "reasoning"
        confidence_label = self.CONFIDENCE_ALIASES.get(confidence_label_raw.lower(), "low")

        confidence_score = 0.0
        if confidence_score_candidates:
            try:
                confidence_score = float(confidence_score_candidates[-1])
            except Exception:
                confidence_score = 0.0

        contract_ok = False
        if contract_ok_candidates:
            contract_ok = contract_ok_candidates[-1].lower() == "true"

        return {
            "predicted_task_family": raw_family,
            "predicted_subject": subject,
            "draft_answer": draft_answer,
            "confidence_label": confidence_label,
            "confidence_score": confidence_score,
            "format_signals": {
                "contract_ok": contract_ok,
                "notes": [note] if note else [],
            },
            "tool_hint": tool_hint,
        }

    def _pick_best_router_value(self, values: list[str], field_name: str = "") -> str:
        cleaned = [value.strip() for value in values if value and value.strip()]
        concrete = [value for value in cleaned if self._is_concrete_router_value(value, field_name=field_name)]
        if not concrete:
            return cleaned[-1] if cleaned else ""
        if field_name == "draft_answer":
            concrete = sorted(concrete, key=lambda value: (len(value), value))
            return concrete[0]
        return concrete[-1]

    def _is_concrete_router_value(self, value: Any, field_name: str = "") -> bool:
        text = str(value).strip()
        if not text:
            return False
        if not self._is_meaningful_output(text):
            return False
        if "|" in text and field_name != "draft_answer":
            return False
        return True
