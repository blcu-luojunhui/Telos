"""
重复检测策略：按意图注册 DuplicatePolicy，统一查库与比较逻辑。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase

from src.core.database.mysql import (
    async_mysql_pool,
    Meal,
    Workout,
    BodyMetric,
    Goal,
)
from src.domain.interaction.duplicate_checker.domain_record import DomainRecord
from src.domain.interaction.schemas import IntentType


class DuplicatePolicy(ABC):
    """单类意图的重复检测策略。"""

    @abstractmethod
    def build_query(self, dr: DomainRecord):  # -> Executable
        """构造查询：返回 select(...).where(...).order_by(...).limit(1)。"""
        ...

    @abstractmethod
    def extract_content(self, row: Any) -> dict[str, Any]:
        """把 DB 行转为 content dict，用于 is_same 比较。"""
        ...

    @abstractmethod
    def is_same(self, existing_content: dict, new_content: dict) -> bool:
        """是否内容完全相同。"""
        ...

    @abstractmethod
    def summary(self, row: Any, existing_content: dict) -> str:
        """给用户看的摘要。"""
        ...

    @property
    @abstractmethod
    def table_name(self) -> str:
        """表名，用于 DuplicateHit.table。"""
        ...


def _meal_type_cn(t: str) -> str:
    return {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐", "snack": "加餐"}.get(t, t)


def _workout_type_cn(t: str) -> str:
    return {"run": "跑步", "basketball": "篮球", "strength": "力量训练"}.get(t, t)


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
        return f"已有身体指标记录：{'、'.join(parts)}" if parts else "已有身体指标记录"


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
        return False  # 目标类一律视为不同内容，只提示存在

    def summary(self, row: Goal, existing_content: dict) -> str:
        return f"已有进行中的{row.type}目标"


POLICIES: dict[IntentType, DuplicatePolicy] = {
    IntentType.RECORD_MEAL: MealDuplicatePolicy(),
    IntentType.RECORD_WORKOUT: WorkoutDuplicatePolicy(),
    IntentType.RECORD_BODY_METRIC: BodyMetricDuplicatePolicy(),
    IntentType.SET_GOAL: GoalDuplicatePolicy(),
}
