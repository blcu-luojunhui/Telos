"""
MySQL 编辑/删除执行器：实现 IEditDeleteRunner，修改或删除已有记录。
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy import select, update

from src.infra.database.mysql import (
    ActivityRecordV2,
    MeasurementItemV2,
    NutritionItemV2,
    NutritionRecordV2,
    Record,
    StatusRecordV2,
    UserGoal,
    Plan,
    async_mysql_pool,
)
from src.infra.persistence.mysql_user_identity import get_or_create_user_id


async def _find_latest_record(session, user_id: int, record_type: str) -> Optional[Any]:
    result = await session.execute(
        select(Record)
        .where(
            Record.user_id == user_id,
            Record.record_type == record_type,
            Record.status == "active",
        )
        .order_by(Record.id.desc())
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
        uid = await get_or_create_user_id(user_id)

        async with async_mysql_pool.session() as session:
            rt = (record_type or "").strip().lower()
            if rt in ("", "workout"):
                row = await _find_latest_record(session, uid, "activity")
                if not row:
                    return {"ok": False, "id": None, "error": "没有找到可修改的最近记录"}
                allowed = {
                    "type": "activity_type",
                    "duration_min": "duration_min",
                    "distance_km": "distance_km",
                    "avg_pace": "avg_pace_sec_per_km",
                    "avg_hr": "avg_hr",
                    "calories": "calories",
                    "subjective_fatigue": "subjective_fatigue",
                    "sleep_quality": "sleep_quality",
                    "mood": "mood",
                    "motivation": "motivation",
                    "stress_level": "stress_level",
                    "note": "note",
                }
                values = {allowed[k]: v for k, v in updates.items() if k in allowed}
                if not values:
                    return {"ok": False, "id": row.id, "error": "没有可应用的修改字段"}
                await session.execute(
                    update(ActivityRecordV2).where(ActivityRecordV2.record_id == row.id).values(**values)
                )
                await session.commit()
                return {"ok": True, "id": row.id, "error": None}

            if rt == "meal":
                row = await _find_latest_record(session, uid, "nutrition")
                if not row:
                    return {"ok": False, "id": None, "error": "没有找到可修改的最近记录"}
                allowed = {
                    "meal_type": "meal_type",
                    "estimated_calories": "estimated_calories",
                    "protein_g": "protein_g",
                    "carb_g": "carb_g",
                    "fat_g": "fat_g",
                    "satiety": "satiety",
                    "mood": "mood",
                    "stress_level": "stress_level",
                    "note": "note",
                }
                values = {allowed[k]: v for k, v in updates.items() if k in allowed}
                has_food_items = "food_items" in updates and updates["food_items"] is not None
                if not values and not has_food_items:
                    return {"ok": False, "id": row.id, "error": "没有可应用的修改字段"}
                if values:
                    await session.execute(
                        update(NutritionRecordV2).where(NutritionRecordV2.record_id == row.id).values(**values)
                    )
                if has_food_items:
                    await session.execute(
                        update(NutritionItemV2)
                        .where(NutritionItemV2.record_id == row.id)
                        .values(food_name=str(updates["food_items"])[:128])
                    )
                await session.commit()
                return {"ok": True, "id": row.id, "error": None}

            if rt == "body_metric":
                row = await _find_latest_record(session, uid, "measurement")
                if not row:
                    return {"ok": False, "id": None, "error": "没有找到可修改的最近记录"}
                metric_fields = {
                    "weight": "weight",
                    "body_fat": "body_fat",
                    "muscle_mass": "muscle_mass",
                    "resting_hr": "resting_hr",
                    "bp_systolic": "bp_systolic",
                    "bp_diastolic": "bp_diastolic",
                    "sleep_hours": "sleep_hours",
                }
                updated = False
                for k, code in metric_fields.items():
                    if k not in updates:
                        continue
                    updated = True
                    await session.execute(
                        update(MeasurementItemV2)
                        .where(
                            MeasurementItemV2.record_id == row.id,
                            MeasurementItemV2.metric_code == code,
                        )
                        .values(numeric_value=updates[k])
                    )
                if not updated:
                    return {"ok": False, "id": row.id, "error": "没有可应用的修改字段"}
                await session.commit()
                return {"ok": True, "id": row.id, "error": None}

            if rt == "goal":
                goal_q = await session.execute(
                    select(UserGoal)
                    .where(UserGoal.user_id == uid, UserGoal.status.in_(["draft", "active", "paused"]))
                    .order_by(UserGoal.id.desc())
                    .limit(1)
                )
                goal = goal_q.scalars().first()
                if not goal:
                    return {"ok": False, "id": None, "error": "没有找到可修改的最近记录"}
                allowed = {
                    "type": "goal_type",
                    "title": "title",
                    "target": "success_definition_json",
                    "deadline": "target_date",
                    "note": "note",
                    "status": "status",
                }
                values = {allowed[k]: v for k, v in updates.items() if k in allowed}
                if not values:
                    return {"ok": False, "id": goal.id, "error": "没有可应用的修改字段"}
                await session.execute(update(UserGoal).where(UserGoal.id == goal.id).values(**values))
                await session.commit()
                return {"ok": True, "id": goal.id, "error": None}

            return {"ok": False, "id": None, "error": f"未知记录类型: {record_type}"}

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
        uid = await get_or_create_user_id(user_id)

        rt = record_type.lower()
        async with async_mysql_pool.session() as session:
            if rt in ("workout", "meal", "body_metric"):
                record_type_map = {
                    "workout": "activity",
                    "meal": "nutrition",
                    "body_metric": "measurement",
                }
                db_type = record_type_map[rt]
                if record_id is not None:
                    result = await session.execute(
                        select(Record).where(
                            Record.id == record_id,
                            Record.user_id == uid,
                            Record.record_type == db_type,
                        )
                    )
                    row = result.scalars().first()
                elif rt == "meal" and date_arg and meal_type:
                    result = await session.execute(
                        select(Record)
                        .join(NutritionRecordV2, NutritionRecordV2.record_id == Record.id)
                        .where(
                            Record.user_id == uid,
                            Record.record_type == "nutrition",
                            Record.local_date == date_arg,
                            NutritionRecordV2.meal_type == meal_type,
                            Record.status == "active",
                        )
                        .order_by(Record.id.desc())
                        .limit(1)
                    )
                    row = result.scalars().first()
                elif rt == "workout" and date_arg and workout_type:
                    result = await session.execute(
                        select(Record)
                        .join(ActivityRecordV2, ActivityRecordV2.record_id == Record.id)
                        .where(
                            Record.user_id == uid,
                            Record.record_type == "activity",
                            Record.local_date == date_arg,
                            ActivityRecordV2.activity_type == workout_type,
                            Record.status == "active",
                        )
                        .order_by(Record.id.desc())
                        .limit(1)
                    )
                    row = result.scalars().first()
                else:
                    row = await _find_latest_record(session, uid, db_type)

                if not row:
                    return {"ok": False, "id": None, "error": "没有找到要删除的记录"}
                await session.execute(
                    update(Record).where(Record.id == row.id).values(status="deleted")
                )
                await session.commit()
                return {"ok": True, "id": row.id, "error": None}

            if rt == "goal":
                if record_id is not None:
                    result = await session.execute(
                        select(UserGoal).where(UserGoal.id == record_id, UserGoal.user_id == uid)
                    )
                    row = result.scalars().first()
                else:
                    result = await session.execute(
                        select(UserGoal)
                        .where(UserGoal.user_id == uid, UserGoal.status.in_(["draft", "active", "paused"]))
                        .order_by(UserGoal.id.desc())
                        .limit(1)
                    )
                    row = result.scalars().first()
                if not row:
                    return {"ok": False, "id": None, "error": "没有找到要删除的记录"}
                await session.execute(update(UserGoal).where(UserGoal.id == row.id).values(status="abandoned"))
                await session.commit()
                return {"ok": True, "id": row.id, "error": None}

            if rt in ("training_plan", "plan"):
                if record_id is not None:
                    result = await session.execute(
                        select(Plan).where(Plan.id == record_id, Plan.user_id == uid)
                    )
                    row = result.scalars().first()
                else:
                    result = await session.execute(
                        select(Plan)
                        .where(Plan.user_id == uid, Plan.status == "active")
                        .order_by(Plan.id.desc())
                        .limit(1)
                    )
                    row = result.scalars().first()
                if not row:
                    return {"ok": False, "id": None, "error": "没有找到要删除的记录"}
                await session.execute(update(Plan).where(Plan.id == row.id).values(status="archived"))
                await session.commit()
                return {"ok": True, "id": row.id, "error": None}

            return {"ok": False, "id": None, "error": f"未知记录类型: {record_type}"}
