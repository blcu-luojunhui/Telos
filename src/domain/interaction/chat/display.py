"""
展示与格式化工具：将解析结果转为人类可读文本。
"""

from __future__ import annotations

from src.domain.interaction.schemas import IntentType, ParsedRecord


def parsed_dict(p: ParsedRecord) -> dict:
    return {
        "intent": p.intent.value,
        "date": p.date.isoformat() if p.date else None,
        "payload": p.payload,
        "raw_message": p.raw_message,
    }


def intent_cn(intent: IntentType) -> str:
    return {
        IntentType.RECORD_WORKOUT: "运动训练",
        IntentType.RECORD_MEAL: "饮食",
        IntentType.RECORD_BODY_METRIC: "身体指标",
        IntentType.SET_GOAL: "目标",
        IntentType.RECORD_STATUS: "今日状态",
    }.get(intent, str(intent.value))


def payload_summary(intent: IntentType, payload: dict) -> str:
    parts: list[str] = []
    if intent == IntentType.RECORD_MEAL:
        if payload.get("meal_type"):
            parts.append(meal_type_cn(payload["meal_type"]))
        if payload.get("food_items"):
            parts.append(payload["food_items"])
    elif intent == IntentType.RECORD_WORKOUT:
        if payload.get("type"):
            parts.append(workout_type_cn(payload["type"]))
        if payload.get("duration_min"):
            parts.append(f"{payload['duration_min']}分钟")
        if payload.get("distance_km"):
            parts.append(f"{payload['distance_km']}km")
    elif intent == IntentType.RECORD_BODY_METRIC:
        if payload.get("weight"):
            parts.append(f"体重{payload['weight']}kg")
        if payload.get("sleep_hours"):
            parts.append(f"睡眠{payload['sleep_hours']}h")
    elif intent == IntentType.SET_GOAL:
        if payload.get("type"):
            parts.append(payload["type"])
    elif intent == IntentType.RECORD_STATUS:
        if payload.get("note"):
            parts.append(payload["note"])
    return "、".join(parts)


def meal_type_cn(t: str) -> str:
    return {
        "breakfast": "早餐",
        "lunch": "午餐",
        "dinner": "晚餐",
        "snack": "加餐",
    }.get(t, t)


def workout_type_cn(t: str) -> str:
    return {"run": "跑步", "basketball": "篮球", "strength": "力量训练"}.get(t, t)
