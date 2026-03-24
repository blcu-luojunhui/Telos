"""V2 record applier: 写入统一 records + detail tables。"""
from typing import Any
from datetime import date, datetime

from src.infra.database.mysql import (
    ActivityRecordV2,
    GoalCheckpoint,
    MeasurementItemV2,
    MeasurementRecordV2,
    NutritionItemV2,
    NutritionRecordV2,
    Plan,
    PlanGoalLink,
    PlanItem,
    PlanVersion,
    Record,
    StatusRecordV2,
    UserGoal,
    async_mysql_pool,
)
from src.domain.interaction.schemas import IntentType, ParsedRecord
from src.domain.interaction.record.utils import _get, _parse_date
from src.infra.persistence.mysql_user_identity import get_or_create_user_id


def _to_float(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _to_int(v):
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _safe_date(parsed: ParsedRecord) -> date:
    return parsed.date or date.today()


async def apply_parsed_record(parsed: ParsedRecord) -> dict[str, Any]:
    """
    根据 ParsedRecord 落表，并返回本次写入摘要。

    :param parsed: parse_user_message 的返回
    :return: {
      "ok": True/False, "intent": ..., "entity": ..., "table": ..., "id": ..., "error": ...
    }
    说明：table 字段为兼容保留，建议上层使用 entity。
    """
    if parsed.intent == IntentType.UNKNOWN:
        return {
            "ok": False,
            "intent": "unknown",
            "entity": None,
            "table": None,
            "id": None,
            "error": "意图无法识别",
        }

    uid = (parsed.user_id or "").strip()
    if not uid:
        return {
            "ok": False,
            "intent": parsed.intent.value,
            "entity": None,
            "table": None,
            "id": None,
            "error": "user_id 不能为空",
        }

    payload = parsed.payload or {}
    d = _safe_date(parsed)
    occurred_at = datetime.combine(d, datetime.min.time())
    user_id = await get_or_create_user_id(uid)

    async with async_mysql_pool.session() as session:
        try:
            if parsed.intent == IntentType.RECORD_WORKOUT:
                rec = Record(
                    user_id=user_id,
                    record_type="activity",
                    source_type="chat",
                    occurred_at=occurred_at,
                    local_date=d,
                    status="active",
                    created_by="user",
                )
                session.add(rec)
                await session.flush()
                row = ActivityRecordV2(
                    record_id=rec.id,
                    activity_type=_get(payload, "type", "other") or "other",
                    duration_min=_to_int(_get(payload, "duration_min")),
                    distance_km=_to_float(_get(payload, "distance_km")),
                    avg_pace_sec_per_km=_to_int(_get(payload, "avg_pace")),
                    avg_hr=_to_int(_get(payload, "avg_hr")),
                    calories=_to_int(_get(payload, "calories")),
                    subjective_fatigue=_to_int(_get(payload, "subjective_fatigue")),
                    sleep_quality=_to_int(_get(payload, "sleep_quality")),
                    mood=_to_int(_get(payload, "mood")),
                    motivation=_to_int(_get(payload, "motivation")),
                    stress_level=_to_int(_get(payload, "stress_level")),
                    note=_get(payload, "note"),
                )
                session.add(row)
                await session.commit()
                return {
                    "ok": True,
                    "intent": "record_workout",
                    "entity": "record.activity",
                    "table": "records/activity_records",
                    "id": rec.id,
                }

            if parsed.intent == IntentType.RECORD_MEAL:
                rec = Record(
                    user_id=user_id,
                    record_type="nutrition",
                    source_type="chat",
                    occurred_at=occurred_at,
                    local_date=d,
                    status="active",
                    created_by="user",
                )
                session.add(rec)
                await session.flush()
                row = NutritionRecordV2(
                    record_id=rec.id,
                    meal_type=_get(payload, "meal_type", "snack") or "snack",
                    estimated_calories=_to_int(_get(payload, "estimated_calories")),
                    protein_g=_to_float(_get(payload, "protein_g")),
                    carb_g=_to_float(_get(payload, "carb_g")),
                    fat_g=_to_float(_get(payload, "fat_g")),
                    satiety=_to_int(_get(payload, "satiety")),
                    mood=_to_int(_get(payload, "mood")),
                    stress_level=_to_int(_get(payload, "stress_level")),
                    note=_get(payload, "note"),
                )
                session.add(row)
                food_items = (_get(payload, "food_items") or "").strip()
                if food_items:
                    session.add(
                        NutritionItemV2(
                            record_id=rec.id,
                            food_name=food_items[:128],
                            quantity_text=None,
                        )
                    )
                await session.commit()
                return {
                    "ok": True,
                    "intent": "record_meal",
                    "entity": "record.nutrition",
                    "table": "records/nutrition_records",
                    "id": rec.id,
                }

            if parsed.intent == IntentType.RECORD_BODY_METRIC:
                rec = Record(
                    user_id=user_id,
                    record_type="measurement",
                    source_type="chat",
                    occurred_at=occurred_at,
                    local_date=d,
                    status="active",
                    created_by="user",
                )
                session.add(rec)
                await session.flush()
                mr = MeasurementRecordV2(
                    record_id=rec.id,
                    measurement_context="manual",
                    note=_get(payload, "note"),
                )
                session.add(mr)
                metric_map = {
                    "weight": "kg",
                    "body_fat": "%",
                    "muscle_mass": "kg",
                    "resting_hr": "bpm",
                    "sleep_hours": "h",
                    "bp_systolic": "mmHg",
                    "bp_diastolic": "mmHg",
                }
                for code, unit in metric_map.items():
                    value = _get(payload, code)
                    if value is None:
                        continue
                    session.add(
                        MeasurementItemV2(
                            record_id=rec.id,
                            user_id=user_id,
                            local_date=d,
                            metric_code=code,
                            numeric_value=_to_float(value),
                            unit=unit,
                            source="chat",
                        )
                    )
                await session.commit()
                return {
                    "ok": True,
                    "intent": "record_body_metric",
                    "entity": "record.measurement",
                    "table": "records/measurement_records",
                    "id": rec.id,
                }

            if parsed.intent == IntentType.SET_GOAL:
                target_date = _parse_date(_get(payload, "deadline"))
                title = _get(payload, "title")
                if not title:
                    g_type = _get(payload, "type") or "maintenance"
                    title = f"{g_type} 目标"
                row = UserGoal(
                    user_id=user_id,
                    goal_type=_get(payload, "type") or "maintenance",
                    title=title[:255],
                    status="active",
                    target_date=target_date,
                    success_definition_json=_get(payload, "target"),
                    note=_get(payload, "note"),
                )
                session.add(row)
                await session.flush()
                if target_date:
                    session.add(
                        GoalCheckpoint(
                            goal_id=row.id,
                            checkpoint_date=target_date,
                            target_json=_get(payload, "target"),
                            status="planned",
                        )
                    )
                await session.commit()
                return {
                    "ok": True,
                    "intent": "set_goal",
                    "entity": "goal",
                    "table": "user_goals",
                    "id": row.id,
                }

            if parsed.intent == IntentType.RECORD_STATUS:
                rec = Record(
                    user_id=user_id,
                    record_type="status",
                    source_type="chat",
                    occurred_at=occurred_at,
                    local_date=d,
                    status="active",
                    created_by="user",
                )
                session.add(rec)
                await session.flush()
                row = StatusRecordV2(
                    record_id=rec.id,
                    mood=_to_int(_get(payload, "mood")),
                    motivation=_to_int(_get(payload, "motivation")),
                    stress_level=_to_int(_get(payload, "stress_level")),
                    energy_level=_to_int(_get(payload, "energy_level")),
                    recovery_state=_to_int(_get(payload, "recovery_state")),
                    summary=(_get(payload, "summary") or parsed.raw_message or "").strip() or None,
                    note=_get(payload, "note"),
                )
                session.add(row)
                await session.commit()
                return {
                    "ok": True,
                    "intent": "record_status",
                    "entity": "record.status",
                    "table": "records/status_records",
                    "id": rec.id,
                }

        except Exception as e:
            await session.rollback()
            return {
                "ok": False,
                "intent": parsed.intent.value,
                "entity": None,
                "table": None,
                "id": None,
                "error": str(e),
            }

    return {
        "ok": False,
        "intent": parsed.intent.value,
        "entity": None,
        "table": None,
        "id": None,
        "error": "未处理意图",
    }


__all__ = ["apply_parsed_record"]
