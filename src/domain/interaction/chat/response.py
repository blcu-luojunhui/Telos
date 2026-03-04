"""
Chat 响应模型。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ChatResponse:
    user_id: str
    type: str  # saved / duplicate_same / needs_confirm / confirmed / cancelled / error / unknown
    message: str  # 给用户看的自然语言回复
    conversation_id: int | None = None  # 本次使用的会话 ID，前端可后续请求带上
    parsed: dict | None = None
    saved: dict | None = None
    conflict: dict | None = None
