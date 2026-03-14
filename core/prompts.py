"""
Shared prompt templates for offline experiments and the legacy API surface.
"""
from dataclasses import dataclass
from typing import Dict, Tuple


# ---------------------------------------------------------------------------
# Legacy API/system prompts kept for compatibility with the unfinished API path
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_BASE = """你是盘古教育助手，一个专业的教育辅导AI，基于华为盘古Embedded模型。"""

SYSTEM_PROMPT_WITH_USER = """你是盘古教育助手，一个专注于个性化教学与严谨推理的教育AI。

{user_context}

{dynamic_memory}

## 当前任务
- 任务类型：{task_type}
- 学科：{subject}

## 对话历史
{history}
"""


def build_system_prompt(
    user_context: str = "",
    dynamic_memory: str = "",
    task_type: str = "",
    subject: str = "",
    history: str = "",
) -> str:
    if not user_context and not history and not dynamic_memory:
        return SYSTEM_PROMPT_BASE
    return SYSTEM_PROMPT_WITH_USER.format(
        user_context=user_context or "无基础用户信息",
        dynamic_memory=dynamic_memory or "",
        task_type=task_type or "通用问答",
        subject=subject or "通用",
        history=history or "无历史对话",
    )


# ---------------------------------------------------------------------------
# Offline experiment prompt manager
# ---------------------------------------------------------------------------

EXPLANATION_STYLE_LABELS = {
    "zh": {"brief": "简洁", "detailed": "详细"},
    "en": {"brief": "brief", "detailed": "detailed"},
}

OUTPUT_FORMAT_INSTRUCTIONS = {
    "text_answer": {
        "zh": "最终输出使用纯文本，不要输出 JSON。",
        "en": "Return the final answer as plain text. Do not output JSON.",
    },
    "json_score_feedback": {
        "zh": "Final Answer 中只输出合法 JSON，对应键为 score, score_detail, personalized_feedback。",
        "en": "In Final Answer, output valid JSON only with keys score, score_detail, personalized_feedback.",
    },
    "json_correction": {
        "zh": "Final Answer 中只输出合法 JSON，对应键为 corrected_answer, correction_explanation。",
        "en": "In Final Answer, output valid JSON only with keys corrected_answer, correction_explanation.",
    },
    "json_guidance": {
        "zh": "Final Answer 中只输出合法 JSON，对应键为 guidance。",
        "en": "In Final Answer, output valid JSON only with key guidance.",
    },
    "json_learning_plan": {
        "zh": "Final Answer 中只输出合法 JSON，对应键为 learning_path_planning, personalized_recommendations。",
        "en": "In Final Answer, output valid JSON only with keys learning_path_planning, personalized_recommendations.",
    },
    "json_personalized_learning_content": {
        "zh": "Final Answer 中只输出合法 JSON，对应键为 personalized_learning_content。",
        "en": "In Final Answer, output valid JSON only with key personalized_learning_content.",
    },
    "json_question_bundle": {
        "zh": "Final Answer 中只输出合法 JSON，对应键为 question, guidance, answer。",
        "en": "In Final Answer, output valid JSON only with keys question, guidance, answer.",
    },
    "json_teaching_materials": {
        "zh": "Final Answer 中只输出合法 JSON，对应键为 teaching_materials。",
        "en": "In Final Answer, output valid JSON only with key teaching_materials.",
    },
    "json_emotional_support": {
        "zh": "Final Answer 中只输出合法 JSON，对应键为 emotional_state_analysis, comfort_and_advice。",
        "en": "In Final Answer, output valid JSON only with keys emotional_state_analysis, comfort_and_advice.",
    },
}


@dataclass(frozen=True)
class TaskPromptSet:
    fast_zh: str
    slow_zh: str
    fast_en: str
    slow_en: str


