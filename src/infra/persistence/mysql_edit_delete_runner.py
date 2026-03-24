"""
MySQL 编辑/删除执行器：实现 IEditDeleteRunner，修改或删除已有记录。
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy import select, update

from src.infra.database.mysql import (
    async_mysql_pool,
    Workout,
    Meal,
    BodyMetric,
    Goal,
    TrainingPlan,
)
async def _find_latest_workout(session, user_id: str) -> Optional[Any]:
    result = await session.execute(
        select(Workout)
        .where(Workout.user_id == user_id, Workout.status == "active")
        .order_by(Workout.id.desc())
        .limit(1)
    )
    return result.scalars().first()


async def _find_latest_meal(session, user_id: str) -> Optional[Any]:
    result = await session.execute(
        select(Meal)
        .where(Meal.user_id == user_id, Meal.status == "active")
        .order_by(Meal.id.desc())
        .limit(1)
    )
    return result.scalars().first()


async def _find_latest_body_metric(session, user_id: str) -> Optional[Any]:
    result = await session.execute(
        select(BodyMetric)
        .where(BodyMetric.user_id == user_id, BodyMetric.status == "active")
        .order_by(BodyMetric.id.desc())
        .limit(1)
    )
    return result.scalars().first()


async def _find_latest_goal(session, user_id: str) -> Optional[Any]:
    result = await session.execute(
        select(Goal)
        .where(Goal.user_id == user_id, Goal.status.in_(["planning", "ongoing"]))
        .order_by(Goal.id.desc())
        .limit(1)
    )
    return result.scalars().first()


async def _find_latest_training_plan(session, user_id: str) -> Optional[Any]:
    result = await session.execute(
        select(TrainingPlan)
        .where(TrainingPlan.user_id == user_id, TrainingPlan.status == "active")
        .order_by(TrainingPlan.id.desc())
        .limit(1)
    )
    return result.scalars().first()


class MySQLEditDeleteRunner:
    """实现 IEditDeleteRunner：按类型找上一条记录并更新，或按条件删除。"""

    async def edit_last(
        self,
        user_id: str,
        record_type: Optional[str],
        updates: dict[str, Any],
        reference_date: Optional[date] = None,
    ) -> dict[str, Any]:
        if not (updates or {}):
            return {"ok": False, "id": None, "error": "未指定要修改的字段"}

        async with async_mysql_pool.session() as session:
            row = None
            model = None
            if record_type == "workout" or not record_type:
                row = await _find_latest_workout(session, user_id)
                model = Workout
            if row is None and (record_type == "meal" or not record_type):
                row = await _find_latest_meal(session, user_id)
                model = Meal
            if row is None and (record_type == "body_metric" or not record_type):
                row = await _find_latest_body_metric(session, user_id)
                model = BodyMetric
            if row is None and record_type == "goal":
                row = await _find_latest_goal(session, user_id)
                model = Goal

            if row is None or model is None:
                return {"ok": False, "id": None, "error": "没有找到可修改的最近记录"}

            # 只允许更新部分字段，避免误改
            allowed = set()
            if model == Workout:
                allowed = {
                    "type", "duration_min", "distance_km", "avg_pace", "avg_hr",
                    "calories", "subjective_fatigue", "sleep_quality", "mood",
                    "motivation", "stress_level", "note",
                }
            elif model == Meal:
                allowed = {
                    "meal_type", "food_items", "estimated_calories",
                    "protein_g", "carb_g", "fat_g", "satiety", "mood", "stress_level", "note",
                }
            elif model == BodyMetric:
                allowed = {
                    "weight", "body_fat", "muscle_mass", "resting_hr",
                    "bp_systolic", "bp_diastolic", "sleep_hours", "note",
                }
            elif model == Goal:
                allowed = {"type", "target", "deadline", "note"}

            values = {k: v for k, v in updates.items() if k in allowed}
            if not values:
                return {"ok": False, "id": row.id, "error": "没有可应用的修改字段"}

            await session.execute(
                update(model).where(model.id == row.id).values(**values)
            )
            await session.commit()
            return {"ok": True, "id": row.id, "error": None}

    async def delete_record(
        self,
        user_id: str,
        record_type: str,
        record_id: Optional[int] = None,
        date_arg: Optional[date] = None,
        meal_type: Optional[str] = None,
        workout_type: Optional[str] = None,
    ) -> dict[str, Any]:
        if not record_type:
            return {"ok": False, "id": None, "error": "请指定要删除的记录类型"}

        model_map = {
            "workout": Workout,
            "meal": Meal,
            "body_metric": BodyMetric,
            "goal": Goal,
            "training_plan": TrainingPlan,
            "plan": TrainingPlan,
        }
        model = model_map.get(record_type.lower())
        if not model:
            return {"ok": False, "id": None, "error": f"未知记录类型: {record_type}"}

        async with async_mysql_pool.session() as session:
            if record_id is not None:
                result = await session.execute(
                    select(model).where(
                        model.id == record_id,
                        model.user_id == user_id,
                    )
                )
                row = result.scalars().first()
            elif record_type == "meal" and date_arg and meal_type:
                result = await session.execute(
                    select(Meal)
                    .where(
                        Meal.user_id == user_id,
                        Meal.date == date_arg,
                        Meal.meal_type == meal_type,
                        Meal.status == "active",
                    )
                    .order_by(Meal.id.desc())
                    .limit(1)
                )
                row = result.scalars().first()
            elif record_type == "workout" and date_arg and workout_type:
                result = await session.execute(
                    select(Workout)
                    .where(
                        Workout.user_id == user_id,
                        Workout.date == date_arg,
                        Workout.type == workout_type,
                        Workout.status == "active",
                    )
                    .order_by(Workout.id.desc())
                    .limit(1)
                )
                row = result.scalars().first()
            else:
                # 删除该类型下最新一条
                if model == Workout:
                    row = await _find_latest_workout(session, user_id)
                elif model == Meal:
                    row = await _find_latest_meal(session, user_id)
                elif model == BodyMetric:
                    row = await _find_latest_body_metric(session, user_id)
                elif model == Goal:
                    row = await _find_latest_goal(session, user_id)
                elif model == TrainingPlan:
                    row = await _find_latest_training_plan(session, user_id)
                else:
                    row = None

            if not row:
                return {"ok": False, "id": None, "error": "没有找到要删除的记录"}

            if model == Goal:
                status_value = "abandoned"
            elif model == TrainingPlan:
                status_value = "archived"
            else:
                status_value = "deleted"
            await session.execute(
                update(model).where(model.id == row.id).values(status=status_value)
            )
            await session.commit()
            return {"ok": True, "id": row.id, "error": None}
