"""
领域记录抽象：将 NLU 的 ParsedRecord 归一为重复检测引擎使用的 DomainRecord。
含餐次推断（MealScope），保证「中午吃了 X」稳定归到 lunch。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, Optional, Sequence

from src.domain.interaction.nlu.preprocess import preprocess_message
from src.domain.interaction.schemas import IntentType, ParsedRecord


@dataclass
class DomainRecord:
    """归一化后的记录，供重复检测策略使用。"""

    user_id: str
    intent: IntentType
    date: date
    primary_scope: dict[str, Any]  # 查库主键，如 {"meal_type": "lunch"}, {"type": "run"}
    content: dict[str, Any]       # 用于比较「是否相同」的字段


MealSlot = Literal["breakfast", "lunch", "dinner", "snack"]


def infer_meal_scope(
    parsed: ParsedRecord,
    ref_date: date,
    history: Optional[Sequence[dict]] = None,
) -> MealSlot:
    payload = parsed.payload or {}
    raw = (parsed.raw_message or "").strip()

    mt = payload.get("meal_type")
    if mt in ("breakfast", "lunch", "dinner", "snack"):
        return mt

    pre = preprocess_message(raw, ref_date)
    hint = pre.hints.get("meal_type")
    if hint in ("breakfast", "lunch", "dinner", "snack"):
        return hint

    # 3) 历史：最近一条助手回复若含「午餐/早餐/晚餐」可作参考（可选）
    if history:
        for turn in reversed(history):
            role = (turn.get("role") or "").strip()
            content = (turn.get("content") or "").strip()
            if role != "assistant" or not content:
                continue
            if "午餐" in content or "午饭" in content:
                return "lunch"
            if "早餐" in content or "早饭" in content:
                return "breakfast"
            if "晚餐" in content or "晚饭" in content:
                return "dinner"
            if "加餐" in content or "零食" in content:
                return "snack"
            break

    return "snack"  # 默认兜底


def to_domain_record(
    parsed: ParsedRecord,
    user_id: str,
    ref_date: date,
    history: Optional[Sequence[dict]] = None,
) -> DomainRecord:
    """将 ParsedRecord 转为 DomainRecord，含餐次等推断。"""
    intent = parsed.intent
    d = parsed.date or ref_date
    payload = parsed.payload or {}

    if intent == IntentType.RECORD_MEAL:
        meal_slot = infer_meal_scope(parsed, ref_date, history)
        return DomainRecord(
            user_id=user_id,
            intent=intent,
            date=d,
            primary_scope={"meal_type": meal_slot},
            content={
                "food_items": (payload.get("food_items") or "").strip().lower(),
                "estimated_calories": payload.get("estimated_calories"),
            },
        )

    if intent == IntentType.RECORD_WORKOUT:
        w_type = payload.get("type") or "other"
        return DomainRecord(
            user_id=user_id,
            intent=intent,
            date=d,
            primary_scope={"type": w_type},
            content={
                "duration_min": payload.get("duration_min"),
                "distance_km": payload.get("distance_km"),
                "avg_pace": payload.get("avg_pace"),
                "avg_hr": payload.get("avg_hr"),
                "calories": payload.get("calories"),
            },
        )

    if intent == IntentType.RECORD_BODY_METRIC:
        return DomainRecord(
            user_id=user_id,
            intent=intent,
            date=d,
            primary_scope={},
            content={
                "weight": payload.get("weight"),
                "body_fat": payload.get("body_fat"),
                "sleep_hours": payload.get("sleep_hours"),
            },
        )

    if intent == IntentType.SET_GOAL:
        g_type = payload.get("type") or ""
        return DomainRecord(
            user_id=user_id,
            intent=intent,
            date=d,
            primary_scope={"type": g_type},
            content=dict(payload),
        )

    return DomainRecord(
        user_id=user_id,
        intent=intent,
        date=d,
        primary_scope={},
        content=dict(payload),
    )