TASK_PROMPTS = {
    "question_answering": TaskPromptSet(
        fast_zh=(
            "你是一名教育问答助手。请以{explanation_level_label}方式直接回答。\n\n"
            "任务输入:\n{task_input}\n\n输出要求:\n{output_instruction}"
        ),
        slow_zh=(
            "你是一名教育问答助手。请先逐步分析，再给出最终答案。分析应准确、教学友好。\n\n"
            "任务输入:\n{task_input}\n\n"
            "请使用以下格式:\nAnalysis:\n<逐步推理>\nFinal Answer:\n<最终答案>\n\n"
            "输出要求:\n{output_instruction}"
        ),
        fast_en=(
            "You are an educational QA assistant. Answer directly in a {explanation_level_label} style.\n\n"
            "Task Input:\n{task_input}\n\nOutput Requirements:\n{output_instruction}"
        ),
        slow_en=(
            "You are an educational QA assistant. Analyze step by step before giving the final answer.\n\n"
            "Task Input:\n{task_input}\n\n"
            "Use this format:\nAnalysis:\n<step-by-step reasoning>\nFinal Answer:\n<final answer>\n\n"
            "Output Requirements:\n{output_instruction}"
        ),
    ),
    "automatic_grading": TaskPromptSet(
        fast_zh=(
            "你是一名教育评分助手。请根据题目与学生答案给出快速评分结果。\n\n"
            "任务输入:\n{task_input}\n\n输出要求:\n{output_instruction}"
        ),
        slow_zh=(
            "你是一名教育评分助手。请先分析学生答案，再给出最终评分结果。\n\n"
            "任务输入:\n{task_input}\n\n"
            "请使用以下格式:\nAnalysis:\n<评分分析>\nFinal Answer:\n<最终 JSON>\n\n"
            "输出要求:\n{output_instruction}"
        ),
        fast_en=(
            "You are an educational grading assistant. Provide a quick grading result from the question and student answer.\n\n"
            "Task Input:\n{task_input}\n\nOutput Requirements:\n{output_instruction}"
        ),
        slow_en=(
            "You are an educational grading assistant. Analyze the student's answer before returning the final grading result.\n\n"
            "Task Input:\n{task_input}\n\n"
            "Use this format:\nAnalysis:\n<grading analysis>\nFinal Answer:\n<final JSON>\n\n"
            "Output Requirements:\n{output_instruction}"
        ),
    ),
    "error_correction": TaskPromptSet(
        fast_zh=(
            "你是一名教育纠错助手。请快速指出错误并给出纠正结果。\n\n"
            "任务输入:\n{task_input}\n\n输出要求:\n{output_instruction}"
        ),
        slow_zh=(
            "你是一名教育纠错助手。请先分析原答案的问题，再给出最终纠错结果。\n\n"
            "任务输入:\n{task_input}\n\n"
            "请使用以下格式:\nAnalysis:\n<错误分析>\nFinal Answer:\n<最终 JSON>\n\n"
            "输出要求:\n{output_instruction}"
        ),
        fast_en=(
            "You are an educational correction assistant. Quickly identify the error and return the correction.\n\n"
            "Task Input:\n{task_input}\n\nOutput Requirements:\n{output_instruction}"
        ),
        slow_en=(
            "You are an educational correction assistant. Analyze the original answer before returning the final correction.\n\n"
            "Task Input:\n{task_input}\n\n"
            "Use this format:\nAnalysis:\n<error analysis>\nFinal Answer:\n<final JSON>\n\n"
            "Output Requirements:\n{output_instruction}"
        ),
    ),
    "idea_prompting": TaskPromptSet(
        fast_zh=(
            "你是一名教育思路提示助手。请给出可执行的简洁解题思路。\n\n"
            "任务输入:\n{task_input}\n\n输出要求:\n{output_instruction}"
        ),
        slow_zh=(
            "你是一名教育思路提示助手。请先分析问题，再给出分步骤的教学思路。\n\n"
            "任务输入:\n{task_input}\n\n"
            "请使用以下格式:\nAnalysis:\n<问题分析>\nFinal Answer:\n<最终 JSON>\n\n"
            "输出要求:\n{output_instruction}"
        ),
        fast_en=(
            "You are an educational guidance assistant. Provide a concise, actionable solution approach.\n\n"
            "Task Input:\n{task_input}\n\nOutput Requirements:\n{output_instruction}"
        ),
        slow_en=(
            "You are an educational guidance assistant. Analyze the problem before returning a structured teaching approach.\n\n"
            "Task Input:\n{task_input}\n\n"
            "Use this format:\nAnalysis:\n<problem analysis>\nFinal Answer:\n<final JSON>\n\n"
            "Output Requirements:\n{output_instruction}"
        ),
    ),
    "personalized_content": TaskPromptSet(
        fast_zh=(
            "你是一名个性化学习规划助手。请根据学生画像给出紧凑的学习规划建议。\n\n"
            "任务输入:\n{task_input}\n\n输出要求:\n{output_instruction}"
        ),
        slow_zh=(
            "你是一名个性化学习规划助手。请先分析学生画像，再给出完整的学习路径与个性化建议。\n\n"
            "任务输入:\n{task_input}\n\n"
            "请使用以下格式:\nAnalysis:\n<学生画像分析>\nFinal Answer:\n<最终 JSON>\n\n"
            "输出要求:\n{output_instruction}"
        ),
        fast_en=(
            "You are a personalized learning planning assistant. Provide a compact plan from the student profile.\n\n"
            "Task Input:\n{task_input}\n\nOutput Requirements:\n{output_instruction}"
        ),
        slow_en=(
            "You are a personalized learning planning assistant. Analyze the student profile before returning a full plan and recommendations.\n\n"
            "Task Input:\n{task_input}\n\n"
            "Use this format:\nAnalysis:\n<profile analysis>\nFinal Answer:\n<final JSON>\n\n"
            "Output Requirements:\n{output_instruction}"
        ),
    ),
    "personalized_learning": TaskPromptSet(
        fast_zh=(
            "你是一名个性化学习内容助手。请根据学生画像快速生成学习内容或任务。\n\n"
            "任务输入:\n{task_input}\n\n输出要求:\n{output_instruction}"
        ),
        slow_zh=(
            "你是一名个性化学习内容助手。请先分析学生画像，再给出适配的学习内容或任务。\n\n"
            "任务输入:\n{task_input}\n\n"
            "请使用以下格式:\nAnalysis:\n<学生画像分析>\nFinal Answer:\n<最终 JSON>\n\n"
            "输出要求:\n{output_instruction}"
        ),
        fast_en=(
            "You are a personalized learning content assistant. Quickly generate learning content or tasks from the student profile.\n\n"
            "Task Input:\n{task_input}\n\nOutput Requirements:\n{output_instruction}"
        ),
        slow_en=(
            "You are a personalized learning content assistant. Analyze the student profile before returning tailored content or tasks.\n\n"
            "Task Input:\n{task_input}\n\n"
            "Use this format:\nAnalysis:\n<profile analysis>\nFinal Answer:\n<final JSON>\n\n"
            "Output Requirements:\n{output_instruction}"
        ),
    ),
    "question_generation": TaskPromptSet(
        fast_zh=(
            "你是一名教育题目生成助手。请根据结构化条件快速生成题目与解题支持信息。\n\n"
            "任务输入:\n{task_input}\n\n输出要求:\n{output_instruction}"
        ),
        slow_zh=(
            "你是一名教育题目生成助手。请先分析知识点与教育层级，再生成题目、思路和答案。\n\n"
            "任务输入:\n{task_input}\n\n"
            "请使用以下格式:\nAnalysis:\n<生成分析>\nFinal Answer:\n<最终 JSON>\n\n"
            "输出要求:\n{output_instruction}"
        ),
        fast_en=(
            "You are an educational question generation assistant. Quickly generate a question bundle from the structured constraints.\n\n"
            "Task Input:\n{task_input}\n\nOutput Requirements:\n{output_instruction}"
        ),
        slow_en=(
            "You are an educational question generation assistant. Analyze the knowledge point and grade level before generating the question bundle.\n\n"
            "Task Input:\n{task_input}\n\n"
            "Use this format:\nAnalysis:\n<generation analysis>\nFinal Answer:\n<final JSON>\n\n"
            "Output Requirements:\n{output_instruction}"
        ),
    ),
    "teaching_material": TaskPromptSet(
        fast_zh=(
            "你是一名教学素材生成助手。请快速生成教学素材框架。\n\n"
            "任务输入:\n{task_input}\n\n输出要求:\n{output_instruction}"
        ),
        slow_zh=(
            "你是一名教学素材生成助手。请先分析教学目标与知识点，再给出完整教学素材。\n\n"
            "任务输入:\n{task_input}\n\n"
            "请使用以下格式:\nAnalysis:\n<教学设计分析>\nFinal Answer:\n<最终 JSON>\n\n"
            "输出要求:\n{output_instruction}"
        ),
        fast_en=(
            "You are a teaching materials generation assistant. Quickly generate a teaching materials outline.\n\n"
            "Task Input:\n{task_input}\n\nOutput Requirements:\n{output_instruction}"
        ),
        slow_en=(
            "You are a teaching materials generation assistant. Analyze the teaching objective and knowledge point before returning the final teaching materials.\n\n"
            "Task Input:\n{task_input}\n\n"
            "Use this format:\nAnalysis:\n<teaching design analysis>\nFinal Answer:\n<final JSON>\n\n"
            "Output Requirements:\n{output_instruction}"
        ),
    ),
    "emotional_support": TaskPromptSet(
        fast_zh=(
            "你是一名教育情绪支持助手。请根据学生对话快速分析情绪状态并提供安慰建议。\n\n"
            "任务输入:\n{task_input}\n\n输出要求:\n{output_instruction}"
        ),
        slow_zh=(
            "你是一名教育情绪支持助手。请先分析学生情绪与触发因素，再给出支持建议。\n\n"
            "任务输入:\n{task_input}\n\n"
            "请使用以下格式:\nAnalysis:\n<情绪分析>\nFinal Answer:\n<最终 JSON>\n\n"
            "输出要求:\n{output_instruction}"
        ),
        fast_en=(
            "You are an educational emotional-support assistant. Quickly analyze the student's emotional state and provide comfort.\n\n"
            "Task Input:\n{task_input}\n\nOutput Requirements:\n{output_instruction}"
        ),
        slow_en=(
            "You are an educational emotional-support assistant. Analyze the student's emotional state and triggers before returning support advice.\n\n"
            "Task Input:\n{task_input}\n\n"
            "Use this format:\nAnalysis:\n<emotional analysis>\nFinal Answer:\n<final JSON>\n\n"
            "Output Requirements:\n{output_instruction}"
        ),
    ),
}

