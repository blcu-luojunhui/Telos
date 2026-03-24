"""
MySQL 会话存储适配器：实现 ISessionStore，基于 user_id + conversation_id 持久化会话与待确认。

会话超时：当最近一个 active 会话的 updated_at 距今超过 SESSION_TIMEOUT_MINUTES 时，
自动将旧会话归档（status → archived），并创建新会话。
"""

from __future__ import annotations

import logging
from datetime import datetime, date, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import delete, select, desc, update, or_
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

logger = logging.getLogger("session")

CONTEXT_WINDOW = 20
SESSION_TIMEOUT_MINUTES = 30


class PendingConfirm:
    """等待用户确认的操作，序列化存入 pending_confirmations 表。"""

    def __init__(self, parsed: ParsedRecord, duplicate: DuplicateHit):
        self.parsed = parsed
        self.duplicate = duplicate

    def to_dict(self) -> dict:
        def _jsonable(value: Any) -> Any:
            if value is None or isinstance(value, (str, int, float, bool)):
                return value
            if isinstance(value, (datetime, date)):
                return value.isoformat()
            if isinstance(value, dict):
                return {str(k): _jsonable(v) for k, v in value.items()}
            if isinstance(value, (list, tuple, set)):
                return [_jsonable(v) for v in value]
            return str(value)

        return {
            "parsed": {
                "user_id": self.parsed.user_id or "",
                "intent": self.parsed.intent.value,
                "date": self.parsed.date.isoformat() if self.parsed.date else None,
                "payload": _jsonable(self.parsed.payload),
                "raw_message": self.parsed.raw_message,
            },
            "duplicate": {
                "existing_id": self.duplicate.existing_id,
                "table": self.duplicate.table,
                "same_content": self.duplicate.same_content,
                "summary": _jsonable(self.duplicate.summary),
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

    def __init__(self, timeout_minutes: int = SESSION_TIMEOUT_MINUTES):
        self._timeout_minutes = timeout_minutes

    async def get_or_create_conversation(
        self,
        user_id: str,
        conversation_id: Optional[int] = None,
    ) -> int:
        """
        返回应使用的 conversation_id。

        逻辑：
        1. 前端显式传入 conversation_id → 校验归属后直接使用
        2. 否则找最近一个 active 会话：
           a. updated_at 在超时阈值内 → 复用
           b. 已超时 → 归档旧会话、清除其 pending，创建新会话
        3. 无 active 会话 → 新建
        """
        async with async_mysql_pool.session() as session:
            # 1. 前端显式指定
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

            # 2. 找最近 active/pinned 会话
            result = await session.execute(
                select(Conversation)
                .where(
                    Conversation.user_id == user_id,
                    or_(Conversation.status == "active", Conversation.status == "pinned"),
                )
                .order_by(desc(Conversation.updated_at))
                .limit(1)
            )
            latest = result.scalars().one_or_none()

            if latest is not None:
                # 置顶会话不受超时切分影响，始终复用
                if latest.status == "pinned":
                    return latest.id
                if not self._is_expired(latest.updated_at):
                    return latest.id
                # 超时：归档旧会话
                await session.execute(
                    update(Conversation)
                    .where(Conversation.id == latest.id)
                    .values(status="archived")
                )
                await session.execute(
                    delete(PendingConfirmation).where(
                        PendingConfirmation.user_id == user_id,
                        PendingConfirmation.conversation_id == latest.id,
                    )
                )
                logger.info(
                    "Session %d expired (user=%s, idle %s), archived → creating new",
                    latest.id, user_id,
                    self._idle_desc(latest.updated_at),
                )

            # 3. 新建
            conv = Conversation(user_id=user_id, status="active")
            session.add(conv)
            await session.commit()
            await session.refresh(conv)
            logger.debug("New session %d created for user=%s", conv.id, user_id)
            return conv.id

    def _is_expired(self, updated_at: Optional[datetime]) -> bool:
        if updated_at is None:
            return True
        now = datetime.now(timezone.utc)
        ua = updated_at if updated_at.tzinfo else updated_at.replace(tzinfo=timezone.utc)
        return (now - ua) > timedelta(minutes=self._timeout_minutes)

    @staticmethod
    def _idle_desc(updated_at: Optional[datetime]) -> str:
        if updated_at is None:
            return "unknown"
        now = datetime.now(timezone.utc)
        ua = updated_at if updated_at.tzinfo else updated_at.replace(tzinfo=timezone.utc)
        delta = now - ua
        minutes = int(delta.total_seconds() / 60)
        if minutes < 60:
            return f"{minutes}m"
        return f"{minutes // 60}h{minutes % 60}m"

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
                    or_(Conversation.status == "active", Conversation.status == "pinned"),
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
