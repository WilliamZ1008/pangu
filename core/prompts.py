"""
Compatibility prompts and shared evaluation prompt exports.

The final task prompts live under `core/prompting/`.
"""
from core.prompting.output_contracts import OUTPUT_CONTRACTS, get_output_contract
from core.prompting.prompt_manager import PromptManager


SYSTEM_PROMPT_BASE = """你是盘古教育助手，一个专业的教育辅导 AI。"""

SYSTEM_PROMPT_WITH_USER = """你是盘古教育助手，一个专注于个性化教学与严谨推理的教育 AI。

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


__all__ = [
    "PromptManager",
    "OUTPUT_CONTRACTS",
    "get_output_contract",
    "GPT5_JUDGE_PROMPT_ZH",
    "SYSTEM_PROMPT_BASE",
    "SYSTEM_PROMPT_WITH_USER",
    "build_system_prompt",
]