SELF_EVAL_PROMPT_ZH = """你是一名严格的教育答案审核助手。

原始任务:
{question}

候选回答:
{candidate_answer}

请判断该回答是否足够完整、正确且可信。
你必须只使用以下标签之一:
- confident
- uncertain
- incorrect

输出格式:
Label: <confident|uncertain|incorrect>
Reason: <一句简短理由>
"""

SELF_EVAL_PROMPT_EN = """You are a strict educational answer reviewer.

Original task:
{question}

Candidate answer:
{candidate_answer}

Judge whether the answer is sufficiently complete, correct, and trustworthy.
You must use exactly one label from:
- confident
- uncertain
- incorrect

Output format:
Label: <confident|uncertain|incorrect>
Reason: <one short reason>
"""

REFINE_FROM_DRAFT_PROMPT_ZH = """你是一名教育任务助手。下面包含原始任务与一个低成本草稿答案。
请先分析草稿是否缺失、错误或格式不合规，再给出更可靠的最终答案。

原始任务:
{question}

草稿答案:
{draft_answer}

请使用以下格式:
Analysis:
<问题与草稿分析>
Final Answer:
<最终答案>

输出要求:
{output_instruction}
"""

REFINE_FROM_DRAFT_PROMPT_EN = """You are an educational task assistant. The input below contains the original task and a low-cost draft answer.
Analyze whether the draft is incomplete, incorrect, or badly formatted, then provide a more reliable final answer.

Original task:
{question}

Draft answer:
{draft_answer}

Use this format:
Analysis:
<analysis of the task and draft>
Final Answer:
<final answer>

Output Requirements:
{output_instruction}
"""

