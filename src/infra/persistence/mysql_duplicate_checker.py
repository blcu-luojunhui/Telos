"""
MySQL 重复检测适配器：实现 IDuplicateChecker，策略化查库并返回 DuplicateHit。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from sqlalchemy import select

from src.infra.database.mysql import (
    async_mysql_pool,
    Meal,
    Workout,
    BodyMetric,
    Goal,
)
from src.domain.interaction.duplicate_checker import DuplicateHit
from src.domain.interaction.duplicate_checker.domain_record import DomainRecord
from src.domain.interaction.schemas import IntentType


def _meal_type_cn(t: str) -> str:
    return {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐", "snack": "加餐"}.get(
        t, t
    )


def _workout_type_cn(t: str) -> str:
    return {
        "run": "跑步",
        "basketball": "篮球",
        "strength": "力量训练",
    }.get(t, t)


class DuplicatePolicy(ABC):
    """单类意图的重复检测策略（持久化层实现，依赖 ORM）。"""

    @property
    @abstractmethod
    def table_name(self) -> str:
        ...

    @abstractmethod
    def build_query(self, dr: DomainRecord):
        ...

    @abstractmethod
    def extract_content(self, row: Any) -> dict[str, Any]:
        ...

    @abstractmethod
    def is_same(self, existing_content: dict, new_content: dict) -> bool:
        ...

    @abstractmethod
    def summary(self, row: Any, existing_content: dict) -> str:
        ...


class MealDuplicatePolicy(DuplicatePolicy):
    table_name = "meals"

    def build_query(self, dr: DomainRecord):
        meal_type = dr.primary_scope.get("meal_type")
        if not meal_type:
            return None
        return (
            select(Meal)
            .where(
                Meal.user_id == dr.user_id,
                Meal.date == dr.date,
                Meal.meal_type == meal_type,
                Meal.status == "active",
            )
            .order_by(Meal.id.desc())
            .limit(1)
        )

    def extract_content(self, row: Meal) -> dict[str, Any]:
        return {
            "food_items": (row.food_items or "").strip().lower(),
            "estimated_calories": row.estimated_calories,
        }

    def is_same(self, existing: dict, new: dict) -> bool:
        ef = (existing.get("food_items") or "").strip()
        nf = (new.get("food_items") or "").strip().lower()
        if ef != nf:
            return False
        ec = existing.get("estimated_calories")
        nc = new.get("estimated_calories")
        if ec is not None and nc is not None and ec != nc:
            return False
        return True

    def summary(self, row: Meal, existing_content: dict) -> str:
        return f"已有{_meal_type_cn(row.meal_type)}记录：{row.food_items or '（无）'}"


class WorkoutDuplicatePolicy(DuplicatePolicy):
    table_name = "workouts"

    def build_query(self, dr: DomainRecord):
        w_type = dr.primary_scope.get("type")
        if not w_type:
            return None
        return (
            select(Workout)
            .where(
                Workout.user_id == dr.user_id,
                Workout.date == dr.date,
                Workout.type == w_type,
                Workout.status == "active",
            )
            .order_by(Workout.id.desc())
            .limit(1)
        )

    def extract_content(self, row: Workout) -> dict[str, Any]:
        return {
            "duration_min": row.duration_min,
            "distance_km": row.distance_km,
            "avg_pace": row.avg_pace,
            "avg_hr": row.avg_hr,
            "calories": row.calories,
        }

    def is_same(self, existing: dict, new: dict) -> bool:
        for key in ("duration_min", "distance_km", "avg_pace", "avg_hr", "calories"):
            ev = existing.get(key)
            nv = new.get(key)
            if ev is not None and nv is not None and ev != nv:
                return False
        return True

    def summary(self, row: Workout, existing_content: dict) -> str:
        parts = [_workout_type_cn(row.type)]
        if row.duration_min:
            parts.append(f"{row.duration_min}分钟")
        if row.distance_km:
            parts.append(f"{row.distance_km}km")
        return f"已有{' '.join(parts)}记录"


class BodyMetricDuplicatePolicy(DuplicatePolicy):
    table_name = "body_metrics"

    def build_query(self, dr: DomainRecord):
        return (
            select(BodyMetric)
            .where(
                BodyMetric.user_id == dr.user_id,
                BodyMetric.date == dr.date,
                BodyMetric.status == "active",
            )
            .order_by(BodyMetric.id.desc())
            .limit(1)
        )

    def extract_content(self, row: BodyMetric) -> dict[str, Any]:
        return {
            "weight": row.weight,
            "body_fat": row.body_fat,
            "sleep_hours": row.sleep_hours,
        }

    def is_same(self, existing: dict, new: dict) -> bool:
        for key in ("weight", "body_fat", "sleep_hours"):
            ev = existing.get(key)
            nv = new.get(key)
            if ev is not None and nv is not None and ev != nv:
                return False
        return True

    def summary(self, row: BodyMetric, existing_content: dict) -> str:
        parts = []
        if row.weight is not None:
            parts.append(f"体重{row.weight}kg")
        if row.sleep_hours is not None:
            parts.append(f"睡眠{row.sleep_hours}h")
        return (
            f"已有身体指标记录：{'、'.join(parts)}" if parts else "已有身体指标记录"
        )


class GoalDuplicatePolicy(DuplicatePolicy):
    table_name = "goals"

    def build_query(self, dr: DomainRecord):
        g_type = dr.primary_scope.get("type")
        if not g_type:
            return None
        return (
            select(Goal)
            .where(
                Goal.user_id == dr.user_id,
                Goal.type == g_type,
                Goal.status.in_(["planning", "ongoing"]),
            )
            .order_by(Goal.id.desc())
            .limit(1)
        )

    def extract_content(self, row: Goal) -> dict[str, Any]:
        return dict(row.target or {})

    def is_same(self, existing: dict, new: dict) -> bool:
        return False

    def summary(self, row: Goal, existing_content: dict) -> str:
        return f"已有进行中的{row.type}目标"


_POLICIES: dict[IntentType, DuplicatePolicy] = {
    IntentType.RECORD_MEAL: MealDuplicatePolicy(),
    IntentType.RECORD_WORKOUT: WorkoutDuplicatePolicy(),
    IntentType.RECORD_BODY_METRIC: BodyMetricDuplicatePolicy(),
    IntentType.SET_GOAL: GoalDuplicatePolicy(),
}


class MySQLDuplicateChecker:
    """实现 IDuplicateChecker：按意图选用策略，查库并比较内容。"""

    async def check(self, dr: DomainRecord) -> Optional[DuplicateHit]:
        policy = _POLICIES.get(dr.intent)
        if not policy:
            return None
        stmt = policy.build_query(dr)
        if stmt is None:
            return None
        async with async_mysql_pool.session() as session:
            result = await session.execute(stmt)
            row = result.scalars().first()
        if not row:
            return None
        existing_content = policy.extract_content(row)
        same = policy.is_same(existing_content, dr.content)
        summary = policy.summary(row, existing_content)
        return DuplicateHit(
            existing_id=row.id,
            table=policy.table_name,
            same_content=same,
            summary=summary,
        )
