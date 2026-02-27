"""
根据解析结果写入数据层（workouts / meals / body_metrics / goals）。

record_status 写入 body_metrics 的 note（或单行仅 date + note）。
"""
from datetime import date
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.mysql import SessionLocal, Workout, Meal, BodyMetric, Goal
from src.core.interaction.schemas import IntentType, ParsedRecord


async def apply_parsed_record(parsed: ParsedRecord) -> dict[str, Any]:
    """
    根据 ParsedRecord 落表，并返回本次写入摘要。

    :param parsed: parse_user_message 的返回
    :return: {"ok": True/False, "intent": ..., "table": ..., "id": ..., "error": ...}
    """
    if parsed.intent == IntentType.UNKNOWN:
        return {"ok": False, "intent": "unknown", "table": None, "id": None, "error": "意图无法识别"}

    payload = parsed.payload or {}
    d = parsed.date or date.today()

    async with SessionLocal() as session:
        try:
            if parsed.intent == IntentType.RECORD_WORKOUT:
                row = await _insert_workout(session, d, payload)
                await session.commit()
                return {"ok": True, "intent": "record_workout", "table": "workouts", "id": row.id}

            if parsed.intent == IntentType.RECORD_MEAL:
                row = await _insert_meal(session, d, payload)
                await session.commit()
                return {"ok": True, "intent": "record_meal", "table": "meals", "id": row.id}

            if parsed.intent == IntentType.RECORD_BODY_METRIC:
                row = await _insert_body_metric(session, d, payload)
                await session.commit()
                return {"ok": True, "intent": "record_body_metric", "table": "body_metrics", "id": row.id}

            if parsed.intent == IntentType.SET_GOAL:
                row = await _insert_goal(session, payload)
                await session.commit()
                return {"ok": True, "intent": "set_goal", "table": "goals", "id": row.id}

            if parsed.intent == IntentType.RECORD_STATUS:
                row = await _insert_status(session, d, payload, parsed.raw_message)
                await session.commit()
                return {"ok": True, "intent": "record_status", "table": "body_metrics", "id": row.id}

        except Exception as e:
            await session.rollback()
            return {"ok": False, "intent": parsed.intent.value, "table": None, "id": None, "error": str(e)}

    return {"ok": False, "intent": parsed.intent.value, "table": None, "id": None, "error": "未处理意图"}


def _get(data: dict, key: str, default=None):
    return data.get(key) if isinstance(data, dict) else default


async def _insert_workout(session: AsyncSession, d: date, payload: dict) -> Workout:
    w = Workout(
        date=d,
        type=_get(payload, "type") or "other",
        duration_min=_get(payload, "duration_min"),
        distance_km=_get(payload, "distance_km"),
        avg_pace=_get(payload, "avg_pace"),
        avg_hr=_get(payload, "avg_hr"),
        calories=_get(payload, "calories"),
        subjective_fatigue=_get(payload, "subjective_fatigue"),
        sleep_quality=_get(payload, "sleep_quality"),
        mood=_get(payload, "mood"),
        motivation=_get(payload, "motivation"),
        stress_level=_get(payload, "stress_level"),
        note=_get(payload, "note"),
    )
    session.add(w)
    await session.flush()
    return w


async def _insert_meal(session: AsyncSession, d: date, payload: dict) -> Meal:
    m = Meal(
        date=d,
        meal_type=_get(payload, "meal_type") or "snack",
        food_items=_get(payload, "food_items") or "",
        estimated_calories=_get(payload, "estimated_calories"),
        protein_g=_get(payload, "protein_g"),
        carb_g=_get(payload, "carb_g"),
        fat_g=_get(payload, "fat_g"),
        satiety=_get(payload, "satiety"),
        mood=_get(payload, "mood"),
        stress_level=_get(payload, "stress_level"),
        note=_get(payload, "note"),
    )
    session.add(m)
    await session.flush()
    return m


async def _insert_body_metric(session: AsyncSession, d: date, payload: dict) -> BodyMetric:
    b = BodyMetric(
        date=d,
        weight=_get(payload, "weight"),
        body_fat=_get(payload, "body_fat"),
        muscle_mass=_get(payload, "muscle_mass"),
        resting_hr=_get(payload, "resting_hr"),
        bp_systolic=_get(payload, "bp_systolic"),
        bp_diastolic=_get(payload, "bp_diastolic"),
        sleep_hours=_get(payload, "sleep_hours"),
        note=_get(payload, "note"),
    )
    session.add(b)
    await session.flush()
    return b


def _parse_date(v: Any) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    if isinstance(v, str) and len(v) >= 10:
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            pass
    return None


async def _insert_goal(session: AsyncSession, payload: dict) -> Goal:
    g = Goal(
        type=_get(payload, "type") or "maintenance",
        target=_get(payload, "target"),
        deadline=_parse_date(_get(payload, "deadline")),
        status="ongoing",
        note=_get(payload, "note"),
    )
    session.add(g)
    await session.flush()
    return g


async def _insert_status(session: AsyncSession, d: date, payload: dict, raw: str) -> BodyMetric:
    """今日状态写入 body_metrics：用 note 存描述，可选 mood/精力/压力。"""
    note = _get(payload, "note") or raw
    b = BodyMetric(
        date=d,
        note=note,
        # 若后续 body_metrics 表加 mood/energy/stress 字段可在这里填
    )
    session.add(b)
    await session.flush()
    return b
