"""
Chat 应用服务：编排 NLU → 重复检测 → 确认 → 落库，依赖注入各端口实现。
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Optional

from src.core.audit import new_trace_id, log_chat_step

from src.domain.interaction.duplicate_checker import (
    DuplicateHit,
    build_domain_record_and_inject_meal,
)
from src.domain.interaction.schemas import IntentType, ParsedRecord
from src.domain.interaction.chat.display import (
    parsed_dict,
    intent_cn,
    payload_summary,
    format_query_reply,
    format_plan_preview_message,
)
from src.domain.interaction.chat.slot_fill import (
    missing_slots,
    slot_fill_question,
    merge_slot_from_message,
)
from src.domain.interaction.chat.response import ChatResponse
from src.infra.persistence import (
    MySQLRecordApplier,
    MySQLDuplicateChecker,
    MySQLSessionStore,
    PendingConfirm,
    MySQLQueryRunner,
    MySQLEditDeleteRunner,
)
from src.infra.persistence.mysql_soul_repository import get_soul_id_by_slug


def _is_confirm(msg: str) -> bool:
    """鲁棒判断用户是否在确认（覆盖）。"""
    t = msg.strip().lower()
    if t in ("确认", "是", "是的", "对", "好", "好的", "替换", "覆盖", "yes", "y", "ok", "1"):
        return True
    if "覆盖" in t or "替换" in t or "确认" in t or "那就" in t and ("好" in t or "吧" in t):
        return True
    return False


def _is_cancel(msg: str) -> bool:
    """鲁棒判断用户是否取消。"""
    t = msg.strip().lower()
    if t in ("取消", "不", "不要", "算了", "no", "n", "cancel", "0"):
        return True
    if "算了" in t or "不用了" in t or "不要了" in t or "取消" in t:
        return True
    return False


def _is_add_new(msg: str) -> bool:
    """是否选择「再记一条」保留原记录并新增。"""
    t = msg.strip()
    return "再记一条" in t or ("保留" in t and "新增" in t) or "不覆盖" in t and "新" in t


class ChatApplicationService:
    """
    聊天用例应用服务：依赖 IRecordApplier、IDuplicateChecker、ISessionStore、
    ISmallChatRunner、INLUParser、IQueryRunner、IEditDeleteRunner，实现 handle_chat_message 流程。
    """

    def __init__(
        self,
        record_applier: Any,  # IRecordApplier
        duplicate_checker: Any,  # IDuplicateChecker
        session_store: Any,  # ISessionStore
        small_chat_runner: Any,  # ISmallChatRunner
        nlu_parser: Any,  # INLUParser
        query_runner: Any,  # IQueryRunner
        edit_delete_runner: Any,  # IEditDeleteRunner
    ):
        self._record_applier = record_applier
        self._duplicate_checker = duplicate_checker
        self._session_store = session_store
        self._small_chat_runner = small_chat_runner
        self._nlu_parser = nlu_parser
        self._query_runner = query_runner
        self._edit_delete_runner = edit_delete_runner

    async def _reply_plan_preview(
        self,
        user_id: str,
        payload: dict,
        ref: date,
    ) -> tuple[str, dict]:
        """
        获取目标对应的计划预览，返回（专业版说明文案，extra 含 plan_preview）。
        若找不到目标或无法生成计划，返回简短提示与空 extra。
        """
        from sqlalchemy import select
        from src.infra.database.mysql import async_mysql_pool, Goal
        from src.domain.interaction.record._training_plan import build_plan_preview

        goal_id = payload.get("goal_id") if isinstance(payload.get("goal_id"), int) else None
        goal = None
        async with async_mysql_pool.session() as session:
            if goal_id:
                r = await session.execute(
                    select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id)
                )
                goal = r.scalars().first()
            if not goal:
                r = await session.execute(
                    select(Goal)
                    .where(Goal.user_id == user_id, Goal.status.in_(["planning", "ongoing"]))
                    .order_by(Goal.id.desc())
                    .limit(1)
                )
                goal = r.scalars().first()
        if not goal:
            return "你还没有可用的目标，先设定一个目标（如减脂、半马）再生成计划。", {}
        preview = build_plan_preview(goal, ref)
        if not preview:
            return "当前目标类型暂不支持自动生成训练计划。", {}
        return format_plan_preview_message(preview), {"plan_preview": preview}

    async def handle_chat_message(
        self,
        user_id: str,
        message: str,
        reference_date: date | None = None,
        conversation_id: int | None = None,
        trace_id: str | None = None,
        soul_id: str | None = None,
    ) -> ChatResponse:
        tid = trace_id or new_trace_id()
        soul_id_int: int | None = None
        if soul_id:
            soul_id_int = await get_soul_id_by_slug(soul_id)

        conv_id = await self._session_store.get_or_create_conversation(
            user_id, conversation_id
        )
        session = self._session_store.get_user_session(user_id, conv_id)
        ref = reference_date or date.today()
        msg = message.strip()

        history = await session.get_recent_history()
        await session.add_turn("user", msg)

        if await session.has_pending():
            return await self._handle_pending(
                session, msg, conv_id, trace_id=tid, soul_id_int=soul_id_int
            )

        try:
            parsed_list = await self._nlu_parser.parse(msg, reference_date=ref, history=history)
        except Exception as e:
            log_chat_step(tid, user_id, "nlu", error=str(e))
            reply = f"抱歉，解析时出了问题：{e}"
            await session.add_turn("assistant", reply, msg_type="error", soul_id=soul_id_int)
            return ChatResponse(
                user_id=user_id,
                type="error",
                message=reply,
                conversation_id=conv_id,
                trace_id=tid,
            )

        if not parsed_list:
            parsed_list = [
                ParsedRecord(
                    intent=IntentType.UNKNOWN,
                    date=ref,
                    payload={},
                    raw_message=msg,
                )
            ]
        record_intents = {
            IntentType.SET_GOAL,
            IntentType.RECORD_WORKOUT,
            IntentType.RECORD_MEAL,
            IntentType.RECORD_BODY_METRIC,
            IntentType.RECORD_STATUS,
        }
        primary_candidates = [p for p in parsed_list if p.intent in record_intents]
        primary = primary_candidates[0] if primary_candidates else parsed_list[0]
        primary.user_id = user_id
        has_request_plan = any(p.intent == IntentType.REQUEST_PLAN for p in parsed_list)
        parsed = primary
        log_chat_step(tid, user_id, "nlu", intent=parsed.intent.value, payload=parsed.payload)

        # 仅「要求计划」且无其他记录意图：直接返回当前目标的计划预览（专业版）
        if parsed.intent == IntentType.REQUEST_PLAN and not primary_candidates:
            plan_reply, plan_extra = await self._reply_plan_preview(user_id, parsed.payload or {}, ref)
            await session.add_turn(
                "assistant",
                plan_reply,
                msg_type="plan_preview",
                extra=plan_extra,
                soul_id=soul_id_int,
            )
            return ChatResponse(
                user_id=user_id,
                type="plan_preview",
                message=plan_reply,
                conversation_id=conv_id,
                parsed=parsed_dict(parsed),
                extra=plan_extra,
                trace_id=tid,
            )

        # 查询类：直接查库并返回自然语言摘要
        if parsed.intent in (
            IntentType.QUERY_WORKOUT,
            IntentType.QUERY_MEAL,
            IntentType.QUERY_BODY_METRIC,
            IntentType.QUERY_SUMMARY,
        ):
            q_result = await self._query_runner.run(
                user_id=user_id,
                intent=parsed.intent.value,
                payload=parsed.payload or {},
                reference_date=ref,
            )
            log_chat_step(tid, user_id, "query", intent=parsed.intent.value, result=q_result.get("summary"))
            reply = format_query_reply(parsed.intent, q_result)
            await session.add_turn("assistant", reply, msg_type="query", soul_id=soul_id_int)
            return ChatResponse(
                user_id=user_id,
                type="query",
                message=reply,
                conversation_id=conv_id,
                parsed=parsed_dict(parsed),
                trace_id=tid,
            )

        # 编辑上一条
        if parsed.intent == IntentType.EDIT_LAST:
            payload = parsed.payload or {}
            updates = payload.get("updates") or {}
            edit_result = await self._edit_delete_runner.edit_last(
                user_id=user_id,
                record_type=payload.get("record_type"),
                updates=updates,
                reference_date=ref,
            )
            if edit_result.get("ok"):
                reply = f"✅ 已修改上一条记录（id={edit_result.get('id')}）。"
            else:
                reply = f"修改失败：{edit_result.get('error', '未知错误')}"
            log_chat_step(tid, user_id, "edit_last", result="ok" if edit_result.get("ok") else edit_result.get("error"))
            await session.add_turn("assistant", reply, msg_type="edit_last", soul_id=soul_id_int)
            return ChatResponse(
                user_id=user_id,
                type="edit_last",
                message=reply,
                conversation_id=conv_id,
                parsed=parsed_dict(parsed),
                trace_id=tid,
            )

        # 删除记录
        if parsed.intent == IntentType.DELETE_RECORD:
            payload = parsed.payload or {}
            from datetime import date as date_type
            date_val = parsed.date or ref
            if isinstance(payload.get("date"), str):
                try:
                    date_val = date_type.fromisoformat(payload["date"][:10])
                except Exception:
                    pass
            del_result = await self._edit_delete_runner.delete_record(
                user_id=user_id,
                record_type=payload.get("record_type") or "",
                record_id=payload.get("record_id"),
                date_arg=date_val,
                meal_type=payload.get("meal_type"),
                workout_type=payload.get("workout_type"),
            )
            if del_result.get("ok"):
                reply = f"✅ 已删除记录（id={del_result.get('id')}）。"
            else:
                reply = f"删除失败：{del_result.get('error', '未知错误')}"
            log_chat_step(tid, user_id, "delete_record", result="ok" if del_result.get("ok") else del_result.get("error"))
            await session.add_turn("assistant", reply, msg_type="delete_record", soul_id=soul_id_int)
            return ChatResponse(
                user_id=user_id,
                type="delete_record",
                message=reply,
                conversation_id=conv_id,
                parsed=parsed_dict(parsed),
                trace_id=tid,
            )

        # 多轮补全：记录类意图缺必填项时先追问
        if parsed.intent in (
            IntentType.RECORD_MEAL,
            IntentType.RECORD_WORKOUT,
            IntentType.SET_GOAL,
        ):
            missing = missing_slots(parsed.intent, parsed.payload)
            if missing:
                slot_fill_dup = DuplicateHit(
                    existing_id=0,
                    table="_slot_fill",
                    same_content=False,
                    summary=json.dumps({"missing": missing}),
                )
                pending_sf = PendingConfirm(parsed=parsed, duplicate=slot_fill_dup)
                await session.set_pending(pending_sf)
                log_chat_step(tid, user_id, "slot_fill", intent=parsed.intent.value, payload={"missing": missing})
                reply = slot_fill_question(parsed.intent, missing)
                await session.add_turn("assistant", reply, msg_type="slot_fill", soul_id=soul_id_int)
                return ChatResponse(
                    user_id=user_id,
                    type="slot_fill",
                    message=reply,
                    conversation_id=conv_id,
                    parsed=parsed_dict(parsed),
                    trace_id=tid,
                )

        if parsed.intent == IntentType.UNKNOWN:
            reply, sticker_id = await self._small_chat_runner.run(
                user_id=user_id,
                message=msg,
                history=history,
                soul_id=soul_id,
            )
            await session.add_turn(
                "assistant",
                reply,
                msg_type="chat_only",
                extra={"sticker_id": sticker_id} if sticker_id is not None else None,
                soul_id=soul_id_int,
            )
            return ChatResponse(
                user_id=user_id,
                type="chat_only",
                message=reply,
                conversation_id=conv_id,
                parsed=None,
                sticker_id=sticker_id,
                trace_id=tid,
            )

        dr = build_domain_record_and_inject_meal(parsed, user_id, ref, history)
        dup = await self._duplicate_checker.check(dr)

        if dup is not None:
            if dup.same_content:
                reply = (
                    f"你已经记录过了哦 —— {dup.summary}，内容完全一样，无需重复记录。"
                )
                await session.add_turn("assistant", reply, msg_type="duplicate_same", soul_id=soul_id_int)
                log_chat_step(tid, user_id, "duplicate_same", intent=parsed.intent.value, result=dup.summary)
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
                    trace_id=tid,
                )
            pending = PendingConfirm(parsed=parsed, duplicate=dup)
            await session.set_pending(pending)
            reply = (
                f"检测到今天已有一条类似记录 —— {dup.summary}。\n"
                "你这次的内容不一样，可以：\n"
                "· 回复「确认」覆盖原记录\n"
                "· 回复「再记一条」保留原记录并新增这条\n"
                "· 回复「取消」放弃本次记录"
            )
            await session.add_turn("assistant", reply, msg_type="needs_confirm", soul_id=soul_id_int)
            log_chat_step(tid, user_id, "needs_confirm", intent=parsed.intent.value, result=dup.summary)
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
                trace_id=tid,
            )

        # 识别到记录意图后先向用户确认再存储，不随意落库
        confirm_summary = json.dumps({"_also_request_plan": True}) if has_request_plan else ""
        confirm_save_dup = DuplicateHit(
            existing_id=0,
            table="_confirm_save",
            same_content=False,
            summary=confirm_summary,
        )
        pending_save = PendingConfirm(parsed=parsed, duplicate=confirm_save_dup)
        await session.set_pending(pending_save)
        detail = payload_summary(parsed.intent, parsed.payload or {})
        reply = (
            f"要帮你记下来吗？—— {intent_cn(parsed.intent)}"
            + (f"（{detail}）" if detail else "")
            + "\n回复「确认」或「好的」保存，回复「取消」不保存。"
        )
        if has_request_plan:
            reply += "\n确认后我会为你生成训练计划预览。"
        await session.add_turn("assistant", reply, msg_type="confirm_before_save", soul_id=soul_id_int)
        log_chat_step(tid, user_id, "confirm_before_save", intent=parsed.intent.value)
        return ChatResponse(
            user_id=user_id,
            type="confirm_before_save",
            message=reply,
            conversation_id=conv_id,
            parsed=parsed_dict(parsed),
            trace_id=tid,
        )

    async def _handle_pending(
        self,
        session: Any,
        msg: str,
        conversation_id: int,
        trace_id: str | None = None,
        soul_id_int: int | None = None,
    ) -> ChatResponse:
        tid = trace_id or new_trace_id()
        pending = await session.get_pending()
        if pending is None:
            await session.clear_pending()
            return await self.handle_chat_message(
                session.user_id, msg, conversation_id=conversation_id, trace_id=tid, soul_id=None
            )

        # 多轮补全：用本轮回复补全缺失的 slot
        if getattr(pending.duplicate, "table", None) == "_slot_fill":
            try:
                meta = json.loads(pending.duplicate.summary or "{}")
                missing = meta.get("missing") or []
            except Exception:
                missing = []
            ref = pending.parsed.date or date.today()
            merged = merge_slot_from_message(
                pending.parsed.intent,
                pending.parsed.payload or {},
                msg,
                ref,
            )
            pending.parsed.payload = merged
            still_missing = missing_slots(pending.parsed.intent, merged)
            if still_missing:
                new_dup = DuplicateHit(
                    existing_id=0,
                    table="_slot_fill",
                    same_content=False,
                    summary=json.dumps({"missing": still_missing}),
                )
                await session.set_pending(PendingConfirm(parsed=pending.parsed, duplicate=new_dup))
                reply = slot_fill_question(pending.parsed.intent, still_missing)
                await session.add_turn("assistant", reply, msg_type="slot_fill", soul_id=soul_id_int)
                return ChatResponse(
                    user_id=session.user_id,
                    type="slot_fill",
                    message=reply,
                    conversation_id=conversation_id,
                    parsed=parsed_dict(pending.parsed),
                    trace_id=tid,
                )
            await session.clear_pending()
            # 补全完成，走重复检测 + 落库
            dr = build_domain_record_and_inject_meal(
                pending.parsed, session.user_id, ref, await session.get_recent_history()
            )
            dup = await self._duplicate_checker.check(dr)
            if dup is not None:
                if dup.same_content:
                    reply = f"你已经记录过了哦 —— {dup.summary}，内容完全一样，无需重复记录。"
                    await session.add_turn("assistant", reply, msg_type="duplicate_same", soul_id=soul_id_int)
                    return ChatResponse(
                        user_id=session.user_id,
                        type="duplicate_same",
                        message=reply,
                        conversation_id=conversation_id,
                        parsed=parsed_dict(pending.parsed),
                        conflict={"existing_id": dup.existing_id, "table": dup.table, "summary": dup.summary},
                        trace_id=tid,
                    )
                new_pending = PendingConfirm(parsed=pending.parsed, duplicate=dup)
                await session.set_pending(new_pending)
                reply = (
                    f"检测到今天已有一条类似记录 —— {dup.summary}。\n"
                    "· 回复「确认」覆盖原记录\n· 回复「再记一条」保留原记录并新增这条\n· 回复「取消」放弃"
                )
                await session.add_turn("assistant", reply, msg_type="needs_confirm", soul_id=soul_id_int)
                return ChatResponse(
                    user_id=session.user_id,
                    type="needs_confirm",
                    message=reply,
                    conversation_id=conversation_id,
                    parsed=parsed_dict(pending.parsed),
                    conflict={"existing_id": dup.existing_id, "table": dup.table, "summary": dup.summary},
                    trace_id=tid,
                )
            # 补全后无重复：同样先确认再存
            confirm_save_dup = DuplicateHit(0, "_confirm_save", False, "")
            await session.set_pending(PendingConfirm(parsed=pending.parsed, duplicate=confirm_save_dup))
            detail = payload_summary(pending.parsed.intent, pending.parsed.payload or {})
            reply = (
                f"要帮你记下来吗？—— {intent_cn(pending.parsed.intent)}"
                + (f"（{detail}）" if detail else "")
                + "\n回复「确认」或「好的」保存，回复「取消」不保存。"
            )
            await session.add_turn("assistant", reply, msg_type="confirm_before_save", soul_id=soul_id_int)
            return ChatResponse(
                user_id=session.user_id,
                type="confirm_before_save",
                message=reply,
                conversation_id=conversation_id,
                parsed=parsed_dict(pending.parsed),
                trace_id=tid,
            )

        # 先确认再存：用户选择「确认」则落库，「取消」则不保存
        if getattr(pending.duplicate, "table", None) == "_confirm_save":
            if _is_confirm(msg):
                await session.clear_pending()
                resp = await self._save_and_reply(
                    session,
                    pending.parsed,
                    conversation_id,
                    replace_id=None,
                    trace_id=tid,
                    soul_id_int=soul_id_int,
                )
                # 若同时请求了计划且刚保存的是目标：追加计划预览
                try:
                    meta = json.loads(pending.duplicate.summary or "{}")
                    if meta.get("_also_request_plan") and pending.parsed.intent == IntentType.SET_GOAL and getattr(resp, "saved", None):
                        goal_id = (resp.saved or {}).get("id")
                        if goal_id:
                            plan_reply, plan_extra = await self._reply_plan_preview(session.user_id, {"goal_id": goal_id}, date.today())
                            if plan_extra.get("plan_preview"):
                                combined = (resp.message or "") + "\n\n" + plan_reply
                                return ChatResponse(
                                    user_id=resp.user_id,
                                    type=resp.type,
                                    message=combined,
                                    conversation_id=resp.conversation_id,
                                    parsed=resp.parsed,
                                    saved=resp.saved,
                                    extra={"plan_preview": plan_extra.get("plan_preview"), **(resp.extra or {})},
                                    trace_id=resp.trace_id,
                                )
                except Exception:
                    pass
                return resp
            if _is_cancel(msg):
                await session.clear_pending()
                reply = "好的，不保存了。"
                await session.add_turn("assistant", reply, msg_type="cancelled", soul_id=soul_id_int)
                return ChatResponse(
                    user_id=session.user_id,
                    type="cancelled",
                    message=reply,
                    conversation_id=conversation_id,
                    trace_id=tid,
                )
            # 既非确认也非取消：清掉待确认，按新消息重新处理
            await session.clear_pending()
            return await self.handle_chat_message(
                session.user_id, msg, conversation_id=conversation_id, trace_id=tid, soul_id=None
            )

        # 确认覆盖（重复且内容不同时的覆盖）
        if _is_confirm(msg):
            await session.clear_pending()
            replace_id = pending.duplicate.existing_id if pending.duplicate.existing_id else None
            return await self._save_and_reply(
                session,
                pending.parsed,
                conversation_id,
                replace_id=replace_id,
                trace_id=tid,
                soul_id_int=soul_id_int,
            )
        # 取消
        if _is_cancel(msg):
            await session.clear_pending()
            reply = "好的，已取消，之前的记录保持不变。"
            await session.add_turn("assistant", reply, msg_type="cancelled", soul_id=soul_id_int)
            return ChatResponse(
                user_id=session.user_id,
                type="cancelled",
                message=reply,
                conversation_id=conversation_id,
                trace_id=tid,
            )
        # 再记一条：保留原记录，新增当前这条（不传 replace_id）
        if _is_add_new(msg):
            await session.clear_pending()
            return await self._save_and_reply(
                session,
                pending.parsed,
                conversation_id,
                replace_id=None,
                trace_id=tid,
                soul_id_int=soul_id_int,
            )

        # 尝试理解为「修改待确认内容」：用 NLU 解析是否在改数字/餐次等，合并到 pending 后重新确认
        try:
            edit_list = await self._nlu_parser.parse(
                msg,
                reference_date=pending.parsed.date,
                history=await session.get_recent_history(),
            )
            edit_parsed = edit_list[0] if edit_list else None
            if edit_parsed and edit_parsed.intent == IntentType.EDIT_LAST and (edit_parsed.payload or {}).get("updates"):
                updates = edit_parsed.payload["updates"]
                if isinstance(pending.parsed.payload, dict):
                    pending.parsed.payload = dict(pending.parsed.payload)
                    pending.parsed.payload.update(updates)
                new_pending = PendingConfirm(parsed=pending.parsed, duplicate=pending.duplicate)
                await session.set_pending(new_pending)
                detail = payload_summary(pending.parsed.intent, pending.parsed.payload or {})
                reply = f"已按你的意思更新为：{detail}。确认覆盖、再记一条、还是取消？"
                await session.add_turn("assistant", reply, msg_type="needs_confirm", soul_id=soul_id_int)
                return ChatResponse(
                    user_id=session.user_id,
                    type="needs_confirm",
                    message=reply,
                    conversation_id=conversation_id,
                    parsed=parsed_dict(pending.parsed),
                    conflict={
                        "existing_id": pending.duplicate.existing_id,
                        "table": pending.duplicate.table,
                        "summary": pending.duplicate.summary,
                    },
                    trace_id=tid,
                )
        except Exception:
            pass

        # 其他：清掉 pending，按新消息重新走一遍流程
        await session.clear_pending()
        return await self.handle_chat_message(
            session.user_id, msg, conversation_id=conversation_id, trace_id=tid, soul_id=None
        )

    async def _save_and_reply(
        self,
        session: Any,
        parsed: ParsedRecord,
        conversation_id: int,
        replace_id: int | None = None,
        trace_id: str | None = None,
        soul_id_int: int | None = None,
    ) -> ChatResponse:
        tid = trace_id or new_trace_id()
        parsed.user_id = session.user_id
        result = await self._record_applier.apply(parsed, replace_id=replace_id)
        if result.get("ok"):
            log_chat_step(tid, session.user_id, "save", intent=parsed.intent.value, result=str(result.get("id")))
            action = "已覆盖旧记录并保存" if replace_id else "已记录"
            reply = f"✅ {action}：{intent_cn(parsed.intent)}"
            detail = payload_summary(parsed.intent, parsed.payload or {})
            if detail:
                reply += f"（{detail}）"
            msg_type = "confirmed" if replace_id else "saved"
            await session.add_turn(
                "assistant", reply, msg_type=msg_type, extra={"saved": result}, soul_id=soul_id_int
            )
            return ChatResponse(
                user_id=session.user_id,
                type=msg_type,
                message=reply,
                conversation_id=conversation_id,
                parsed=parsed_dict(parsed),
                saved=result,
                trace_id=tid,
            )
        log_chat_step(tid, session.user_id, "save", intent=parsed.intent.value, error=result.get("error"))
        reply = f"保存失败：{result.get('error', '未知错误')}"
        await session.add_turn("assistant", reply, msg_type="error", soul_id=soul_id_int)
        return ChatResponse(
            user_id=session.user_id,
            type="error",
            message=reply,
            conversation_id=conversation_id,
            parsed=parsed_dict(parsed),
            trace_id=tid,
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
    """INLUParser 的默认实现：委托给 domain nlu.parse_user_message（返回多意图列表）。"""

    async def parse(
        self,
        message: str,
        reference_date: Optional[date] = None,
        history: Optional[list] = None,
    ) -> list:
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
        soul_id: Optional[str] = None,
    ) -> tuple[str, Optional[int]]:
        from src.domain.interaction.chat.small_chat import small_chat_reply
        return await small_chat_reply(
            user_id=user_id,
            message=message,
            history=history,
            soul_id=soul_id,
        )


def create_chat_application_service() -> ChatApplicationService:
    """组合根：使用默认的 MySQL 适配器与 NLU/SmallChat/Query/EditDelete 实现创建 Chat 应用服务。"""
    record_applier = MySQLRecordApplier()
    duplicate_checker = MySQLDuplicateChecker()
    session_store = MySQLSessionStore()
    small_chat_runner = _DefaultSmallChatRunner()
    nlu_parser = _DefaultNluParser()
    query_runner = MySQLQueryRunner()
    edit_delete_runner = MySQLEditDeleteRunner()
    return ChatApplicationService(
        record_applier=record_applier,
        duplicate_checker=duplicate_checker,
        session_store=session_store,
        small_chat_runner=small_chat_runner,
        nlu_parser=nlu_parser,
        query_runner=query_runner,
        edit_delete_runner=edit_delete_runner,
    )
