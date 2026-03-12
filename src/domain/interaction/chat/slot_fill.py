"""
多轮补全（Slot Filling）：当记录类意图缺少必填项时，追问并合并下一轮回复。
"""

from __future__ import annotations

from datetime import date

from src.domain.interaction.schemas import IntentType


def merge_slot_from_message(
    intent: IntentType,
    payload: dict,
    user_message: str,
    reference_date: date,
) -> dict:
    """
    用用户本轮的回复补全 payload 中缺失的 slot。
    使用预处理 hint（餐次、运动类型）或直接把整句当 food_items。
    """
    from src.domain.interaction.nlu.preprocess import preprocess_message

    payload = dict(payload or {})
    msg = (user_message or "").strip()
    pre = preprocess_message(msg, reference_date)

    if intent == IntentType.RECORD_MEAL:
        if not payload.get("meal_type") and pre.hints.get("meal_type"):
            payload["meal_type"] = pre.hints["meal_type"]
        if not (payload.get("food_items") or "").strip():
            payload["food_items"] = msg or "（未填写）"
    elif intent == IntentType.RECORD_WORKOUT:
        if not payload.get("type") and pre.hints.get("workout_type"):
            payload["type"] = pre.hints["workout_type"]
        elif not payload.get("type"):
            payload["type"] = "other"
    elif intent == IntentType.SET_GOAL:
        if not payload.get("type") and msg:
            # 简单映射
            if "减" in msg or "瘦" in msg or "脂" in msg:
                payload["type"] = "weight_loss"
            elif "增肌" in msg or "肌肉" in msg:
                payload["type"] = "muscle_gain"
            elif "马" in msg or "跑" in msg or "比赛" in msg:
                payload["type"] = "race"
            else:
                payload["type"] = "maintenance"
    return payload


def required_slots(intent: IntentType) -> list[str]:
    """返回该意图必填的 payload 字段（缺一不可）。"""
    if intent == IntentType.RECORD_MEAL:
        return ["meal_type", "food_items"]
    if intent == IntentType.RECORD_WORKOUT:
        return ["type"]
    if intent == IntentType.SET_GOAL:
        return ["type"]
    return []


def missing_slots(intent: IntentType, payload: dict | None) -> list[str]:
    """返回当前 payload 中仍缺失的必填项。"""
    required = required_slots(intent)
    if not required:
        return []
    payload = payload or {}
    return [k for k in required if not _has_value(payload.get(k))]


def _has_value(v) -> bool:
    if v is None:
        return False
    if isinstance(v, str) and not v.strip():
        return False
    return True


def slot_fill_question(intent: IntentType, missing: list[str]) -> str:
    """根据缺失的 slot 生成一句追问。"""
    if not missing:
        return ""
    if intent == IntentType.RECORD_MEAL:
        if "meal_type" in missing and "food_items" in missing:
            return "请问是早餐、午餐、晚餐还是加餐？吃了啥？"
        if "meal_type" in missing:
            return "请问是早餐、午餐、晚餐还是加餐？"
        if "food_items" in missing:
            return "吃了啥？"
    if intent == IntentType.RECORD_WORKOUT:
        if "type" in missing:
            return "请问是跑步、篮球、力量训练还是其他运动？"
    if intent == IntentType.SET_GOAL:
        if "type" in missing:
            return "想设定什么类型的目标？例如减脂、增肌、半马等。"
    return "请补充一下信息～"
