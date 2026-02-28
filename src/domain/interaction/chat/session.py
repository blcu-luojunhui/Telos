"""
用户会话管理：基于 user_id + MySQL 持久化。

每个 user_id 就是一个长期 session，对话历史存库。
PendingConfirm（等待确认）存在最近一条 system 消息的 extra 字段中。
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select, desc

from src.core.database.mysql import async_mysql_pool, ChatMessage
from src.domain.interaction.duplicate_checker import DuplicateHit
from src.domain.interaction.schemas import IntentType, ParsedRecord

CONTEXT_WINDOW = 20  # 取最近 N 条消息作为上下文


class PendingConfirm:
    """等待用户确认的操作，序列化存入 DB extra 字段。"""

    def __init__(self, parsed: ParsedRecord, duplicate: DuplicateHit):
        self.parsed = parsed
        self.duplicate = duplicate

    def to_dict(self) -> dict:
        return {
            "parsed": {
                "intent": self.parsed.intent.value,
                "date": self.parsed.date.isoformat() if self.parsed.date else None,
                "payload": self.parsed.payload,
                "raw_message": self.parsed.raw_message,
            },
            "duplicate": {
                "existing_id": self.duplicate.existing_id,
                "table": self.duplicate.table,
                "same_content": self.duplicate.same_content,
                "summary": self.duplicate.summary,
            },
        }

    @classmethod
    def from_dict(cls, d: dict) -> PendingConfirm:
        from datetime import date as date_cls

        p = d["parsed"]
        parsed_date = date_cls.fromisoformat(p["date"]) if p.get("date") else None
        parsed = ParsedRecord(
            intent=IntentType(p["intent"]),
            date=parsed_date,
            payload=p.get("payload"),
            raw_message=p.get("raw_message", ""),
        )
        dup = DuplicateHit(**d["duplicate"])
        return cls(parsed=parsed, duplicate=dup)


class UserSession:
    """基于 user_id 的持久化会话。"""

    def __init__(self, user_id: str):
        self.user_id = user_id

    async def add_turn(
        self,
        role: str,
        content: str,
        msg_type: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        async with async_mysql_pool.session() as session:
            msg = ChatMessage(
                user_id=self.user_id,
                role=role,
                content=content,
                msg_type=msg_type,
                extra=extra,
            )
            session.add(msg)
            await session.commit()

    async def get_recent_history(
        self, limit: int = CONTEXT_WINDOW
    ) -> list[dict[str, Any]]:
        async with async_mysql_pool.session() as session:
            stmt = (
                select(ChatMessage)
                .where(ChatMessage.user_id == self.user_id)
                .order_by(desc(ChatMessage.created_at))
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()

        return [
            {
                "role": r.role,
                "content": r.content,
                "msg_type": r.msg_type,
                "extra": r.extra,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reversed(rows)
        ]

    async def set_pending(self, pending: PendingConfirm) -> None:
        await self.add_turn(
            role="system",
            content="pending_confirm",
            msg_type="pending",
            extra={"pending": pending.to_dict()},
        )

    async def get_pending(self) -> Optional[PendingConfirm]:
        async with async_mysql_pool.session() as session:
            stmt = (
                select(ChatMessage)
                .where(
                    ChatMessage.user_id == self.user_id,
                    ChatMessage.msg_type == "pending",
                )
                .order_by(desc(ChatMessage.created_at))
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.scalars().first()

        if not row or not row.extra:
            return None

        pending_data = row.extra.get("pending")
        if not pending_data:
            return None

        try:
            return PendingConfirm.from_dict(pending_data)
        except Exception:
            return None

    async def clear_pending(self) -> None:
        """通过写一条 system 消息标记 pending 已处理。"""
        await self.add_turn(
            role="system",
            content="pending_resolved",
            msg_type="pending_resolved",
        )

    async def has_pending(self) -> bool:
        """检查是否有未处理的 pending（最近的 pending 消息后面没有 pending_resolved）。"""
        async with async_mysql_pool.session() as session:
            stmt = (
                select(ChatMessage)
                .where(
                    ChatMessage.user_id == self.user_id,
                    ChatMessage.msg_type.in_(["pending", "pending_resolved"]),
                )
                .order_by(desc(ChatMessage.created_at))
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.scalars().first()

        return row is not None and row.msg_type == "pending"


def get_user_session(user_id: str) -> UserSession:
    return UserSession(user_id=user_id)
