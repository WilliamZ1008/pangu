"""
Prompt assembly for the final offline experiment system.
"""
from core.prompting.output_contracts import get_output_contract
from core.prompting.task_templates import TASK_TEMPLATE_GROUPS


class PromptManager:
    """Central prompt assembler used by the inference engine."""

    def build_1b_router_prompt(self, sample) -> tuple[str, str]:
        contract = get_output_contract(sample.task_key)
        lang = sample.lang
        template = TASK_TEMPLATE_GROUPS["fast_router"][lang]
        prompt = template.format(
            prompt_text=sample.prompt_text,
            task_key=sample.task_key,
            task_type=sample.task_type,
            task_family=sample.task_family,
            subject=sample.subject or "unknown",
            education_level=sample.education_level or "unknown",
            expected_output_format=sample.expected_output_format,
            output_instruction=contract[f"instruction_{lang}"],
        )
        return prompt, f"fast_router:{lang}"

    def build_7b_specialist_prompt(self, sample, router_output, specialist_name: str) -> tuple[str, str]:
        contract = get_output_contract(sample.task_key)
        lang = sample.lang
        template_name = f"specialist_{specialist_name}"
        template = TASK_TEMPLATE_GROUPS[template_name][lang]
        prompt = template.format(
            prompt_text=sample.prompt_text,
            predicted_task_family=router_output.predicted_task_family,
            predicted_subject=router_output.predicted_subject,
            confidence_label=router_output.confidence_label,
            confidence_score=router_output.confidence_score,
            tool_hint=router_output.tool_hint,
            draft_answer=router_output.draft_answer,
            output_instruction=contract[f"instruction_{lang}"],
        )
        return prompt, f"{template_name}:{lang}"

    def build_format_repair_prompt(self, sample, draft_output) -> tuple[str, str]:
        contract = get_output_contract(sample.task_key)
        lang = sample.lang
        template = TASK_TEMPLATE_GROUPS["format_repair"][lang]
        prompt = template.format(
            prompt_text=sample.prompt_text,
            output_instruction=contract[f"instruction_{lang}"],
            draft_output=draft_output,
        )
        return prompt, f"format_repair:{lang}"

    def build_rule_baseline_prompt(self, sample, mode: str) -> tuple[str, str]:
        contract = get_output_contract(sample.task_key)
        lang = sample.lang
        if mode == "fast":
            group = "rule_baseline_fast"
        else:
            group = "rule_baseline_slow"
        template = TASK_TEMPLATE_GROUPS[group][lang]
        prompt = template.format(
            prompt_text=sample.prompt_text,
            output_instruction=contract[f"instruction_{lang}"],
        )
        return prompt, f"{group}:{lang}"

    def build_self_check_prompt(self, sample, candidate_answer: str) -> tuple[str, str]:
        lang = sample.lang
        template = TASK_TEMPLATE_GROUPS["self_check"][lang]
        prompt = template.format(
            prompt_text=sample.prompt_text,
            candidate_answer=candidate_answer,
        )
        return prompt, f"self_check:{lang}"
