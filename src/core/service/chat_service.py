"""
Chat 应用服务：人机交互的会话管理层。

职责边界：
- 会话管理（conversation / history / pending）
- 重复检测 → 确认/取消/再记一条
- slot 补全多轮（pending 状态机）
- 调用领域层执行实际操作（落库 / 查询 / 编辑删除 / 计划生成）
- 不做任何 NLP 工作 —— NLU、意图路由、小聊天均委托给交互层 (interaction)
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Optional

from src.core.audit import new_trace_id, log_chat_step

from src.domain.interaction.agents import run_interaction_agent
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
    merge_from_nlu_result,
)
from src.domain.interaction.chat.response import ChatResponse
from src.domain.interaction.nlu import parse_user_message

from src.infra.persistence import (
    MySQLRecordApplier,
    MySQLDuplicateChecker,
    MySQLSessionStore,
    PendingConfirm,
    MySQLQueryRunner,
    MySQLEditDeleteRunner,
)
from src.infra.persistence.mysql_soul_repository import get_soul_id_by_slug


# ---------------------------------------------------------------------------
# 辅助：确认/取消/再记一条 判断
# ---------------------------------------------------------------------------

def _is_confirm(msg: str) -> bool:
    t = msg.strip().lower()
    if t in ("确认", "是", "是的", "对", "好", "好的", "替换", "覆盖", "yes", "y", "ok", "1"):
        return True
    if "覆盖" in t or "替换" in t or "确认" in t or "那就" in t and ("好" in t or "吧" in t):
        return True
    return False


def _is_cancel(msg: str) -> bool:
    t = msg.strip().lower()
    if t in ("取消", "不", "不要", "算了", "no", "n", "cancel", "0"):
        return True
    if "算了" in t or "不用了" in t or "不要了" in t or "取消" in t:
        return True
    return False


def _is_add_new(msg: str) -> bool:
    t = msg.strip()
    return "再记一条" in t or ("保留" in t and "新增" in t) or "不覆盖" in t and "新" in t


# ---------------------------------------------------------------------------
# 应用服务
# ---------------------------------------------------------------------------

class ChatApplicationService:
    """
    聊天应用服务：管理会话状态，将用户消息委托给交互层做 NLP，
    再根据结果执行重复检测、确认流、实际落库等应用层逻辑。
    """

    def __init__(
        self,
        record_applier: Any,       # IRecordApplier
        duplicate_checker: Any,    # IDuplicateChecker
        session_store: Any,        # ISessionStore
        query_runner: Any,         # IQueryRunner
        edit_delete_runner: Any,   # IEditDeleteRunner
    ):
        self._record_applier = record_applier
        self._duplicate_checker = duplicate_checker
        self._session_store = session_store
        self._query_runner = query_runner
        self._edit_delete_runner = edit_delete_runner

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

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

        # 有待确认状态时，走 pending 处理
        if await session.has_pending():
            return await self._handle_pending(
                session, msg, conv_id, ref=ref,
                trace_id=tid, soul_id=soul_id, soul_id_int=soul_id_int,
            )

        # --- 委托交互层做全部 NLP ---
        try:
            nlp_result = await run_interaction_agent(
                user_id=user_id,
                message=msg,
                history=history,
                reference_date=ref,
                soul_id=soul_id,
                trace_id=tid,
            )
        except Exception as e:
            log_chat_step(tid, user_id, "nlu", error=str(e))
            reply = f"抱歉，解析时出了问题：{e}"
            await session.add_turn("assistant", reply, msg_type="error", soul_id=soul_id_int)
            return ChatResponse(
                user_id=user_id, type="error", message=reply,
                conversation_id=conv_id, trace_id=tid,
            )

        log_chat_step(
            tid, user_id, "nlu",
            intent=(nlp_result.parsed or {}).get("intent"),
            payload=(nlp_result.parsed or {}).get("payload"),
        )

        # --- 根据交互层返回的 type 分发到应用层逻辑 ---
        return await self._dispatch(
            nlp_result, session, conv_id, ref,
            trace_id=tid, soul_id=soul_id, soul_id_int=soul_id_int,
        )

    # ------------------------------------------------------------------
    # 分发交互层结果
    # ------------------------------------------------------------------

    async def _dispatch(
        self,
        nlp_result: ChatResponse,
        session: Any,
        conv_id: int,
        ref: date,
        trace_id: str = "",
        soul_id: str | None = None,
        soul_id_int: int | None = None,
    ) -> ChatResponse:
        rtype = nlp_result.type
        user_id = nlp_result.user_id

        # 小聊天：直接透传
        if rtype == "chat_only":
            await session.add_turn(
                "assistant", nlp_result.message, msg_type="chat_only",
                extra={"sticker_id": nlp_result.sticker_id} if nlp_result.sticker_id is not None else None,
                soul_id=soul_id_int,
            )
            return ChatResponse(
                user_id=user_id, type="chat_only",
                message=nlp_result.message, conversation_id=conv_id,
                sticker_id=nlp_result.sticker_id, trace_id=trace_id,
            )

        # slot 补全：进入 pending 状态
        if rtype == "needs_slot_fill":
            parsed = self._rebuild_parsed(nlp_result)
            missing = (nlp_result.extra or {}).get("missing_slots", [])
            dup = DuplicateHit(existing_id=0, table="_slot_fill", same_content=False,
                               summary=json.dumps({"missing": missing}))
            await session.set_pending(PendingConfirm(parsed=parsed, duplicate=dup))
            log_chat_step(trace_id, user_id, "slot_fill",
                          intent=(nlp_result.parsed or {}).get("intent"),
                          payload={"missing": missing})
            await session.add_turn("assistant", nlp_result.message, msg_type="slot_fill", soul_id=soul_id_int)
            return ChatResponse(
                user_id=user_id, type="slot_fill",
                message=nlp_result.message, conversation_id=conv_id,
                parsed=nlp_result.parsed, trace_id=trace_id,
            )

        # 记录类：就绪 → 重复检测 → 确认
        if rtype == "ready_to_save":
            parsed = self._rebuild_parsed(nlp_result)
            has_request_plan = (nlp_result.extra or {}).get("has_request_plan", False)
            return await self._confirm_before_save(
                session, parsed, conv_id, ref,
                has_request_plan=has_request_plan,
                trace_id=trace_id, soul_id_int=soul_id_int,
            )

        # 查询
        if rtype == "query":
            extra = nlp_result.extra or {}
            q_result = await self._query_runner.run(
                user_id=user_id,
                intent=extra.get("query_intent", ""),
                payload=extra.get("query_payload") or {},
                reference_date=ref,
            )
            try:
                intent_enum = IntentType(extra.get("query_intent", "unknown"))
            except ValueError:
                intent_enum = IntentType.UNKNOWN
            reply = format_query_reply(intent_enum, q_result)
            log_chat_step(trace_id, user_id, "query",
                          intent=extra.get("query_intent"), result=q_result.get("summary"))
            await session.add_turn("assistant", reply, msg_type="query", soul_id=soul_id_int)
            return ChatResponse(
                user_id=user_id, type="query", message=reply,
                conversation_id=conv_id, parsed=nlp_result.parsed, trace_id=trace_id,
            )

        # 计划预览 → 设 pending 等待用户确认保存
        if rtype == "plan_preview":
            plan_mode = ((nlp_result.extra or {}).get("plan_mode") or "build").strip().lower()
            if plan_mode == "view":
                view_reply, view_extra = await self._reply_existing_plan(user_id)
                await session.add_turn(
                    "assistant",
                    view_reply,
                    msg_type="plan_view",
                    extra=view_extra,
                    soul_id=soul_id_int,
                )
                return ChatResponse(
                    user_id=user_id,
                    type="plan_view",
                    message=view_reply,
                    conversation_id=conv_id,
                    parsed=nlp_result.parsed,
                    extra=view_extra,
                    trace_id=trace_id,
                )

            plan_reply, plan_extra = await self._reply_plan_preview(
                user_id, (nlp_result.extra or {}), ref,
            )
            if plan_extra.get("plan_preview"):
                plan_dup = DuplicateHit(
                    existing_id=0, table="_plan_confirm", same_content=False,
                    summary=json.dumps({
                        "plan_preview": plan_extra["plan_preview"],
                        "goal_id": plan_extra["plan_preview"].get("goal_id"),
                    }),
                )
                dummy_parsed = ParsedRecord(
                    intent=IntentType.REQUEST_PLAN, date=ref,
                    payload=plan_extra.get("plan_preview") or {},
                    raw_message="", user_id=user_id,
                )
                await session.set_pending(PendingConfirm(parsed=dummy_parsed, duplicate=plan_dup))
                plan_reply += "\n\n回复「确认」保存此计划，回复「取消」放弃。"
            await session.add_turn("assistant", plan_reply, msg_type="plan_preview",
                                   extra=plan_extra, soul_id=soul_id_int)
            return ChatResponse(
                user_id=user_id, type="plan_preview", message=plan_reply,
                conversation_id=conv_id, parsed=nlp_result.parsed,
                extra=plan_extra, trace_id=trace_id,
            )

        # 编辑
        if rtype == "edit":
            extra = nlp_result.extra or {}
            edit_result = await self._edit_delete_runner.edit_last(
                user_id=user_id,
                record_type=extra.get("record_type"),
                updates=extra.get("updates") or {},
                reference_date=ref,
            )
            reply = (f"已修改上一条记录（id={edit_result.get('id')}）。"
                     if edit_result.get("ok")
                     else f"修改失败：{edit_result.get('error', '未知错误')}")
            log_chat_step(trace_id, user_id, "edit_last",
                          result="ok" if edit_result.get("ok") else edit_result.get("error"))
            await session.add_turn("assistant", reply, msg_type="edit_last", soul_id=soul_id_int)
            return ChatResponse(
                user_id=user_id, type="edit_last", message=reply,
                conversation_id=conv_id, parsed=nlp_result.parsed, trace_id=trace_id,
            )

        # 删除
        if rtype == "delete":
            parsed = self._rebuild_parsed(nlp_result)
            payload = parsed.payload or {}
            record_type = ((nlp_result.extra or {}).get("record_type") or payload.get("record_type") or "").strip().lower()
            record_id = (nlp_result.extra or {}).get("record_id") or payload.get("record_id") or payload.get("plan_id")
            if record_type in ("plan", "training-plans", "training_plans"):
                record_type = "training_plan"
            if not record_type:
                if record_id:
                    record_type = "training_plan"
            if not record_type:
                reply = (
                    "我可以帮你删除记录，但还不确定要删哪一类。\n"
                    "请补充：workout / meal / body_metric / goal / training_plan，"
                    "或直接说「删除计划 id=2」。"
                )
                await session.add_turn("assistant", reply, msg_type="need_delete_target", soul_id=soul_id_int)
                return ChatResponse(
                    user_id=user_id, type="need_delete_target", message=reply,
                    conversation_id=conv_id, parsed=nlp_result.parsed, trace_id=trace_id,
                )
            del_dup = DuplicateHit(
                existing_id=0, table="_confirm_delete", same_content=False,
                summary=json.dumps({
                    "record_type": record_type,
                    "record_id": record_id,
                    "date": str(payload.get("date") or ""),
                    "meal_type": payload.get("meal_type"),
                    "workout_type": payload.get("workout_type"),
                }),
            )
            await session.set_pending(PendingConfirm(parsed=parsed, duplicate=del_dup))
            target = f"{record_type}（id={record_id}）" if record_id else record_type
            reply = (
                f"收到，你要删除的是：{target}。\n"
                "回复「确认」执行删除，回复「取消」放弃。"
            )
            await session.add_turn("assistant", reply, msg_type="confirm_delete", soul_id=soul_id_int)
            return ChatResponse(
                user_id=user_id, type="confirm_delete", message=reply,
                conversation_id=conv_id, parsed=nlp_result.parsed, trace_id=trace_id,
            )

        # fallback: 不认识的 type，当 chat_only 处理
        await session.add_turn("assistant", nlp_result.message, msg_type=rtype, soul_id=soul_id_int)
        return ChatResponse(
            user_id=user_id, type=rtype, message=nlp_result.message,
            conversation_id=conv_id, trace_id=trace_id,
        )

    # ------------------------------------------------------------------
    # 记录类：重复检测 → 确认
    # ------------------------------------------------------------------

    async def _confirm_before_save(
        self,
        session: Any,
        parsed: ParsedRecord,
        conv_id: int,
        ref: date,
        has_request_plan: bool = False,
        trace_id: str = "",
        soul_id_int: int | None = None,
    ) -> ChatResponse:
        user_id = parsed.user_id or session.user_id
        history = await session.get_recent_history()
        dr = build_domain_record_and_inject_meal(parsed, user_id, ref, history)
        dup = await self._duplicate_checker.check(dr)

        if dup is not None:
            if dup.same_content:
                reply = f"你已经记录过了哦 —— {dup.summary}，内容完全一样，无需重复记录。"
                await session.add_turn("assistant", reply, msg_type="duplicate_same", soul_id=soul_id_int)
                log_chat_step(trace_id, user_id, "duplicate_same",
                              intent=parsed.intent.value, result=dup.summary)
                return ChatResponse(
                    user_id=user_id, type="duplicate_same", message=reply,
                    conversation_id=conv_id, parsed=parsed_dict(parsed),
                    conflict={"existing_id": dup.existing_id, "table": dup.table, "summary": dup.summary},
                    trace_id=trace_id,
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
            log_chat_step(trace_id, user_id, "needs_confirm",
                          intent=parsed.intent.value, result=dup.summary)
            return ChatResponse(
                user_id=user_id, type="needs_confirm", message=reply,
                conversation_id=conv_id, parsed=parsed_dict(parsed),
                conflict={"existing_id": dup.existing_id, "table": dup.table, "summary": dup.summary},
                trace_id=trace_id,
            )

        # 无重复：先确认再存
        confirm_summary = json.dumps({"_also_request_plan": True}) if has_request_plan else ""
        confirm_dup = DuplicateHit(existing_id=0, table="_confirm_save",
                                   same_content=False, summary=confirm_summary)
        await session.set_pending(PendingConfirm(parsed=parsed, duplicate=confirm_dup))
        detail = payload_summary(parsed.intent, parsed.payload or {})
        reply = (
            f"要帮你记下来吗？—— {intent_cn(parsed.intent)}"
            + (f"（{detail}）" if detail else "")
            + "\n回复「确认」或「好的」保存，回复「取消」不保存。"
        )
        if has_request_plan:
            reply += "\n确认后我会为你生成训练计划预览。"
        await session.add_turn("assistant", reply, msg_type="confirm_before_save", soul_id=soul_id_int)
        log_chat_step(trace_id, user_id, "confirm_before_save", intent=parsed.intent.value)
        return ChatResponse(
            user_id=user_id, type="confirm_before_save", message=reply,
            conversation_id=conv_id, parsed=parsed_dict(parsed), trace_id=trace_id,
        )

    # ------------------------------------------------------------------
    # Pending 状态处理
    # ------------------------------------------------------------------

    async def _handle_pending(
        self,
        session: Any,
        msg: str,
        conversation_id: int,
        ref: date = None,
        trace_id: str | None = None,
        soul_id: str | None = None,
        soul_id_int: int | None = None,
    ) -> ChatResponse:
        tid = trace_id or new_trace_id()
        ref = ref or date.today()
        pending = await session.get_pending()
        if pending is None:
            await session.clear_pending()
            return await self.handle_chat_message(
                session.user_id, msg, conversation_id=conversation_id,
                trace_id=tid, soul_id=soul_id,
            )

        # slot 补全
        if getattr(pending.duplicate, "table", None) == "_slot_fill":
            return await self._handle_slot_fill(
                session, pending, msg, conversation_id, ref,
                trace_id=tid, soul_id=soul_id, soul_id_int=soul_id_int,
            )

        # 计划确认保存
        if getattr(pending.duplicate, "table", None) == "_plan_confirm":
            return await self._handle_plan_confirm(
                session, pending, msg, conversation_id, ref,
                trace_id=tid, soul_id=soul_id, soul_id_int=soul_id_int,
            )

        # 先确认再存
        if getattr(pending.duplicate, "table", None) == "_confirm_save":
            return await self._handle_confirm_save(
                session, pending, msg, conversation_id, ref,
                trace_id=tid, soul_id=soul_id, soul_id_int=soul_id_int,
            )
        if getattr(pending.duplicate, "table", None) == "_confirm_delete":
            return await self._handle_confirm_delete(
                session, pending, msg, conversation_id, ref,
                trace_id=tid, soul_id=soul_id, soul_id_int=soul_id_int,
            )

        # 确认覆盖（重复且内容不同）
        if _is_confirm(msg):
            await session.clear_pending()
            replace_id = pending.duplicate.existing_id if pending.duplicate.existing_id else None
            return await self._save_and_reply(
                session, pending.parsed, conversation_id,
                replace_id=replace_id, trace_id=tid, soul_id_int=soul_id_int,
            )
        if _is_cancel(msg):
            await session.clear_pending()
            reply = "好的，已取消，之前的记录保持不变。"
            await session.add_turn("assistant", reply, msg_type="cancelled", soul_id=soul_id_int)
            return ChatResponse(
                user_id=session.user_id, type="cancelled", message=reply,
                conversation_id=conversation_id, trace_id=tid,
            )
        if _is_add_new(msg):
            await session.clear_pending()
            return await self._save_and_reply(
                session, pending.parsed, conversation_id,
                replace_id=None, trace_id=tid, soul_id_int=soul_id_int,
            )

        # 尝试理解为修改待确认内容（唯一需要再调一次 NLU 的地方）
        try:
            edit_list = await parse_user_message(
                msg,
                reference_date=pending.parsed.date,
                history=await session.get_recent_history(),
                trace_id=tid,
            )
            edit_parsed = edit_list[0] if edit_list else None
            if (edit_parsed
                    and edit_parsed.intent == IntentType.EDIT_LAST
                    and (edit_parsed.payload or {}).get("updates")):
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
                    user_id=session.user_id, type="needs_confirm", message=reply,
                    conversation_id=conversation_id, parsed=parsed_dict(pending.parsed),
                    conflict={
                        "existing_id": pending.duplicate.existing_id,
                        "table": pending.duplicate.table,
                        "summary": pending.duplicate.summary,
                    },
                    trace_id=tid,
                )
        except Exception:
            pass

        # 既不是确认/取消/修改：清掉 pending，当新消息处理
        await session.clear_pending()
        return await self.handle_chat_message(
            session.user_id, msg, conversation_id=conversation_id,
            trace_id=tid, soul_id=soul_id,
        )

    # ------------------------------------------------------------------
    # slot 补全子流程
    # ------------------------------------------------------------------

    async def _handle_slot_fill(
        self,
        session: Any,
        pending: Any,
        msg: str,
        conversation_id: int,
        ref: date,
        trace_id: str = "",
        soul_id: str | None = None,
        soul_id_int: int | None = None,
    ) -> ChatResponse:
        # 允许用户在 slot fill 过程中取消
        if _is_cancel(msg):
            await session.clear_pending()
            reply = "好的，已取消记录。"
            await session.add_turn("assistant", reply, msg_type="cancelled", soul_id=soul_id_int)
            return ChatResponse(
                user_id=session.user_id, type="cancelled", message=reply,
                conversation_id=conversation_id, trace_id=trace_id,
            )

        merged = merge_slot_from_message(
            pending.parsed.intent, pending.parsed.payload or {}, msg, ref,
        )
        still_missing = missing_slots(pending.parsed.intent, merged)

        # 简单合并仍缺字段时，尝试 NLU 重解析用户回复
        if still_missing:
            try:
                nlu_results = await parse_user_message(msg, reference_date=ref)
                if nlu_results:
                    nlu_payload = nlu_results[0].payload
                    merged = merge_from_nlu_result(
                        pending.parsed.intent, merged, nlu_payload,
                    )
                    still_missing = missing_slots(pending.parsed.intent, merged)
            except Exception:
                pass

        pending.parsed.payload = merged

        if still_missing:
            new_dup = DuplicateHit(
                existing_id=0, table="_slot_fill", same_content=False,
                summary=json.dumps({"missing": still_missing}),
            )
            await session.set_pending(PendingConfirm(parsed=pending.parsed, duplicate=new_dup))
            reply = slot_fill_question(pending.parsed.intent, still_missing)
            await session.add_turn("assistant", reply, msg_type="slot_fill", soul_id=soul_id_int)
            return ChatResponse(
                user_id=session.user_id, type="slot_fill", message=reply,
                conversation_id=conversation_id, parsed=parsed_dict(pending.parsed),
                trace_id=trace_id,
            )

        # 补全完毕 → 重复检测 → 确认
        await session.clear_pending()
        return await self._confirm_before_save(
            session, pending.parsed, conversation_id, ref,
            trace_id=trace_id, soul_id_int=soul_id_int,
        )

    # ------------------------------------------------------------------
    # confirm_save 子流程
    # ------------------------------------------------------------------

    async def _handle_confirm_save(
        self,
        session: Any,
        pending: Any,
        msg: str,
        conversation_id: int,
        ref: date,
        trace_id: str = "",
        soul_id: str | None = None,
        soul_id_int: int | None = None,
    ) -> ChatResponse:
        if _is_confirm(msg):
            await session.clear_pending()
            resp = await self._save_and_reply(
                session, pending.parsed, conversation_id,
                replace_id=None, trace_id=trace_id, soul_id_int=soul_id_int,
            )
            # 若同时请求了计划且刚保存的是目标：追加计划预览
            try:
                meta = json.loads(pending.duplicate.summary or "{}")
                if (meta.get("_also_request_plan")
                        and pending.parsed.intent == IntentType.SET_GOAL
                        and getattr(resp, "saved", None)):
                    goal_id = (resp.saved or {}).get("id")
                    if goal_id:
                        plan_reply, plan_extra = await self._reply_plan_preview(
                            session.user_id, {"goal_id": goal_id}, ref,
                        )
                        if plan_extra.get("plan_preview"):
                            plan_dup = DuplicateHit(
                                existing_id=0,
                                table="_plan_confirm",
                                same_content=False,
                                summary=json.dumps({
                                    "plan_preview": plan_extra["plan_preview"],
                                    "goal_id": plan_extra["plan_preview"].get("goal_id") or goal_id,
                                }),
                            )
                            dummy_parsed = ParsedRecord(
                                intent=IntentType.REQUEST_PLAN,
                                date=ref,
                                payload=plan_extra.get("plan_preview") or {},
                                raw_message="",
                                user_id=session.user_id,
                            )
                            await session.set_pending(
                                PendingConfirm(parsed=dummy_parsed, duplicate=plan_dup)
                            )
                            combined = (
                                (resp.message or "")
                                + "\n\n"
                                + plan_reply
                                + "\n\n回复「确认」保存此计划，回复「取消」放弃。"
                            )
                            return ChatResponse(
                                user_id=resp.user_id, type="plan_preview", message=combined,
                                conversation_id=resp.conversation_id, parsed=resp.parsed,
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
                user_id=session.user_id, type="cancelled", message=reply,
                conversation_id=conversation_id, trace_id=trace_id,
            )

        # 既非确认也非取消：清掉待确认，按新消息重新处理
        await session.clear_pending()
        return await self.handle_chat_message(
            session.user_id, msg, conversation_id=conversation_id,
            trace_id=trace_id, soul_id=soul_id,
        )

    async def _handle_confirm_delete(
        self,
        session: Any,
        pending: Any,
        msg: str,
        conversation_id: int,
        ref: date,
        trace_id: str = "",
        soul_id: str | None = None,
        soul_id_int: int | None = None,
    ) -> ChatResponse:
        if _is_cancel(msg):
            await session.clear_pending()
            reply = "好的，不删除了。"
            await session.add_turn("assistant", reply, msg_type="cancelled", soul_id=soul_id_int)
            return ChatResponse(
                user_id=session.user_id, type="cancelled", message=reply,
                conversation_id=conversation_id, trace_id=trace_id,
            )

        if not _is_confirm(msg):
            await session.clear_pending()
            return await self.handle_chat_message(
                session.user_id, msg, conversation_id=conversation_id,
                trace_id=trace_id, soul_id=soul_id,
            )

        await session.clear_pending()
        try:
            meta = json.loads(pending.duplicate.summary or "{}")
        except Exception:
            meta = {}
        payload = pending.parsed.payload or {}
        record_type = (meta.get("record_type") or payload.get("record_type") or "").strip().lower()
        record_id = meta.get("record_id") or payload.get("record_id") or payload.get("plan_id")
        if record_type in ("plan", "training-plans", "training_plans"):
            record_type = "training_plan"

        date_val = pending.parsed.date or ref
        if isinstance(payload.get("date"), str):
            try:
                date_val = date.fromisoformat(payload["date"][:10])
            except Exception:
                pass

        del_result = await self._edit_delete_runner.delete_record(
            user_id=session.user_id,
            record_type=record_type,
            record_id=record_id,
            date_arg=date_val,
            meal_type=payload.get("meal_type"),
            workout_type=payload.get("workout_type"),
        )
        if del_result.get("ok"):
            reply = f"已删除 {record_type} 记录（id={del_result.get('id')}）。"
        else:
            reply = f"删除失败：{del_result.get('error', '未知错误')}"
        log_chat_step(trace_id, session.user_id, "delete_record",
                      result="ok" if del_result.get("ok") else del_result.get("error"))
        await session.add_turn("assistant", reply, msg_type="delete_record", soul_id=soul_id_int)
        return ChatResponse(
            user_id=session.user_id, type="delete_record", message=reply,
            conversation_id=conversation_id, trace_id=trace_id,
        )

    # ------------------------------------------------------------------
    # 计划确认保存子流程
    # ------------------------------------------------------------------

    async def _handle_plan_confirm(
        self,
        session: Any,
        pending: Any,
        msg: str,
        conversation_id: int,
        ref: date,
        trace_id: str = "",
        soul_id: str | None = None,
        soul_id_int: int | None = None,
    ) -> ChatResponse:
        if _is_confirm(msg):
            await session.clear_pending()
            try:
                meta = json.loads(pending.duplicate.summary or "{}")
            except Exception:
                meta = {}
            plan_preview = meta.get("plan_preview") or (pending.parsed.payload if pending.parsed else {})
            goal_id = meta.get("goal_id") or (plan_preview.get("goal_id") if plan_preview else None)
            if not goal_id or not plan_preview:
                reply = "计划数据丢失，请重新生成计划。"
                await session.add_turn("assistant", reply, msg_type="error", soul_id=soul_id_int)
                return ChatResponse(
                    user_id=session.user_id, type="error", message=reply,
                    conversation_id=conversation_id, trace_id=trace_id,
                )
            try:
                from src.infra.database.mysql import async_mysql_pool
                from src.domain.interaction.record.training_plan import save_plan

                async with async_mysql_pool.session() as db_session:
                    tp, count = await save_plan(db_session, session.user_id, goal_id, plan_preview)
                    await db_session.commit()
                reply = f"训练计划已保存！共 {count} 个训练日，计划 ID={tp.id}。加油！"
                log_chat_step(trace_id, session.user_id, "plan_saved",
                              result=f"plan_id={tp.id}, sessions={count}")
            except Exception as e:
                reply = f"计划保存失败：{e}"
                log_chat_step(trace_id, session.user_id, "plan_save_error", error=str(e))
                await session.add_turn("assistant", reply, msg_type="error", soul_id=soul_id_int)
                return ChatResponse(
                    user_id=session.user_id, type="error", message=reply,
                    conversation_id=conversation_id, trace_id=trace_id,
                )
            await session.add_turn("assistant", reply, msg_type="plan_saved", soul_id=soul_id_int)
            return ChatResponse(
                user_id=session.user_id, type="plan_saved", message=reply,
                conversation_id=conversation_id, trace_id=trace_id,
            )

        if _is_cancel(msg):
            await session.clear_pending()
            reply = "好的，计划已放弃，有需要再告诉我。"
            await session.add_turn("assistant", reply, msg_type="cancelled", soul_id=soul_id_int)
            return ChatResponse(
                user_id=session.user_id, type="cancelled", message=reply,
                conversation_id=conversation_id, trace_id=trace_id,
            )

        # 既非确认也非取消：清掉 pending，按新消息处理
        await session.clear_pending()
        return await self.handle_chat_message(
            session.user_id, msg, conversation_id=conversation_id,
            trace_id=trace_id, soul_id=soul_id,
        )

    # ------------------------------------------------------------------
    # 落库 + 回复
    # ------------------------------------------------------------------

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
            log_chat_step(tid, session.user_id, "save",
                          intent=parsed.intent.value, result=str(result.get("id")))
            action = "已覆盖旧记录并保存" if replace_id else "已记录"
            reply = f"{action}：{intent_cn(parsed.intent)}"
            detail = payload_summary(parsed.intent, parsed.payload or {})
            if detail:
                reply += f"（{detail}）"
            msg_type = "confirmed" if replace_id else "saved"
            await session.add_turn(
                "assistant", reply, msg_type=msg_type, extra={"saved": result}, soul_id=soul_id_int
            )
            return ChatResponse(
                user_id=session.user_id, type=msg_type, message=reply,
                conversation_id=conversation_id, parsed=parsed_dict(parsed),
                saved=result, trace_id=tid,
            )
        log_chat_step(tid, session.user_id, "save",
                      intent=parsed.intent.value, error=result.get("error"))
        reply = f"保存失败：{result.get('error', '未知错误')}"
        await session.add_turn("assistant", reply, msg_type="error", soul_id=soul_id_int)
        return ChatResponse(
            user_id=session.user_id, type="error", message=reply,
            conversation_id=conversation_id, parsed=parsed_dict(parsed), trace_id=tid,
        )

    # ------------------------------------------------------------------
    # 计划预览
    # ------------------------------------------------------------------

    async def _reply_plan_preview(
        self,
        user_id: str,
        payload: dict,
        ref: date,
    ) -> tuple[str, dict]:
        from sqlalchemy import select
        from src.infra.database.mysql import async_mysql_pool, Goal
        from src.domain.interaction.record.training_plan import build_plan_preview

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
        return format_plan_preview_message(preview), {
            "plan_preview": preview,
            "plan_requires_confirm": True,
        }

    async def _reply_existing_plan(self, user_id: str) -> tuple[str, dict]:
        from sqlalchemy import select, desc
        from src.infra.database.mysql import async_mysql_pool, TrainingPlan

        async with async_mysql_pool.session() as session:
            row = await session.execute(
                select(TrainingPlan)
                .where(TrainingPlan.user_id == user_id, TrainingPlan.status == "active")
                .order_by(desc(TrainingPlan.updated_at), desc(TrainingPlan.id))
                .limit(1)
            )
            plan = row.scalars().first()

        if not plan:
            return "你还没有已保存的训练计划。可以先说「帮我制定计划」。", {
                "plan_requires_confirm": False
            }

        payload = plan.plan if isinstance(plan.plan, dict) else {}
        if not payload:
            return "找到一条训练计划，但内容为空。你可以说「帮我制定计划」重新生成。", {
                "plan_requires_confirm": False
            }
        title = payload.get("title") or plan.title or "训练计划"
        payload.setdefault("title", title)
        msg = f"这是你当前已保存的训练计划（计划 ID={plan.id}）："
        return msg, {
            "plan_preview": payload,
            "plan_id": plan.id,
            "plan_requires_confirm": False,
        }

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _rebuild_parsed(nlp_result: ChatResponse) -> ParsedRecord:
        """从交互层返回的 ChatResponse.parsed dict 重建 ParsedRecord 对象。"""
        p = nlp_result.parsed or {}
        return ParsedRecord(
            intent=IntentType(p.get("intent", "unknown")),
            date=date.fromisoformat(p["date"]) if p.get("date") else None,
            payload=p.get("payload"),
            raw_message=p.get("raw_message", ""),
            user_id=nlp_result.user_id,
        )

    # ------------------------------------------------------------------
    # 会话代理方法（供路由层直接使用）
    # ------------------------------------------------------------------

    async def get_or_create_conversation(
        self, user_id: str, conversation_id: Optional[int] = None,
    ) -> int:
        return await self._session_store.get_or_create_conversation(user_id, conversation_id)

    def get_user_session(
        self, user_id: str, conversation_id: Optional[int] = None,
    ) -> Any:
        return self._session_store.get_user_session(user_id, conversation_id)

    async def get_latest_conversation_id(self, user_id: str) -> Optional[int]:
        return await self._session_store.get_latest_conversation_id(user_id)

    async def conversation_belongs_to_user(
        self, user_id: str, conversation_id: int,
    ) -> bool:
        return await self._session_store.conversation_belongs_to_user(user_id, conversation_id)


# ---------------------------------------------------------------------------
# 组合根
# ---------------------------------------------------------------------------

def create_chat_application_service() -> ChatApplicationService:
    """使用默认的 MySQL 适配器创建 Chat 应用服务。"""
    return ChatApplicationService(
        record_applier=MySQLRecordApplier(),
        duplicate_checker=MySQLDuplicateChecker(),
        session_store=MySQLSessionStore(),
        query_runner=MySQLQueryRunner(),
        edit_delete_runner=MySQLEditDeleteRunner(),
    )
