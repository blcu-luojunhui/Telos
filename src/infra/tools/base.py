"""
Agent 工具基础抽象：Tool 定义 + ToolExecutor，供多种 Agent 复用。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

# 工具执行函数: (tool_input: str, **kwargs) -> Awaitable[str]
ToolFn = Callable[..., Awaitable[str]]


@dataclass
class Tool:
    """单个工具：名称、描述、执行函数。"""

    name: str
    description: str
    execute: ToolFn

    def to_description_line(self) -> str:
        return f"- {self.name}[输入]: {self.description}"


class ToolExecutor:
    """
    管理一组工具：生成给 LLM 看的描述文本，并按名称执行。
    执行时传入的 kwargs 会传给 execute（如 user_id、reference_date 等）。
    """

    def __init__(self, tools: list[Tool]):
        self._tools = {t.name.lower(): t for t in tools}

    def get_tools_description(self) -> str:
        lines = [t.to_description_line() for t in self._tools.values()]
        return "\n".join(lines) if lines else "（暂无可用工具）"

    def get_tool_names(self) -> list[str]:
        return list(self._tools.keys())

    async def run(self, tool_name: str, tool_input: str, **kwargs: Any) -> str:
        name = (tool_name or "").strip().lower()
        if not name:
            return "错误：未指定工具名称。"
        tool = self._tools.get(name)
        if not tool:
            return f"错误：未知工具「{tool_name}」。可用工具：{', '.join(self.get_tool_names())}。"
        try:
            return await tool.execute(tool_input, **kwargs) or ""
        except Exception as e:
            return f"工具执行异常：{e!s}"
