"""
Chat 核心流程：NLU → 重复检测 → 确认 → 落库。
"""
from __future__ import annotations

from datetime import date

from src.domain.interaction.nlu import parse_user_message
from src.domain.interaction.record import apply_parsed_record
from src.domain.interaction.duplicate_checker import check_duplicate
from src.domain.interaction.schemas import IntentType, ParsedRecord

from .session import ChatSession, PendingConfirm, get_or_create_session
from .response import ChatResponse
from .display import parsed_dict, intent_cn, payload_summary

_CONFIRM_KEYWORDS = {
    "确认", "是", "是的", "对", "好", "好的", "替换", "覆盖", "yes", "y", "ok",
}
_CANCEL_KEYWORDS = {"取消", "不", "不要", "算了", "no", "n", "cancel"}


async def handle_chat_message(
    message: str,
    session_id: str | None = None,
    reference_date: date | None = None,
) -> ChatResponse:
    session = get_or_create_session(session_id)
    ref = reference_date or date.today()
    msg = message.strip()

    session.add_turn("user", msg)

    if session.pending:
        return await _handle_pending(session, msg)

    try:
        parsed = await parse_user_message(msg, reference_date=ref)
    except Exception as e:
        session.add_turn("assistant", f"解析出错：{e}")
        return ChatResponse(
            session_id=session.session_id,
            type="error",
            message=f"抱歉，解析时出了问题：{e}",
        )

    if parsed.intent == IntentType.UNKNOWN:
        reply = "抱歉，我没有理解你的意思。你可以告诉我你吃了什么、做了什么运动、或者记录身体数据。"
        session.add_turn("assistant", reply)
        return ChatResponse(
            session_id=session.session_id,
            type="unknown",
            message=reply,
            parsed=parsed_dict(parsed),
        )

    dup = await check_duplicate(parsed.intent, parsed.date or ref, parsed.payload or {})

    if dup is not None:
        if dup.same_content:
            reply = f"你已经记录过了哦 —— {dup.summary}，内容完全一样，无需重复记录。"
            session.add_turn("assistant", reply, extra={"dup": "same"})
            return ChatResponse(
                session_id=session.session_id,
                type="duplicate_same",
                message=reply,
                parsed=parsed_dict(parsed),
                conflict={
                    "existing_id": dup.existing_id,
                    "table": dup.table,
                    "summary": dup.summary,
                },
            )
        else:
            session.pending = PendingConfirm(parsed=parsed, duplicate=dup)
            reply = (
                f"检测到今天已有一条类似记录 —— {dup.summary}。\n"
                f"你这次的内容不一样，是否要覆盖之前的记录？\n"
                f"回复「确认」覆盖，或「取消」放弃。"
            )
            session.add_turn("assistant", reply, extra={"dup": "diff_confirm"})
            return ChatResponse(
                session_id=session.session_id,
                type="needs_confirm",
                message=reply,
                parsed=parsed_dict(parsed),
                conflict={
                    "existing_id": dup.existing_id,
                    "table": dup.table,
                    "summary": dup.summary,
                },
            )

    return await _save_and_reply(session, parsed)


async def _handle_pending(session: ChatSession, msg: str) -> ChatResponse:
    pending = session.pending
    assert pending is not None
    normalized = msg.strip().lower()

    if normalized in _CONFIRM_KEYWORDS:
        session.pending = None
        return await _save_and_reply(
            session, pending.parsed, replace_id=pending.duplicate.existing_id
        )

    if normalized in _CANCEL_KEYWORDS:
        session.pending = None
        reply = "好的，已取消，之前的记录保持不变。"
        session.add_turn("assistant", reply)
        return ChatResponse(
            session_id=session.session_id,
            type="cancelled",
            message=reply,
        )

    session.pending = None
    session.add_turn("system", "[pending expired: new message received]")
    return await handle_chat_message(msg, session_id=session.session_id)


async def _save_and_reply(
    session: ChatSession,
    parsed: ParsedRecord,
    replace_id: int | None = None,
) -> ChatResponse:
    if replace_id is not None:
        await _delete_existing(parsed.intent, replace_id)

    result = await apply_parsed_record(parsed)

    if result.get("ok"):
        action = "已覆盖旧记录并保存" if replace_id else "已记录"
        reply = f"✅ {action}：{intent_cn(parsed.intent)}"
        detail = payload_summary(parsed.intent, parsed.payload or {})
        if detail:
            reply += f"（{detail}）"
        session.add_turn("assistant", reply, extra={"saved": result})
        return ChatResponse(
            session_id=session.session_id,
            type="confirmed" if replace_id else "saved",
            message=reply,
            parsed=parsed_dict(parsed),
            saved=result,
        )
    else:
        reply = f"保存失败：{result.get('error', '未知错误')}"
        session.add_turn("assistant", reply)
        return ChatResponse(
            session_id=session.session_id,
            type="error",
            message=reply,
            parsed=parsed_dict(parsed),
        )


async def _delete_existing(intent: IntentType, record_id: int) -> None:
    from src.core.database.mysql import (
        async_mysql_pool,
        Workout,
        Meal,
        BodyMetric,
        Goal,
    )
    from sqlalchemy import delete

    model_map = {
        IntentType.RECORD_WORKOUT: Workout,
        IntentType.RECORD_MEAL: Meal,
        IntentType.RECORD_BODY_METRIC: BodyMetric,
        IntentType.SET_GOAL: Goal,
    }
    model = model_map.get(intent)
    if not model:
        return
    async with async_mysql_pool.session() as session:
        await session.execute(delete(model).where(model.id == record_id))
        await session.commit()
