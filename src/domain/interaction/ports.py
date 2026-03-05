"""
领域端口（Ports）：定义与基础设施的边界接口。

领域层仅依赖这些 Protocol，不依赖 core/infra 的具体实现。
应用层负责注入适配器（Adapters）实现这些端口。
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional, Protocol, Sequence

from src.domain.interaction.duplicate_checker import DuplicateHit
from src.domain.interaction.duplicate_checker.domain_record import DomainRecord
from src.domain.interaction.schemas import ParsedRecord


class IRecordApplier(Protocol):
    """记录落库端口：将解析结果持久化，支持覆盖时先软删再写入。"""

    async def apply(
        self,
        parsed: ParsedRecord,
        replace_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        落表并返回摘要。
        :param parsed: 解析结果
        :param replace_id: 若提供，则先对旧记录做软删再写入
        :return: {"ok": bool, "intent": str, "table": str|None, "id": int|None, "error": str|None}
        """
        ...


class IDuplicateChecker(Protocol):
    """重复检测端口：根据领域记录查库并返回是否重复。"""

    async def check(self, dr: DomainRecord) -> Optional[DuplicateHit]:
        """若存在同类记录返回 DuplicateHit，否则返回 None。"""
        ...


class IUserSession(Protocol):
    """单次用户会话抽象：历史、待确认、落轮。"""

    @property
    def user_id(self) -> str:
        ...

    async def add_turn(
        self,
        role: str,
        content: str,
        msg_type: Optional[str] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        ...

    async def get_recent_history(self, limit: int = 20) -> list[dict[str, Any]]:
        ...

    async def set_pending(self, pending: Any) -> None:
        ...

    async def get_pending(self) -> Optional[Any]:
        ...

    async def clear_pending(self) -> None:
        ...

    async def has_pending(self) -> bool:
        ...


class ISessionStore(Protocol):
    """会话存储端口：会话创建、获取、校验。"""

    async def get_or_create_conversation(
        self,
        user_id: str,
        conversation_id: Optional[int] = None,
    ) -> int:
        """返回最终使用的 conversation_id。"""
        ...

    def get_user_session(
        self,
        user_id: str,
        conversation_id: Optional[int] = None,
    ) -> IUserSession:
        ...

    async def get_latest_conversation_id(self, user_id: str) -> Optional[int]:
        ...

    async def conversation_belongs_to_user(
        self,
        user_id: str,
        conversation_id: int,
    ) -> bool:
        ...


class ISmallChatRunner(Protocol):
    """小聊天/唤起端口：未识别记录意图时生成自然语言回复。"""

    async def run(
        self,
        user_id: str,
        message: str,
        history: Sequence[dict],
    ) -> tuple[str, Optional[int]]:
        """返回 (回复正文, sticker_id 或 None)。"""
        ...


class INLUParser(Protocol):
    """NLU 解析端口：用户消息 → 意图与结构化 payload。"""

    async def parse(
        self,
        message: str,
        reference_date: Optional[date] = None,
        history: Optional[Sequence[dict]] = None,
    ) -> ParsedRecord:
        ...


__all__ = [
    "IRecordApplier",
    "IDuplicateChecker",
    "IUserSession",
    "ISessionStore",
    "ISmallChatRunner",
    "INLUParser",
]
