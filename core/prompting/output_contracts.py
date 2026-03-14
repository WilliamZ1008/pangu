"""
Task-level output contracts used by prompts and validation.
"""
from typing import Dict


OUTPUT_CONTRACTS: Dict[str, Dict[str, object]] = {
    "Q&A": {
        "type": "json",
        "required_keys": ["direct_answer", "short_explanation"],
        "instruction_zh": "输出合法 JSON，键为 direct_answer, short_explanation。",
        "instruction_en": "Return valid JSON with keys direct_answer and short_explanation.",
    },
    "AG": {
        "type": "json",
        "required_keys": ["score", "evidence", "feedback"],
        "instruction_zh": "输出合法 JSON，键为 score, evidence, feedback。",
        "instruction_en": "Return valid JSON with keys score, evidence, feedback.",
    },
    "EC": {
        "type": "json",
        "required_keys": ["error_list", "corrected_answer", "explanation"],
        "instruction_zh": "输出合法 JSON，键为 error_list, corrected_answer, explanation。",
        "instruction_en": "Return valid JSON with keys error_list, corrected_answer, explanation.",
    },
    "IP": {
        "type": "json",
        "required_keys": ["hints"],
        "instruction_zh": "输出合法 JSON，键为 hints。hints 应为分步骤提示，尽量避免直接给出完整答案。",
        "instruction_en": "Return valid JSON with key hints. Hints should be structured and avoid leaking the full answer when possible.",
    },
    "PCC": {
        "type": "json",
        "required_keys": ["learning_path", "personalized_suggestions"],
        "instruction_zh": "输出合法 JSON，键为 learning_path, personalized_suggestions。",
        "instruction_en": "Return valid JSON with keys learning_path and personalized_suggestions.",
    },
    "PLS": {
        "type": "json",
        "required_keys": ["personalized_learning_content"],
        "instruction_zh": "输出合法 JSON，键为 personalized_learning_content。",
        "instruction_en": "Return valid JSON with key personalized_learning_content.",
    },
    "QG": {
        "type": "json",
        "required_keys": ["generated_question", "answer", "rationale"],
        "instruction_zh": "输出合法 JSON，键为 generated_question, answer, rationale。",
        "instruction_en": "Return valid JSON with keys generated_question, answer, rationale.",
    },
    "TMG": {
        "type": "json",
        "required_keys": ["objectives", "key_points", "classroom_activity_design"],
        "instruction_zh": "输出合法 JSON，键为 objectives, key_points, classroom_activity_design。",
        "instruction_en": "Return valid JSON with keys objectives, key_points, classroom_activity_design.",
    },
}


def get_output_contract(task_key: str) -> Dict[str, object]:
    if task_key not in OUTPUT_CONTRACTS:
        raise KeyError(f"Unsupported task key for output contract: {task_key}")
    return OUTPUT_CONTRACTS[task_key]
