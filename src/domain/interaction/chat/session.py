"""
用户会话管理：基于 user_id + conversation_id + MySQL 持久化。

- 会话维度：conversation_id 标识一次对话，上下文仅限当前会话。
- 待确认状态：存入 pending_confirmations 表，与消息表解耦。
- conversation_id 为 None 时按仅 user_id 行为（兼容旧数据）。
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import delete, select, desc, update
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql import func

from src.core.database.mysql import (
    async_mysql_pool,
    Conversation,
    ChatMessage,
    PendingConfirmation,
)
from src.domain.interaction.duplicate_checker import DuplicateHit
from src.domain.interaction.schemas import IntentType, ParsedRecord

CONTEXT_WINDOW = 20  # 当前会话最近 N 条消息作为上下文
CONVERSATION_REUSE_MINUTES = 30  # 多少分钟内复用同一会话（不传 conversation_id 时）


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


async def conversation_belongs_to_user(user_id: str, conversation_id: int) -> bool:
    """校验 conversation_id 是否存在且属于该 user_id（用于拉历史时不做复用）。"""
    async with async_mysql_pool.session() as session:
        result = await session.execute(
            select(Conversation.id).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            ).limit(1)
        )
        return result.scalars().first() is not None


async def get_latest_conversation_id(user_id: str) -> Optional[int]:
    """返回该用户最近一次 active 会话的 id，没有则返回 None。"""
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
        row = result.scalar_one_or_none()
        return int(row) if row is not None else None


async def get_or_create_conversation(
    user_id: str, conversation_id: Optional[int] = None
) -> int | InstrumentedAttribute[int] | Any:
    """
    解析或创建会话 ID。
    - 若传入 conversation_id：校验存在且属于该 user，返回该 id。
    - 若未传：取该用户最近一次 active 会话（updated_at 在 N 分钟内则复用），否则新建。
    返回最终使用的 conversation_id。
    """
    async with async_mysql_pool.session() as session:
        if conversation_id is not None:
            result = await session.execute(
                select(Conversation).where(
                    Conversation.id == conversation_id, Conversation.user_id == user_id
                )
            )
            conv = result.scalars().one_or_none()
            if conv is not None:
                return conversation_id

        # 最近一条 active 会话（可选：按 updated_at 在 N 分钟内复用）
        result = await session.execute(
            select(Conversation)
            .where(
                Conversation.user_id == user_id, Conversation.status == "active"
            )
            .order_by(
                desc(Conversation.updated_at)
            )
            .limit(1)
        )
        latest = result.scalars().one_or_none()
        if latest:
            # 简单策略：总是复用最近会话；如需“超时新建”可在此比较 updated_at
            return latest.id

        # 新建会话
        conv = Conversation(user_id=user_id, status="active")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        return conv.id


class UserSession:
    """基于 user_id + conversation_id 的持久化会话。conversation_id 为 None 时仅按 user_id（兼容旧数据）。"""

    def __init__(self, user_id: str, conversation_id: Optional[int] = None):
        self.user_id = user_id
        self.conversation_id = conversation_id

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
                conversation_id=self.conversation_id,
                role=role,
                content=content,
                msg_type=msg_type,
                extra=extra,
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
        """当前会话的消息筛选条件。"""
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
                .order_by(
                    desc(ChatMessage.created_at)
                )
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


def get_user_session(
    user_id: str, conversation_id: Optional[int] = None
) -> UserSession:
    return UserSession(user_id=user_id, conversation_id=conversation_id)
