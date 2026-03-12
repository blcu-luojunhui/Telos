"""
Chat 响应模型。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ChatResponse:
    user_id: str
    type: str  # saved / duplicate_same / needs_confirm / confirmed / cancelled / error / chat_only / query / plan_preview / ...
    message: str  # 给用户看的自然语言回复
    conversation_id: int | None = None  # 本次使用的会话 ID，前端可后续请求带上
    parsed: dict | None = None
    saved: dict | None = None
    conflict: dict | None = None
    sticker_id: int | None = None  # 情绪表情包 ID 1~25，仅 type=chat_only 时可能有
    trace_id: str | None = None  # 请求追踪 ID，便于审计与排查
    extra: Optional[dict[str, Any]] = None  # 扩展：如 plan_preview 等供前端表格展示
