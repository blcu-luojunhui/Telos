"""
归一化 + Pydantic 校验（Hybrid NLU）。

- 将 LLM 输出的 intent/payload 做白名单过滤、类型转换、枚举映射
- 用 schemas.py 中的 Pydantic 模型校验 payload
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from pydantic import ValidationError

from src.domain.interaction.schemas import (
    IntentType,
    RecordBodyMetricPayload,
    RecordMealPayload,
    RecordStatusPayload,
    RecordWorkoutPayload,
    SetGoalPayload,
)


_WORKOUT_TYPE_MAP = {
    "跑步": "run",
    "长跑": "run",
    "LSD": "run",
    "慢跑": "run",
    "run": "run",
    "jog": "run",
    "篮球": "basketball",
    "basketball": "basketball",
    "力量": "strength",
    "健身": "strength",
    "strength": "strength",
}

_MEAL_TYPE_MAP = {
    "breakfast": "breakfast",
    "早餐": "breakfast",
    "早饭": "breakfast",
    "lunch": "lunch",
    "午饭": "lunch",
    "午餐": "lunch",
    "dinner": "dinner",
    "晚饭": "dinner",
    "晚餐": "dinner",
    "snack": "snack",
    "零食": "snack",
    "加餐": "snack",
    "夜宵": "snack",
}


def _to_number(v: Any) -> Any:
    if isinstance(v, (int, float)) or v is None:
        return v
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        # 去掉常见单位尾巴
        for suf in ("%", "kg", "g", "分钟", "min", "km", "公里", "小时", "h"):
            if s.lower().endswith(suf):
                s = s[: -len(suf)].strip()
                break
        try:
            if "." in s:
                return float(s)
            return int(s)
        except Exception:
            try:
                return float(s)
            except Exception:
                return v
    return v


def _clamp_1_10(v: Any) -> Any:
    n = _to_number(v)
    if isinstance(n, (int, float)):
        n2 = int(round(float(n)))
        if n2 < 1:
            return 1
        if n2 > 10:
            return 10
        return n2
    return v


def _clean_payload(intent: IntentType, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    allow: set[str]
    if intent == IntentType.RECORD_WORKOUT:
        allow = set(RecordWorkoutPayload.model_fields.keys())
    elif intent == IntentType.RECORD_MEAL:
        allow = set(RecordMealPayload.model_fields.keys())
    elif intent == IntentType.RECORD_BODY_METRIC:
        allow = set(RecordBodyMetricPayload.model_fields.keys())
    elif intent == IntentType.SET_GOAL:
        allow = set(SetGoalPayload.model_fields.keys())
    elif intent == IntentType.RECORD_STATUS:
        allow = set(RecordStatusPayload.model_fields.keys())
    else:
        return {}

    return {k: payload.get(k) for k in allow if k in payload}


def normalize_payload(
    intent: IntentType, payload: Any, hints: dict[str, Any] | None = None
) -> dict[str, Any]:
    hints = hints or {}
    p = _clean_payload(intent, payload)

    # 通用数字转换
    for k, v in list(p.items()):
        if k in {
            "duration_min",
            "distance_km",
            "avg_pace",
            "avg_hr",
            "calories",
            "estimated_calories",
            "protein_g",
            "carb_g",
            "fat_g",
            "weight",
            "body_fat",
            "muscle_mass",
            "resting_hr",
            "bp_systolic",
            "bp_diastolic",
            "sleep_hours",
        }:
            p[k] = _to_number(v)

    # 主观 1-10
    for k in (
        "subjective_fatigue",
        "sleep_quality",
        "mood",
        "motivation",
        "stress_level",
        "satiety",
        "energy",
    ):
        if k in p:
            p[k] = _clamp_1_10(p.get(k))

    # workout type 枚举映射 + hints 兜底
    if intent == IntentType.RECORD_WORKOUT:
        raw = p.get("type") or hints.get("workout_type")
        if isinstance(raw, str):
            p["type"] = _WORKOUT_TYPE_MAP.get(
                raw.strip().lower(),
                _WORKOUT_TYPE_MAP.get(raw.strip(), raw.strip().lower()),
            )
        if not p.get("distance_km") and hints.get("distance_km") is not None:
            p["distance_km"] = hints["distance_km"]
        if not p.get("duration_min") and hints.get("duration_min") is not None:
            p["duration_min"] = hints["duration_min"]

    # meal type + hints 兜底
    if intent == IntentType.RECORD_MEAL:
        raw = p.get("meal_type") or hints.get("meal_type")
        if isinstance(raw, str):
            p["meal_type"] = _MEAL_TYPE_MAP.get(
                raw.strip().lower(),
                _MEAL_TYPE_MAP.get(raw.strip(), raw.strip().lower()),
            )

    # body metric：若 hints 识别了 斤->kg，且用户语句像在报体重，则可补 weight
    if intent == IntentType.RECORD_BODY_METRIC:
        if p.get("weight") is None and hints.get("weight_kg") is not None:
            p["weight"] = hints["weight_kg"]

    return p


def validate_payload(
    intent: IntentType, payload: dict[str, Any]
) -> tuple[dict[str, Any], Optional[str]]:
    """
    返回 (validated_payload_dict, error_text_or_none)。
    """
    try:
        if intent == IntentType.RECORD_WORKOUT:
            obj = RecordWorkoutPayload.model_validate(payload)
        elif intent == IntentType.RECORD_MEAL:
            obj = RecordMealPayload.model_validate(payload)
        elif intent == IntentType.RECORD_BODY_METRIC:
            obj = RecordBodyMetricPayload.model_validate(payload)
        elif intent == IntentType.SET_GOAL:
            obj = SetGoalPayload.model_validate(payload)
        elif intent == IntentType.RECORD_STATUS:
            obj = RecordStatusPayload.model_validate(payload)
        else:
            return {}, None
        return obj.model_dump(exclude_none=True), None
    except ValidationError as e:
        return payload, str(e)


def normalize_intent(raw: Any) -> IntentType:
    s = raw or "unknown"
    if isinstance(s, str):
        s2 = s.strip().lower()
    else:
        s2 = "unknown"
    try:
        return IntentType(s2)
    except Exception:
        return IntentType.UNKNOWN


def normalize_date(
    raw: Any, reference_date: date, hints: dict[str, Any] | None = None
) -> date:
    """
    顶层 date：接受 str/date/None；None 则用 reference_date；hints 里的 explicit_date 优先。
    """
    hints = hints or {}
    hinted = hints.get("explicit_date")
    if isinstance(hinted, str):
        try:
            return date.fromisoformat(hinted[:10])
        except Exception:
            pass

    if raw is None:
        return reference_date
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s or s.lower() == "null":
            return reference_date
        try:
            return date.fromisoformat(s[:10])
        except Exception:
            return reference_date
    return reference_date