GPT5_JUDGE_PROMPT_ZH = """你是一位顶尖的教育专家和语言模型评估者。请对以下模型生成的回答进行多维度评分。

【评估背景】：
- 场景类型：{task_type}
- 题目内容：{question}
- 标准答案（仅供参考）：{ground_truth}

【待评估回答】：
{prediction}

【评分维度 (1-10分)】：
1. 场景自适应
2. 事实与逻辑准确性
3. 教育应用价值

请以 JSON 格式输出各维度分数、总分 Average 和简短理由 Reason。
"""


def get_task_prompt(task_type: str, mode: str, lang: str = "zh") -> str:
    prompt_set = TASK_PROMPTS[task_type]
    key = f"{mode}_{lang}"
    return getattr(prompt_set, key)


def get_output_instruction(expected_output_format: str, lang: str = "zh") -> str:
    return OUTPUT_FORMAT_INSTRUCTIONS[expected_output_format][lang]


def render_task_prompt(data_item, mode: str, explanation_level: str = "detailed") -> Tuple[str, str]:
    lang = data_item.lang
    template = get_task_prompt(data_item.task_type, mode, lang)
    prompt_text = template.format(
        explanation_level_label=EXPLANATION_STYLE_LABELS[lang].get(explanation_level, explanation_level),
        task_input=data_item.prompt,
        output_instruction=get_output_instruction(data_item.expected_output_format, lang),
    )
    template_name = f"{data_item.task_type}:{mode}:{lang}"
    return prompt_text, template_name


def render_self_eval_prompt(question: str, candidate_answer: str, lang: str = "zh") -> str:
    template = SELF_EVAL_PROMPT_ZH if lang == "zh" else SELF_EVAL_PROMPT_EN
    return template.format(question=question, candidate_answer=candidate_answer)


def render_refine_prompt(data_item, draft_answer: str) -> Tuple[str, str]:
    lang = data_item.lang
    template = REFINE_FROM_DRAFT_PROMPT_ZH if lang == "zh" else REFINE_FROM_DRAFT_PROMPT_EN
    prompt_text = template.format(
        question=data_item.prompt,
        draft_answer=draft_answer,
        output_instruction=get_output_instruction(data_item.expected_output_format, lang),
    )
    template_name = f"{data_item.task_type}:refine_from_draft:{lang}"
    return prompt_text, template_name
