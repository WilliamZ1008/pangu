"""
Prompt template groups for router, specialists, repair, and self-check.
"""

FAST_ROUTER_TEMPLATE_ZH = """你是一个低成本教育任务路由器。请先理解任务，再输出一个 JSON 对象。

任务输入:
{prompt_text}

已知任务信息:
- task_key: {task_key}
- task_type: {task_type}
- task_family: {task_family}
- subject: {subject}
- education_level: {education_level}
- expected_output_format: {expected_output_format}

目标输出契约:
{output_instruction}

请只输出合法 JSON，字段必须包含:
- predicted_task_family: reasoning | assessment | planning
- predicted_subject: 字符串
- draft_answer: 你的草稿答案，必须尽量满足目标输出契约
- confidence_label: high | medium | low
- confidence_score: 0 到 1 之间的小数
- format_signals: 对象，至少包含 contract_ok 和 notes
- tool_hint: 简短字符串
"""


FAST_ROUTER_TEMPLATE_EN = """You are a low-cost educational task router. Understand the task and output one JSON object.

Task Input:
{prompt_text}

Known task metadata:
- task_key: {task_key}
- task_type: {task_type}
- task_family: {task_family}
- subject: {subject}
- education_level: {education_level}
- expected_output_format: {expected_output_format}

Target output contract:
{output_instruction}

Return valid JSON only with fields:
- predicted_task_family: reasoning | assessment | planning
- predicted_subject: string
- draft_answer: your draft answer that tries to satisfy the target contract
- confidence_label: high | medium | low
- confidence_score: decimal between 0 and 1
- format_signals: object with at least contract_ok and notes
- tool_hint: short string
"""


SPECIALIST_REASONING_TEMPLATE_ZH = """你是 7B reasoning specialist，负责高风险教育推理与纠错任务。

原始任务:
{prompt_text}

1B 路由摘要:
- predicted_task_family: {predicted_task_family}
- predicted_subject: {predicted_subject}
- confidence_label: {confidence_label}
- confidence_score: {confidence_score}
- tool_hint: {tool_hint}

1B 草稿:
{draft_answer}

请以推理专家身份改写并提升答案质量。
必须匹配以下输出契约:
{output_instruction}
"""


SPECIALIST_REASONING_TEMPLATE_EN = """You are the 7B reasoning specialist for high-risk educational reasoning and correction tasks.

Original task:
{prompt_text}

1B router summary:
- predicted_task_family: {predicted_task_family}
- predicted_subject: {predicted_subject}
- confidence_label: {confidence_label}
- confidence_score: {confidence_score}
- tool_hint: {tool_hint}

1B draft:
{draft_answer}

Rewrite and improve the answer as a reasoning specialist.
You must satisfy this output contract:
{output_instruction}
"""


SPECIALIST_ASSESSMENT_TEMPLATE_ZH = """你是 7B assessment specialist，负责教育评分与评价任务。

原始任务:
{prompt_text}

1B 草稿:
{draft_answer}

请聚焦评价标准、证据与反馈，输出更可靠的最终答案。
必须匹配以下输出契约:
{output_instruction}
"""


SPECIALIST_ASSESSMENT_TEMPLATE_EN = """You are the 7B assessment specialist for grading and evaluation tasks.

Original task:
{prompt_text}

1B draft:
{draft_answer}

Focus on rubric consistency, evidence, and feedback, then return a more reliable final answer.
You must satisfy this output contract:
{output_instruction}
"""


SPECIALIST_PLANNING_TEMPLATE_ZH = """你是 7B planning specialist，负责学习规划、内容生成与教学设计任务。

原始任务:
{prompt_text}

1B 草稿:
{draft_answer}

请补足结构、细节与教学实用性，输出更可靠的最终答案。
必须匹配以下输出契约:
{output_instruction}
"""


