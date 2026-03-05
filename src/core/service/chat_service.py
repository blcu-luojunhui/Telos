"""
Chat 应用服务：编排 NLU → 重复检测 → 确认 → 落库，依赖注入各端口实现。
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from src.domain.interaction.duplicate_checker import (
    DuplicateHit,
    build_domain_record_and_inject_meal,
)
from src.domain.interaction.schemas import IntentType, ParsedRecord
from src.domain.interaction.chat.display import parsed_dict, intent_cn, payload_summary
from src.domain.interaction.chat.response import ChatResponse
from src.infra.persistence import (
    MySQLRecordApplier,
    MySQLDuplicateChecker,
    MySQLSessionStore,
    PendingConfirm,
)


_CONFIRM_KEYWORDS = {
    "确认", "是", "是的", "对", "好", "好的", "替换", "覆盖",
    "yes", "y", "ok", "1",
}
_CANCEL_KEYWORDS = {"取消", "不", "不要", "算了", "no", "n", "cancel", "0"}


class ChatApplicationService:
    """
    聊天用例应用服务：依赖 IRecordApplier、IDuplicateChecker、ISessionStore、
    ISmallChatRunner、INLUParser 的具象实现，实现 handle_chat_message 流程。
    """

    def __init__(
        self,
        record_applier: Any,  # IRecordApplier
        duplicate_checker: Any,  # IDuplicateChecker
        session_store: Any,  # ISessionStore
        small_chat_runner: Any,  # ISmallChatRunner
        nlu_parser: Any,  # INLUParser
    ):
        self._record_applier = record_applier
        self._duplicate_checker = duplicate_checker
        self._session_store = session_store
        self._small_chat_runner = small_chat_runner
        self._nlu_parser = nlu_parser

    async def handle_chat_message(
        self,
        user_id: str,
        message: str,
        reference_date: date | None = None,
        conversation_id: int | None = None,
    ) -> ChatResponse:
        conv_id = await self._session_store.get_or_create_conversation(
            user_id, conversation_id
        )
        session = self._session_store.get_user_session(user_id, conv_id)
        ref = reference_date or date.today()
        msg = message.strip()

        history = await session.get_recent_history()
        await session.add_turn("user", msg)

        if await session.has_pending():
            return await self._handle_pending(session, msg, conv_id)

        try:
            parsed = await self._nlu_parser.parse(msg, reference_date=ref, history=history)
            parsed.user_id = user_id
        except Exception as e:
            reply = f"抱歉，解析时出了问题：{e}"
            await session.add_turn("assistant", reply, msg_type="error")
            return ChatResponse(
                user_id=user_id,
                type="error",
                message=reply,
                conversation_id=conv_id,
            )

        if parsed.intent == IntentType.UNKNOWN:
            reply, sticker_id = await self._small_chat_runner.run(
                user_id=user_id, message=msg, history=history
            )
            await session.add_turn(
                "assistant",
                reply,
                msg_type="chat_only",
                extra={"sticker_id": sticker_id} if sticker_id is not None else None,
            )
            return ChatResponse(
                user_id=user_id,
                type="chat_only",
                message=reply,
                conversation_id=conv_id,
                parsed=None,
                sticker_id=sticker_id,
            )

        dr = build_domain_record_and_inject_meal(parsed, user_id, ref, history)
        dup = await self._duplicate_checker.check(dr)

        if dup is not None:
            if dup.same_content:
                reply = (
                    f"你已经记录过了哦 —— {dup.summary}，内容完全一样，无需重复记录。"
                )
                await session.add_turn("assistant", reply, msg_type="duplicate_same")
                return ChatResponse(
                    user_id=user_id,
                    type="duplicate_same",
                    message=reply,
                    conversation_id=conv_id,
                    parsed=parsed_dict(parsed),
                    conflict={
                        "existing_id": dup.existing_id,
                        "table": dup.table,
                        "summary": dup.summary,
                    },
                )
            pending = PendingConfirm(parsed=parsed, duplicate=dup)
            await session.set_pending(pending)
            reply = (
                f"检测到今天已有一条类似记录 —— {dup.summary}。\n"
                "你这次的内容不一样，是否要覆盖之前的记录？\n"
                "回复「确认」覆盖，或「取消」放弃。"
            )
            await session.add_turn("assistant", reply, msg_type="needs_confirm")
            return ChatResponse(
                user_id=user_id,
                type="needs_confirm",
                message=reply,
                conversation_id=conv_id,
                parsed=parsed_dict(parsed),
                conflict={
                    "existing_id": dup.existing_id,
                    "table": dup.table,
                    "summary": dup.summary,
                },
            )

        return await self._save_and_reply(session, parsed, conv_id)

    async def _handle_pending(
        self,
        session: Any,
        msg: str,
        conversation_id: int,
    ) -> ChatResponse:
        pending = await session.get_pending()
        normalized = msg.strip().lower()

        if pending is None:
            await session.clear_pending()
            return await self.handle_chat_message(
                session.user_id, msg, conversation_id=conversation_id
            )
        if normalized in _CONFIRM_KEYWORDS:
            await session.clear_pending()
            return await self._save_and_reply(
                session,
                pending.parsed,
                conversation_id,
                replace_id=pending.duplicate.existing_id,
            )
        if normalized in _CANCEL_KEYWORDS:
            await session.clear_pending()
            reply = "好的，已取消，之前的记录保持不变。"
            await session.add_turn("assistant", reply, msg_type="cancelled")
            return ChatResponse(
                user_id=session.user_id,
                type="cancelled",
                message=reply,
                conversation_id=conversation_id,
            )
        await session.clear_pending()
        return await self.handle_chat_message(
            session.user_id, msg, conversation_id=conversation_id
        )

    async def _save_and_reply(
        self,
        session: Any,
        parsed: ParsedRecord,
        conversation_id: int,
        replace_id: int | None = None,
    ) -> ChatResponse:
        parsed.user_id = session.user_id
        result = await self._record_applier.apply(parsed, replace_id=replace_id)
        if result.get("ok"):
            action = "已覆盖旧记录并保存" if replace_id else "已记录"
            reply = f"✅ {action}：{intent_cn(parsed.intent)}"
            detail = payload_summary(parsed.intent, parsed.payload or {})
            if detail:
                reply += f"（{detail}）"
            msg_type = "confirmed" if replace_id else "saved"
            await session.add_turn(
                "assistant", reply, msg_type=msg_type, extra={"saved": result}
            )
            return ChatResponse(
                user_id=session.user_id,
                type=msg_type,
                message=reply,
                conversation_id=conversation_id,
                parsed=parsed_dict(parsed),
                saved=result,
            )
        reply = f"保存失败：{result.get('error', '未知错误')}"
        await session.add_turn("assistant", reply, msg_type="error")
        return ChatResponse(
            user_id=session.user_id,
            type="error",
            message=reply,
            conversation_id=conversation_id,
            parsed=parsed_dict(parsed),
        )

    # 委托给 session_store，供路由直接使用
    async def get_or_create_conversation(
        self,
        user_id: str,
        conversation_id: Optional[int] = None,
    ) -> int:
        return await self._session_store.get_or_create_conversation(
            user_id, conversation_id
        )

    def get_user_session(
        self,
        user_id: str,
        conversation_id: Optional[int] = None,
    ) -> Any:
        return self._session_store.get_user_session(user_id, conversation_id)

    async def get_latest_conversation_id(self, user_id: str) -> Optional[int]:
        return await self._session_store.get_latest_conversation_id(user_id)

    async def conversation_belongs_to_user(
        self,
        user_id: str,
        conversation_id: int,
    ) -> bool:
        return await self._session_store.conversation_belongs_to_user(
            user_id, conversation_id
        )


class _DefaultNluParser:
    """INLUParser 的默认实现：委托给 domain nlu.parse_user_message。"""

    async def parse(
        self,
        message: str,
        reference_date: Optional[date] = None,
        history: Optional[list] = None,
    ) -> ParsedRecord:
        from src.domain.interaction.nlu import parse_user_message
        return await parse_user_message(
            message,
            reference_date=reference_date,
            history=history,
        )


class _DefaultSmallChatRunner:
    """ISmallChatRunner 的默认实现：委托给 domain small_chat_reply。"""

    async def run(
        self,
        user_id: str,
        message: str,
        history: Any,
    ) -> tuple[str, Optional[int]]:
        from src.domain.interaction.chat.small_chat import small_chat_reply
        return await small_chat_reply(
            user_id=user_id,
            message=message,
            history=history,
        )


def create_chat_application_service() -> ChatApplicationService:
    """组合根：使用默认的 MySQL 适配器与 NLU/SmallChat 实现创建 Chat 应用服务。"""
    record_applier = MySQLRecordApplier()
    duplicate_checker = MySQLDuplicateChecker()
    session_store = MySQLSessionStore()
    small_chat_runner = _DefaultSmallChatRunner()
    nlu_parser = _DefaultNluParser()
    return ChatApplicationService(
        record_applier=record_applier,
        duplicate_checker=duplicate_checker,
        session_store=session_store,
        small_chat_runner=small_chat_runner,
        nlu_parser=nlu_parser,
    )
