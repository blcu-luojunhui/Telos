"""
LLM 输入/输出类型定义。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

# 消息角色
ChatRole = Literal["system", "user", "assistant"]


@dataclass
class ChatMessage:
    """单条对话消息，用于构造 LLM 请求。"""

    role: ChatRole
    content: str

    def to_openai_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content or ""}


@dataclass
class ToolDef:
    """
    OpenAI 风格的工具定义（function calling）。
    parameters 为 JSON Schema 字典，如 {"type": "object", "properties": {...}}
    """

    name: str
    description: str
    parameters: dict[str, Any] = field(
        default_factory=lambda: {"type": "object", "properties": {}}
    )

    def to_openai_dict(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolCall:
    """模型返回的一次工具调用。"""

    id: str
    name: str
    arguments: str  # JSON 字符串，调用方自行解析

    def get_args_dict(self) -> dict[str, Any]:
        try:
            return json.loads(self.arguments) if self.arguments else {}
        except Exception:
            return {}


@dataclass
class ChatCompletionResult:
    """
    单次模型调用的统一返回：
    - 纯文本对话：仅 content 有值
    - 带 tool_calls：content 可能为空，tool_calls 为列表
    """

    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None
    raw_message: Any = None  # 原始 API message 对象，便于调试或取 usage

    @property
    def text(self) -> str:
        """首选：取文本内容，无则空串。"""
        return (self.content or "").strip()
