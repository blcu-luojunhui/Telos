"""
交互层主入口：NLU 解析 → 意图路由 → 返回结构化结果。

职责边界：
- 本模块负责所有 NLP 工作：NLU 解析、意图路由、小聊天、slot 补全检测
- 不负责：会话管理、重复检测、确认流、实际落库（这些由 chat_service 处理）
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional, Sequence

from src.domain.interaction.schemas import IntentType, ParsedRecord
from src.domain.interaction.chat.response import ChatResponse
from src.domain.interaction.chat.display import (
    parsed_dict,
    intent_cn,
    payload_summary,
)
from src.domain.interaction.chat.slot_fill import (
    missing_slots,
    slot_fill_question,
)
from ..chains.nlu_chain import parse_user_message
from ..chains.small_chat_chain import small_chat_reply


_RECORD_INTENTS = {
    IntentType.RECORD_WORKOUT,
    IntentType.RECORD_MEAL,
    IntentType.RECORD_BODY_METRIC,
    IntentType.SET_GOAL,
    IntentType.RECORD_STATUS,
}

_QUERY_INTENTS = {
    IntentType.QUERY_WORKOUT,
    IntentType.QUERY_MEAL,
    IntentType.QUERY_BODY_METRIC,
    IntentType.QUERY_SUMMARY,
}

_INTENT_PRIORITY = {
    IntentType.DELETE_RECORD: 100,
    IntentType.EDIT_LAST: 95,
    IntentType.REQUEST_PLAN: 90,
    IntentType.SET_GOAL: 85,
    IntentType.RECORD_WORKOUT: 80,
    IntentType.RECORD_MEAL: 80,
    IntentType.RECORD_BODY_METRIC: 80,
    IntentType.RECORD_STATUS: 80,
    IntentType.QUERY_WORKOUT: 70,
    IntentType.QUERY_MEAL: 70,
    IntentType.QUERY_BODY_METRIC: 70,
    IntentType.QUERY_SUMMARY: 70,
    IntentType.UNKNOWN: 0,
}


def _pick_primary_intent(records: Sequence[ParsedRecord]) -> ParsedRecord:
    """
    统一主意图选择策略：
    - 删除/编辑优先于记录和查询（避免“删计划id=2”被误当普通聊天）
    - 目标与请求计划优先于一般记录
    - UNKNOWN 最低
    """
    if not records:
        raise ValueError("records must not be empty")
    return max(records, key=lambda r: _INTENT_PRIORITY.get(r.intent, 1))


async def run_interaction_agent(
    user_id: str,
    message: str,
    history: Optional[Sequence[dict]] = None,
    reference_date: Optional[date] = None,
    soul_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> ChatResponse:
    """
    交互层唯一入口：接收用户消息，返回 NLP 理解结果。

    返回的 ChatResponse.type 含义：
    - "chat_only"      : NLU 未识别结构化意图，已生成自然语言回复
    - "ready_to_save"  : 记录类意图已解析完毕、slot 齐全，等待应用层保存
    - "needs_slot_fill": 记录类意图缺必填字段，message 为追问话术
    - "query"          : 查询类意图，extra 含 query_intent / query_payload
    - "plan_preview"   : 要求生成训练计划
    - "edit"           : 修改上一条记录
    - "delete"         : 删除记录

    应用层 (chat_service) 拿到结果后，负责：
    - 会话/历史管理
    - 重复检测与确认流
    - 调用 apply_parsed_record / query_runner / edit_delete_runner 执行实际操作
    """
    ref = reference_date or date.today()

    llm_metrics: dict[str, Any] = {}

    parsed_list = await parse_user_message(
        message=message,
        reference_date=ref,
        history=history,
        trace_id=trace_id,
        metrics=llm_metrics,
    )

    if not parsed_list:
        parsed_list = [
            ParsedRecord(
                intent=IntentType.UNKNOWN,
                date=ref,
                payload={},
                raw_message=message.strip(),
            )
        ]

    primary = _pick_primary_intent(parsed_list)
    primary.user_id = user_id

    has_request_plan = any(p.intent == IntentType.REQUEST_PLAN for p in parsed_list)

    resp = await _route_intent(
        parsed=primary,
        user_id=user_id,
        message=message,
        history=history or [],
        ref=ref,
        soul_id=soul_id,
        has_request_plan=has_request_plan,
        trace_id=trace_id,
        llm_metrics=llm_metrics,
    )
    # 将 LLM 统计信息挂到 ChatResponse.extra.llm_metrics 上，供上层 API 返回
    if llm_metrics:
        if resp.extra is None:
            resp.extra = {}
        resp.extra.setdefault("llm_metrics", llm_metrics)
    return resp


async def _route_intent(
    parsed: ParsedRecord,
    user_id: str,
    message: str,
    history: Sequence[dict],
    ref: date,
    soul_id: Optional[str],
    has_request_plan: bool = False,
    trace_id: Optional[str] = None,
    llm_metrics: Optional[dict[str, Any]] = None,
) -> ChatResponse:
    intent = parsed.intent

    if intent == IntentType.UNKNOWN:
        return await _handle_unknown(
            user_id,
            message,
            history,
            soul_id,
            trace_id=trace_id,
            llm_metrics=llm_metrics,
        )

    if intent in _RECORD_INTENTS:
        return _handle_record(parsed, user_id, has_request_plan)

    if intent in _QUERY_INTENTS:
        return _handle_query(parsed, user_id)

    if intent == IntentType.REQUEST_PLAN:
        return _handle_request_plan(parsed, user_id)

    if intent == IntentType.EDIT_LAST:
        return _handle_edit(parsed, user_id)

    if intent == IntentType.DELETE_RECORD:
        return _handle_delete(parsed, user_id)

    return await _handle_unknown(
        user_id,
        message,
        history,
        soul_id,
        trace_id=trace_id,
        llm_metrics=llm_metrics,
    )


async def _handle_unknown(
    user_id: str,
    message: str,
    history: Sequence[dict],
    soul_id: Optional[str],
    trace_id: Optional[str] = None,
    llm_metrics: Optional[dict[str, Any]] = None,
) -> ChatResponse:
    reply_text, sticker_id = await small_chat_reply(
        user_id=user_id,
        message=message,
        history=history,
        soul_id=soul_id,
        trace_id=trace_id,
        metrics=llm_metrics,
    )
    return ChatResponse(
        user_id=user_id,
        type="chat_only",
        message=reply_text,
        sticker_id=sticker_id,
    )


def _handle_record(
    parsed: ParsedRecord,
    user_id: str,
    has_request_plan: bool = False,
) -> ChatResponse:
    """检查 slot 是否齐全；齐全则返回 ready_to_save，缺则返回 needs_slot_fill。不落库。"""
    miss = missing_slots(parsed.intent, parsed.payload)
    if miss:
        return ChatResponse(
            user_id=user_id,
            type="needs_slot_fill",
            message=slot_fill_question(parsed.intent, miss),
            parsed=parsed_dict(parsed),
            extra={"missing_slots": miss},
        )

    summary = payload_summary(parsed.intent, parsed.payload or {})
    cn = intent_cn(parsed.intent)
    detail = f"（{summary}）" if summary else ""
    extra = {"has_request_plan": True} if has_request_plan else None

    return ChatResponse(
        user_id=user_id,
        type="ready_to_save",
        message=f"{cn}{detail}",
        parsed=parsed_dict(parsed),
        extra=extra,
    )


def _handle_query(parsed: ParsedRecord, user_id: str) -> ChatResponse:
    return ChatResponse(
        user_id=user_id,
        type="query",
        message=f"收到，我来帮你查一下{intent_cn(parsed.intent)}。我先整理一下数据，马上给你结果。",
        parsed=parsed_dict(parsed),
        extra={"query_intent": parsed.intent.value, "query_payload": parsed.payload},
    )


def _handle_request_plan(parsed: ParsedRecord, user_id: str) -> ChatResponse:
    text = (parsed.raw_message or "").strip().lower()
    # “查看/展示/我的计划”走读库展示；“制定/生成/创建”走生成预览
    view_keywords = ("展示", "查看", "看看", "显示", "我的计划", "当前计划", "plan")
    build_keywords = ("制定", "生成", "新建", "创建", "安排")
    mode = "view" if any(k in text for k in view_keywords) and not any(
        k in text for k in build_keywords
    ) else "build"
    msg = (
        "好的，我来读取你当前已保存的训练计划并展示给你。"
        if mode == "view"
        else "明白了，我来给你做一版可执行的训练计划。稍等一下，我会按你的目标和当前状态来安排。"
    )
    return ChatResponse(
        user_id=user_id,
        type="plan_preview",
        message=msg,
        parsed=parsed_dict(parsed),
        extra={"goal_id": (parsed.payload or {}).get("goal_id"), "plan_mode": mode},
    )


def _handle_edit(parsed: ParsedRecord, user_id: str) -> ChatResponse:
    return ChatResponse(
        user_id=user_id,
        type="edit",
        message="好的，修改需求我收到了。我会按你这次的描述去更新对应记录。",
        parsed=parsed_dict(parsed),
        extra={
            "record_type": (parsed.payload or {}).get("record_type"),
            "updates": (parsed.payload or {}).get("updates"),
        },
    )


def _handle_delete(parsed: ParsedRecord, user_id: str) -> ChatResponse:
    return ChatResponse(
        user_id=user_id,
        type="delete",
        message="明白，这条删除请求我记下了。接下来我会按你给的信息定位并删除对应记录。",
        parsed=parsed_dict(parsed),
        extra={
            "record_type": (parsed.payload or {}).get("record_type"),
            "record_id": (parsed.payload or {}).get("record_id"),
        },
    )
