"""
Chat 响应模型。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ChatResponse:
    session_id: str
    type: str  # saved / duplicate_same / needs_confirm / confirmed / cancelled / error / unknown
    message: str  # 给用户看的自然语言回复
    parsed: dict | None = None
    saved: dict | None = None
    conflict: dict | None = None
