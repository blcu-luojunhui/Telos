"""
重复记录检测：根据 intent + date + 子类型，查库判断是否已有类似记录。

返回：
- None  → 无重复
- existing_rows list → 有潜在重复，附带是否"内容相同"标记
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from sqlalchemy import select

from src.core.database.mysql import async_mysql_pool, Workout, Meal, BodyMetric, Goal
from src.domain.interaction.schemas import IntentType


@dataclass
class DuplicateHit:
    existing_id: int
    table: str
    same_content: bool
    summary: str


async def check_duplicate(
    intent: IntentType,
    record_date: date,
    payload: dict[str, Any],
) -> Optional[DuplicateHit]:
    """
    检查当天是否已有"同类"记录。
    如果有，判断内容是否一致，返回 DuplicateHit；没有则返回 None。
    """
    if intent == IntentType.RECORD_MEAL:
        return await _check_meal(record_date, payload)
    if intent == IntentType.RECORD_WORKOUT:
        return await _check_workout(record_date, payload)
    if intent == IntentType.RECORD_BODY_METRIC:
        return await _check_body_metric(record_date, payload)
    if intent == IntentType.SET_GOAL:
        return await _check_goal(payload)
    return None


async def _check_meal(d: date, payload: dict) -> Optional[DuplicateHit]:
    meal_type = payload.get("meal_type")
    if not meal_type:
        return None

    async with async_mysql_pool.session() as session:
        stmt = select(Meal).where(Meal.date == d, Meal.meal_type == meal_type)
        result = await session.execute(stmt)
        existing = result.scalars().first()
        if not existing:
            return None

        new_food = (payload.get("food_items") or "").strip().lower()
        old_food = (existing.food_items or "").strip().lower()
        same = new_food == old_food

        return DuplicateHit(
            existing_id=existing.id,
            table="meals",
            same_content=same,
            summary=f"已有{_meal_type_cn(meal_type)}记录：{existing.food_items}",
        )


async def _check_workout(d: date, payload: dict) -> Optional[DuplicateHit]:
    w_type = payload.get("type")
    if not w_type:
        return None

    async with async_mysql_pool.session() as session:
        stmt = select(Workout).where(Workout.date == d, Workout.type == w_type)
        result = await session.execute(stmt)
        existing = result.scalars().first()
        if not existing:
            return None

        same = _workout_same(existing, payload)
        summary_parts = [_workout_type_cn(w_type)]
        if existing.duration_min:
            summary_parts.append(f"{existing.duration_min}分钟")
        if existing.distance_km:
            summary_parts.append(f"{existing.distance_km}km")

        return DuplicateHit(
            existing_id=existing.id,
            table="workouts",
            same_content=same,
            summary=f"已有{' '.join(summary_parts)}记录",
        )


async def _check_body_metric(d: date, payload: dict) -> Optional[DuplicateHit]:
    async with async_mysql_pool.session() as session:
        stmt = select(BodyMetric).where(BodyMetric.date == d)
        result = await session.execute(stmt)
        existing = result.scalars().first()
        if not existing:
            return None

        same = _body_metric_same(existing, payload)
        parts = []
        if existing.weight:
            parts.append(f"体重{existing.weight}kg")
        if existing.sleep_hours:
            parts.append(f"睡眠{existing.sleep_hours}h")

        return DuplicateHit(
            existing_id=existing.id,
            table="body_metrics",
            same_content=same,
            summary=f"已有身体指标记录：{'、'.join(parts)}"
            if parts
            else "已有身体指标记录",
        )


async def _check_goal(payload: dict) -> Optional[DuplicateHit]:
    g_type = payload.get("type")
    if not g_type:
        return None

    async with async_mysql_pool.session() as session:
        stmt = select(Goal).where(
            Goal.type == g_type,
            Goal.status.in_(["planning", "ongoing"]),
        )
        result = await session.execute(stmt)
        existing = result.scalars().first()
        if not existing:
            return None

        return DuplicateHit(
            existing_id=existing.id,
            table="goals",
            same_content=False,
            summary=f"已有进行中的{g_type}目标",
        )


def _workout_same(existing: Workout, payload: dict) -> bool:
    for key in ("duration_min", "distance_km", "avg_pace", "avg_hr", "calories"):
        ev = getattr(existing, key, None)
        pv = payload.get(key)
        if ev is not None and pv is not None and ev != pv:
            return False
    return True


def _body_metric_same(existing: BodyMetric, payload: dict) -> bool:
    for key in ("weight", "body_fat", "muscle_mass", "resting_hr", "sleep_hours"):
        ev = getattr(existing, key, None)
        pv = payload.get(key)
        if ev is not None and pv is not None and ev != pv:
            return False
    return True


def _meal_type_cn(t: str) -> str:
    return {
        "breakfast": "早餐",
        "lunch": "午餐",
        "dinner": "晚餐",
        "snack": "加餐",
    }.get(t, t)


def _workout_type_cn(t: str) -> str:
    return {"run": "跑步", "basketball": "篮球", "strength": "力量训练"}.get(t, t)
