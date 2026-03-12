"""
MySQL 会话存储适配器：实现 ISessionStore，基于 user_id + conversation_id 持久化会话与待确认。
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import delete, select, desc, update
from sqlalchemy.sql import func

from src.infra.database.mysql import (
    async_mysql_pool,
    Conversation,
    ChatMessage,
    PendingConfirmation,
    Soul,
)
from src.domain.interaction.duplicate_checker import DuplicateHit
from src.domain.interaction.schemas import IntentType, ParsedRecord

CONTEXT_WINDOW = 20
CONVERSATION_REUSE_MINUTES = 30  # 未使用：可后续做超时新建会话


class PendingConfirm:
    """等待用户确认的操作，序列化存入 pending_confirmations 表。"""

    def __init__(self, parsed: ParsedRecord, duplicate: DuplicateHit):
        self.parsed = parsed
        self.duplicate = duplicate

    def to_dict(self) -> dict:
        return {
            "parsed": {
                "user_id": self.parsed.user_id or "",
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
            user_id=p.get("user_id") or "",
            intent=IntentType(p["intent"]),
            date=parsed_date,
            payload=p.get("payload"),
            raw_message=p.get("raw_message", ""),
        )
        dup = DuplicateHit(**d["duplicate"])
        return cls(parsed=parsed, duplicate=dup)


class MySQLUserSession:
    """基于 user_id + conversation_id 的持久化会话（实现 IUserSession）。"""

    def __init__(self, user_id: str, conversation_id: Optional[int] = None):
        self.user_id = user_id
        self.conversation_id = conversation_id

    async def add_turn(
        self,
        role: str,
        content: str,
        msg_type: Optional[str] = None,
        extra: Optional[dict[str, Any]] = None,
        soul_id: Optional[int] = None,
    ) -> None:
        async with async_mysql_pool.session() as session:
            msg = ChatMessage(
                user_id=self.user_id,
                conversation_id=self.conversation_id,
                role=role,
                content=content,
                msg_type=msg_type,
                extra=extra,
                soul_id=soul_id,
            )
            session.add(msg)
            if self.conversation_id is not None:
                await session.execute(
                    update(Conversation)
                    .where(Conversation.id == self.conversation_id)
                    .values(updated_at=func.now())
                )
            await session.commit()

    def _message_filter(self):
        if self.conversation_id is not None:
            return ChatMessage.conversation_id == self.conversation_id
        return ChatMessage.user_id == self.user_id

    async def get_recent_history(
        self, limit: int = CONTEXT_WINDOW
    ) -> list[dict[str, Any]]:
        async with async_mysql_pool.session() as session:
            stmt = (
                select(ChatMessage)
                .where(self._message_filter())
                .order_by(desc(ChatMessage.created_at))
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
        # 预加载 soul 信息以便返回 slug/name
        soul_ids = [r.soul_id for r in rows if r.soul_id is not None]
        soul_map: dict[int, dict] = {}
        if soul_ids:
            async with async_mysql_pool.session() as session:
                stmt = select(Soul).where(Soul.id.in_(soul_ids))
                res = await session.execute(stmt)
                for row in res.scalars().all():
                    soul_map[row.id] = {"id": row.id, "slug": row.slug, "name": row.name}
        return [
            {
                "role": r.role,
                "content": r.content,
                "msg_type": r.msg_type,
                "extra": r.extra,
                "soul_id": r.soul_id,
                "soul": soul_map.get(r.soul_id) if r.soul_id else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reversed(rows)
        ]

    def _pending_filter(self):
        if self.conversation_id is not None:
            return (
                PendingConfirmation.user_id == self.user_id,
                PendingConfirmation.conversation_id == self.conversation_id,
            )
        return (
            PendingConfirmation.user_id == self.user_id,
            PendingConfirmation.conversation_id.is_(None),
        )

    async def set_pending(self, pending: PendingConfirm) -> None:
        async with async_mysql_pool.session() as session:
            cond1, cond2 = self._pending_filter()
            await session.execute(delete(PendingConfirmation).where(cond1, cond2))
            snap = pending.to_dict()
            rec = PendingConfirmation(
                user_id=self.user_id,
                conversation_id=self.conversation_id,
                parsed_snapshot=snap["parsed"],
                duplicate_snapshot=snap["duplicate"],
            )
            session.add(rec)
            await session.commit()

    async def get_pending(self) -> Optional[PendingConfirm]:
        async with async_mysql_pool.session() as session:
            cond1, cond2 = self._pending_filter()
            stmt = select(PendingConfirmation).where(cond1, cond2)
            result = await session.execute(stmt)
            row = result.scalars().first()
        if not row:
            return None
        try:
            return PendingConfirm.from_dict(
                {"parsed": row.parsed_snapshot, "duplicate": row.duplicate_snapshot}
            )
        except Exception:
            return None

    async def clear_pending(self) -> None:
        async with async_mysql_pool.session() as session:
            cond1, cond2 = self._pending_filter()
            await session.execute(delete(PendingConfirmation).where(cond1, cond2))
            await session.commit()

    async def has_pending(self) -> bool:
        return await self.get_pending() is not None


class MySQLSessionStore:
    """实现 ISessionStore：会话创建、获取、校验。"""

    async def get_or_create_conversation(
        self,
        user_id: str,
        conversation_id: Optional[int] = None,
    ) -> int:
        async with async_mysql_pool.session() as session:
            if conversation_id is not None:
                result = await session.execute(
                    select(Conversation).where(
                        Conversation.id == conversation_id,
                        Conversation.user_id == user_id,
                    )
                )
                conv = result.scalars().one_or_none()
                if conv is not None:
                    return conversation_id
            result = await session.execute(
                select(Conversation)
                .where(
                    Conversation.user_id == user_id,
                    Conversation.status == "active",
                )
                .order_by(desc(Conversation.updated_at))
                .limit(1)
            )
            latest = result.scalars().one_or_none()
            if latest:
                return latest.id
            conv = Conversation(user_id=user_id, status="active")
            session.add(conv)
            await session.commit()
            await session.refresh(conv)
            return conv.id

    def get_user_session(
        self,
        user_id: str,
        conversation_id: Optional[int] = None,
    ) -> MySQLUserSession:
        return MySQLUserSession(user_id=user_id, conversation_id=conversation_id)

    async def get_latest_conversation_id(self, user_id: str) -> Optional[int]:
        async with async_mysql_pool.session() as session:
            result = await session.execute(
                select(Conversation.id)
                .where(
                    Conversation.user_id == user_id,
                    Conversation.status == "active",
                )
                .order_by(desc(Conversation.updated_at))
                .limit(1)
            )
            row = result.scalars().first()
        return int(row) if row is not None else None

    async def conversation_belongs_to_user(
        self,
        user_id: str,
        conversation_id: int,
    ) -> bool:
        async with async_mysql_pool.session() as session:
            result = await session.execute(
                select(Conversation.id).where(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id,
                ).limit(1)
            )
            return result.scalars().first() is not None