SPECIALIST_PLANNING_TEMPLATE_EN = """You are the 7B planning specialist for learning plans, content generation, and teaching design tasks.

Original task:
{prompt_text}

1B draft:
{draft_answer}

Improve the structure, detail, and pedagogical usefulness of the answer.
You must satisfy this output contract:
{output_instruction}
"""


FORMAT_REPAIR_TEMPLATE_ZH = """下面的模型输出不符合目标格式。请只修复格式，不要改变核心语义。

原始任务:
{prompt_text}

目标输出契约:
{output_instruction}

待修复输出:
{draft_output}

请只输出修复后的最终答案。
"""


FORMAT_REPAIR_TEMPLATE_EN = """The model output below does not satisfy the target format. Repair the format without changing the core meaning.

Original task:
{prompt_text}

Target output contract:
{output_instruction}

Output to repair:
{draft_output}

Return only the repaired final answer.
"""


SELF_CHECK_TEMPLATE_ZH = """你是一名教育答案自检助手。

原始任务:
{prompt_text}

候选答案:
{candidate_answer}

请判断该答案是否足够完整、正确且可信。
只允许输出以下 JSON:
{{
  "label": "confident | uncertain | incorrect",
  "reason": "一句简短理由"
}}
"""


SELF_CHECK_TEMPLATE_EN = """You are a self-check assistant for educational answers.

Original task:
{prompt_text}

Candidate answer:
{candidate_answer}

Judge whether the answer is sufficiently complete, correct, and trustworthy.
Return only this JSON:
{{
  "label": "confident | uncertain | incorrect",
  "reason": "one short reason"
}}
"""


RULE_BASELINE_FAST_ZH = """你是一名教育助手。请直接完成下面的任务，并尽量满足输出契约。

任务输入:
{prompt_text}

输出契约:
{output_instruction}
"""


RULE_BASELINE_FAST_EN = """You are an educational assistant. Complete the task directly and try to satisfy the output contract.

Task Input:
{prompt_text}

Output Contract:
{output_instruction}
"""


RULE_BASELINE_SLOW_ZH = """你是一名教育助手。请先分析，再给出最终答案，并满足输出契约。

任务输入:
{prompt_text}

请使用以下格式:
Analysis:
<逐步分析>
Final Answer:
<最终答案>

输出契约:
{output_instruction}
"""


RULE_BASELINE_SLOW_EN = """You are an educational assistant. Analyze first, then provide the final answer, and satisfy the output contract.

Task Input:
{prompt_text}

Use this format:
Analysis:
<step-by-step analysis>
Final Answer:
<final answer>

Output Contract:
{output_instruction}
"""


TASK_TEMPLATE_GROUPS = {
    "fast_router": {"zh": FAST_ROUTER_TEMPLATE_ZH, "en": FAST_ROUTER_TEMPLATE_EN},
    "specialist_reasoning": {"zh": SPECIALIST_REASONING_TEMPLATE_ZH, "en": SPECIALIST_REASONING_TEMPLATE_EN},
    "specialist_assessment": {"zh": SPECIALIST_ASSESSMENT_TEMPLATE_ZH, "en": SPECIALIST_ASSESSMENT_TEMPLATE_EN},
    "specialist_planning": {"zh": SPECIALIST_PLANNING_TEMPLATE_ZH, "en": SPECIALIST_PLANNING_TEMPLATE_EN},
    "format_repair": {"zh": FORMAT_REPAIR_TEMPLATE_ZH, "en": FORMAT_REPAIR_TEMPLATE_EN},
    "self_check": {"zh": SELF_CHECK_TEMPLATE_ZH, "en": SELF_CHECK_TEMPLATE_EN},
    "rule_baseline_fast": {"zh": RULE_BASELINE_FAST_ZH, "en": RULE_BASELINE_FAST_EN},
    "rule_baseline_slow": {"zh": RULE_BASELINE_SLOW_ZH, "en": RULE_BASELINE_SLOW_EN},
}
