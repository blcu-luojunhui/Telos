"""
MySQL 重复检测适配器：实现 IDuplicateChecker，策略化查库并返回 DuplicateHit。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from sqlalchemy import case, func, select

from src.infra.database.mysql import (
    ActivityRecordV2,
    MeasurementItemV2,
    NutritionItemV2,
    NutritionRecordV2,
    Record,
    UserGoal,
    async_mysql_pool,
)
from src.infra.persistence.mysql_user_identity import get_or_create_user_id
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
    table_name = "records/nutrition_records"

    def build_query(self, dr: DomainRecord):
        meal_type = dr.primary_scope.get("meal_type")
        if not meal_type:
            return None
        return (
            select(Record.id, NutritionRecordV2.meal_type, NutritionRecordV2.estimated_calories, NutritionItemV2.food_name)
            .join(NutritionRecordV2, NutritionRecordV2.record_id == Record.id)
            .outerjoin(NutritionItemV2, NutritionItemV2.record_id == NutritionRecordV2.record_id)
            .where(
                Record.user_id == dr.user_id,
                Record.record_type == "nutrition",
                Record.local_date == dr.date,
                Record.status == "active",
                NutritionRecordV2.meal_type == meal_type,
            )
            .order_by(Record.id.desc())
            .limit(1)
        )

    def extract_content(self, row: Any) -> dict[str, Any]:
        return {
            "food_items": (row.food_name or "").strip().lower(),
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

    def summary(self, row: Any, existing_content: dict) -> str:
        return f"已有{_meal_type_cn(row.meal_type)}记录：{row.food_name or '（无）'}"


class WorkoutDuplicatePolicy(DuplicatePolicy):
    table_name = "records/activity_records"

    def build_query(self, dr: DomainRecord):
        w_type = dr.primary_scope.get("type")
        if not w_type:
            return None
        return (
            select(
                Record.id,
                ActivityRecordV2.activity_type,
                ActivityRecordV2.duration_min,
                ActivityRecordV2.distance_km,
                ActivityRecordV2.avg_pace_sec_per_km,
                ActivityRecordV2.avg_hr,
                ActivityRecordV2.calories,
            )
            .join(ActivityRecordV2, ActivityRecordV2.record_id == Record.id)
            .where(
                Record.user_id == dr.user_id,
                Record.record_type == "activity",
                Record.local_date == dr.date,
                Record.status == "active",
                ActivityRecordV2.activity_type == w_type,
            )
            .order_by(Record.id.desc())
            .limit(1)
        )

    def extract_content(self, row: Any) -> dict[str, Any]:
        return {
            "duration_min": row.duration_min,
            "distance_km": row.distance_km,
            "avg_pace": row.avg_pace_sec_per_km,
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

    def summary(self, row: Any, existing_content: dict) -> str:
        parts = [_workout_type_cn(row.activity_type)]
        if row.duration_min:
            parts.append(f"{row.duration_min}分钟")
        if row.distance_km:
            parts.append(f"{row.distance_km}km")
        return f"已有{' '.join(parts)}记录"


class BodyMetricDuplicatePolicy(DuplicatePolicy):
    table_name = "records/measurement_records"

    def build_query(self, dr: DomainRecord):
        return (
            select(
                Record.id,
                func.max(
                    case((MeasurementItemV2.metric_code == "weight", MeasurementItemV2.numeric_value))
                ).label("weight"),
                func.max(
                    case((MeasurementItemV2.metric_code == "body_fat", MeasurementItemV2.numeric_value))
                ).label("body_fat"),
                func.max(
                    case((MeasurementItemV2.metric_code == "sleep_hours", MeasurementItemV2.numeric_value))
                ).label("sleep_hours"),
            )
            .join(MeasurementItemV2, MeasurementItemV2.record_id == Record.id)
            .where(
                Record.user_id == dr.user_id,
                Record.record_type == "measurement",
                Record.local_date == dr.date,
                Record.status == "active",
            )
            .group_by(Record.id)
            .order_by(Record.id.desc())
            .limit(1)
        )

    def extract_content(self, row: Any) -> dict[str, Any]:
        return {
            "weight": float(row.weight) if row.weight is not None else None,
            "body_fat": float(row.body_fat) if row.body_fat is not None else None,
            "sleep_hours": float(row.sleep_hours) if row.sleep_hours is not None else None,
        }

    def is_same(self, existing: dict, new: dict) -> bool:
        for key in ("weight", "body_fat", "sleep_hours"):
            ev = existing.get(key)
            nv = new.get(key)
            if ev is not None and nv is not None and ev != nv:
                return False
        return True

    def summary(self, row: Any, existing_content: dict) -> str:
        parts = []
        if row.weight is not None:
            parts.append(f"体重{row.weight}kg")
        if row.sleep_hours is not None:
            parts.append(f"睡眠{row.sleep_hours}h")
        return (
            f"已有身体指标记录：{'、'.join(parts)}" if parts else "已有身体指标记录"
        )


class GoalDuplicatePolicy(DuplicatePolicy):
    table_name = "user_goals"

    def build_query(self, dr: DomainRecord):
        g_type = dr.primary_scope.get("type")
        if not g_type:
            return None
        return (
            select(UserGoal)
            .where(
                UserGoal.user_id == dr.user_id,
                UserGoal.goal_type == g_type,
                UserGoal.status.in_(["draft", "active", "paused"]),
            )
            .order_by(UserGoal.id.desc())
            .limit(1)
        )

    def extract_content(self, row: Any) -> dict[str, Any]:
        return dict(row.success_definition_json or {})

    def is_same(self, existing: dict, new: dict) -> bool:
        return False

    def summary(self, row: Any, existing_content: dict) -> str:
        return f"已有进行中的{row.goal_type}目标"


_POLICIES: dict[IntentType, DuplicatePolicy] = {
    IntentType.RECORD_MEAL: MealDuplicatePolicy(),
    IntentType.RECORD_WORKOUT: WorkoutDuplicatePolicy(),
    IntentType.RECORD_BODY_METRIC: BodyMetricDuplicatePolicy(),
    IntentType.SET_GOAL: GoalDuplicatePolicy(),
}


class MySQLDuplicateChecker:
    """实现 IDuplicateChecker：按意图选用策略，查库并比较内容。"""

    async def check(self, dr: DomainRecord) -> Optional[DuplicateHit]:
        dr.user_id = await get_or_create_user_id(dr.user_id)
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
