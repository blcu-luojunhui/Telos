from typing import Any
from ._tool import Tool


class ToolExecutor:
    """
    管理一组工具：生成给 LLM 看的描述文本，并按名称执行。
    执行时传入的 kwargs 会传给 execute（如 user_id、reference_date 等）。
    """

    def __init__(self, tools: list[Tool]):
        self._tools = {t.name.lower(): t for t in tools}

    def get_tools_description(self) -> str:
        """返回给 prompt 用的工具说明。"""
        lines = [t.to_description_line() for t in self._tools.values()]
        return "\n".join(lines) if lines else "（暂无可用工具）"

    def get_tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def run(self, tool_name: str, tool_input: str, **kwargs: Any) -> str:
        """执行指定工具，返回观察结果字符串。"""
        name = (tool_name or "").strip().lower()
        if not name:
            return "错误：未指定工具名称。"
        tool = self._tools.get(name)
        if not tool:
            return f"错误：未知工具「{tool_name}」。可用工具：{', '.join(self.get_tool_names())}。"
        try:
            return tool.execute(tool_input, **kwargs) or ""
        except Exception as e:
            return f"工具执行异常：{e!s}"
