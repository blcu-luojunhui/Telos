"""
多轮补全（Slot Filling）：当记录类意图缺少必填项时，追问并合并下一轮回复。
"""

from __future__ import annotations

import re
from datetime import date
from typing import Optional

from src.domain.interaction.schemas import IntentType


_MEAL_TYPE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("breakfast", re.compile(r"早[餐饭上]|早[上晨]")),
    ("lunch", re.compile(r"午[餐饭]|中[餐饭午]")),
    ("dinner", re.compile(r"晚[餐饭上]|夜[宵饭]")),
    ("snack", re.compile(r"加餐|零食|下午茶|甜点")),
]

_WORKOUT_TYPE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("run", re.compile(r"跑[步了]|慢跑|快跑|跑")),
    ("basketball", re.compile(r"篮球|打球")),
    ("strength", re.compile(r"力量|举[铁重]|撸铁|器械|深蹲|卧推|硬拉")),
    ("swim", re.compile(r"游泳|泳")),
    ("cycling", re.compile(r"骑[车行]|单车|自行车")),
    ("yoga", re.compile(r"瑜伽|拉伸")),
    ("hiking", re.compile(r"徒步|爬山|登山|散步|走路|步行")),
]


def merge_slot_from_message(
    intent: IntentType,
    payload: dict,
    user_message: str,
    reference_date: date,
) -> dict:
    """
    用用户本轮的回复补全 payload 中缺失的 slot。
    使用预处理 hint + 正则模式提取，或直接把整句当 food_items。
    """
    from src.domain.interaction.nlu.preprocess import preprocess_message

    payload = dict(payload or {})
    msg = (user_message or "").strip()
    pre = preprocess_message(msg, reference_date)

    if intent == IntentType.RECORD_MEAL:
        payload = _fill_meal_slots(payload, msg, pre.hints)
    elif intent == IntentType.RECORD_WORKOUT:
        payload = _fill_workout_slots(payload, msg, pre.hints)
    elif intent == IntentType.SET_GOAL:
        payload = _fill_goal_slots(payload, msg)
    return payload


def _fill_meal_slots(payload: dict, msg: str, hints: dict) -> dict:
    if not payload.get("meal_type"):
        if hints.get("meal_type"):
            payload["meal_type"] = hints["meal_type"]
        else:
            for mt, pat in _MEAL_TYPE_PATTERNS:
                if pat.search(msg):
                    payload["meal_type"] = mt
                    break

    if not (payload.get("food_items") or "").strip():
        food = msg
        if payload.get("meal_type"):
            for _, pat in _MEAL_TYPE_PATTERNS:
                food = pat.sub("", food).strip()
        food = re.sub(r"^[，,、：:\s]+|[，,、：:\s]+$", "", food)
        payload["food_items"] = food if food else msg or "（未填写）"

    return payload


def _fill_workout_slots(payload: dict, msg: str, hints: dict) -> dict:
    if not payload.get("type"):
        if hints.get("workout_type"):
            payload["type"] = hints["workout_type"]
        else:
            for wt, pat in _WORKOUT_TYPE_PATTERNS:
                if pat.search(msg):
                    payload["type"] = wt
                    break
            else:
                payload["type"] = "other"

    dur_match = re.search(r"(\d+)\s*分钟", msg)
    if dur_match and payload.get("duration_min") is None:
        payload["duration_min"] = int(dur_match.group(1))

    dist_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:公里|km|千米)", msg, re.IGNORECASE)
    if dist_match and payload.get("distance_km") is None:
        payload["distance_km"] = float(dist_match.group(1))

    return payload


def _fill_goal_slots(payload: dict, msg: str) -> dict:
    if not payload.get("type") and msg:
        if re.search(r"减[脂肥重]|瘦", msg):
            payload["type"] = "weight_loss"
        elif re.search(r"增肌|肌肉|增重", msg):
            payload["type"] = "muscle_gain"
        elif re.search(r"马拉松|半马|全马|10[kK公]|5[kK公]|跑|比赛", msg):
            payload["type"] = "race"
        elif re.search(r"维持|保持", msg):
            payload["type"] = "maintenance"
        else:
            payload["type"] = "maintenance"
    return payload


def merge_from_nlu_result(
    intent: IntentType,
    current_payload: dict,
    nlu_payload: Optional[dict],
) -> dict:
    """将 NLU 重新解析的 payload 中非空字段合并到当前 payload（仅补缺不覆盖）。"""
    if not nlu_payload:
        return current_payload
    payload = dict(current_payload)
    for key, val in nlu_payload.items():
        if not _has_value(payload.get(key)) and _has_value(val):
            payload[key] = val
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
