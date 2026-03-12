"""
JSON 修复链：当 NLU 输出的 payload 校验失败时，交给 LLM 做最小改动修复。

使用 LCEL：repair_prompt → LLM → 提取 JSON。
链在调用时构建，避免模块导入时就创建 LLM 实例。
"""

from __future__ import annotations

from langchain_core.runnables import RunnableSequence

from ..llm import get_chat_model
from ..prompts.repair import repair_prompt


def get_repair_chain() -> RunnableSequence:
    """
    构建修复链：repair_prompt → LLM。

    输入 dict keys: reference_date, raw_message, hints_json, current_json, validation_error
    输出 AIMessage（content 为修复后的 JSON 字符串）。
    """
    return repair_prompt | get_chat_model(temperature=0.0)
