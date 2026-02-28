"""
会话管理：ChatSession、PendingConfirm、会话存储与生命周期。
内存版，后续可迁移 Redis。
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from src.domain.interaction.duplicate_checker import DuplicateHit
from src.domain.interaction.schemas import ParsedRecord

SESSION_TTL = 30 * 60  # 30 分钟无操作过期


@dataclass
class PendingConfirm:
    """等待用户确认的操作"""

    parsed: ParsedRecord
    duplicate: DuplicateHit
    created_at: float = field(default_factory=time.time)


@dataclass
class ChatSession:
    session_id: str
    history: list[dict[str, Any]] = field(default_factory=list)
    pending: Optional[PendingConfirm] = None
    last_active: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_active = time.time()

    def is_expired(self) -> bool:
        return (time.time() - self.last_active) > SESSION_TTL

    def add_turn(
        self, role: str, content: str, extra: dict[str, Any] | None = None
    ) -> None:
        entry: dict[str, Any] = {"role": role, "content": content, "ts": time.time()}
        if extra:
            entry["extra"] = extra
        self.history.append(entry)
        self.touch()


_sessions: dict[str, ChatSession] = {}


def get_or_create_session(session_id: str | None) -> ChatSession:
    _gc_expired()
    if session_id and session_id in _sessions:
        s = _sessions[session_id]
        if not s.is_expired():
            s.touch()
            return s
        del _sessions[session_id]

    sid = session_id or uuid.uuid4().hex[:16]
    s = ChatSession(session_id=sid)
    _sessions[sid] = s
    return s


def _gc_expired() -> None:
    expired = [k for k, v in _sessions.items() if v.is_expired()]
    for k in expired:
        del _sessions[k]
