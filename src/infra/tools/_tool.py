"""
Agent 工具抽象：工具描述 + 执行器，供多种 Agent 复用。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

# 工具执行函数: (tool_input: str, **kwargs) -> str
ToolFn = Callable[..., str]


@dataclass
class Tool:
    """单个工具：名称、描述、执行函数。"""

    name: str
    description: str
    execute: ToolFn

    def to_description_line(self) -> str:
        return f"- {self.name}[输入]: {self.description}"
