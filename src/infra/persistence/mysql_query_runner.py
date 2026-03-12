"""
MySQL 查询执行器：实现 IQueryRunner，按意图与 payload 查库并返回结构化结果。
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from sqlalchemy import select, func

from src.infra.database.mysql import (
    async_mysql_pool,
    Workout,
    Meal,
    BodyMetric,
    Goal,
)
from src.domain.interaction.schemas import IntentType


def _resolve_date_range(
    payload: dict,
    reference_date: date,
) -> tuple[date, date]:
    """根据 payload 的 date_range 或 start_date/end_date 得到 (start, end)。"""
    start = end = reference_date
    dr = (payload.get("date_range") or "").strip().lower()
    if dr == "today":
        return reference_date, reference_date
    if dr == "yesterday":
        d = reference_date - timedelta(days=1)
        return d, d
    if dr == "last_7_days":
        return reference_date - timedelta(days=6), reference_date
    if dr == "last_30_days":
        return reference_date - timedelta(days=29), reference_date

    sd = payload.get("start_date")
    ed = payload.get("end_date")
    if isinstance(sd, str):
        try:
            start = date.fromisoformat(sd[:10])
        except Exception:
            start = reference_date - timedelta(days=6)
    elif isinstance(sd, date):
        start = sd
    if isinstance(ed, str):
        try:
            end = date.fromisoformat(ed[:10])
        except Exception:
            end = reference_date
    elif isinstance(ed, date):
        end = ed
    if start > end:
        start, end = end, start
    return start, end


def _workout_to_dict(row: Any) -> dict:
    return {
        "id": row.id,
        "date": row.date.isoformat() if row.date else None,
        "type": row.type,
        "duration_min": row.duration_min,
        "distance_km": row.distance_km,
        "avg_pace": row.avg_pace,
        "calories": row.calories,
        "note": row.note,
    }


def _meal_to_dict(row: Any) -> dict:
    return {
        "id": row.id,
        "date": row.date.isoformat() if row.date else None,
        "meal_type": row.meal_type,
        "food_items": row.food_items,
        "estimated_calories": row.estimated_calories,
        "note": row.note,
    }


def _body_metric_to_dict(row: Any) -> dict:
    return {
        "id": row.id,
        "date": row.date.isoformat() if row.date else None,
        "weight": row.weight,
        "body_fat": row.body_fat,
        "sleep_hours": row.sleep_hours,
        "note": row.note,
    }


class MySQLQueryRunner:
    """实现 IQueryRunner：查 workouts / meals / body_metrics 并返回列表或汇总。"""

    async def run(
        self,
        user_id: str,
        intent: str,
        payload: dict[str, Any],
        reference_date: Optional[date] = None,
    ) -> dict[str, Any]:
        ref = reference_date or date.today()
        payload = payload or {}

        if intent == IntentType.QUERY_WORKOUT.value:
            return await self._query_workouts(user_id, payload, ref)
        if intent == IntentType.QUERY_MEAL.value:
            return await self._query_meals(user_id, payload, ref)
        if intent == IntentType.QUERY_BODY_METRIC.value:
            return await self._query_body_metrics(user_id, payload, ref)
        if intent == IntentType.QUERY_SUMMARY.value:
            return await self._query_summary(user_id, payload, ref)

        return {"ok": False, "data": [], "summary": "", "error": f"未知查询意图: {intent}"}

    async def _query_workouts(
        self,
        user_id: str,
        payload: dict,
        ref: date,
    ) -> dict[str, Any]:
        start, end = _resolve_date_range(payload, ref)
        w_type = payload.get("workout_type") or payload.get("type")

        async with async_mysql_pool.session() as session:
            q = (
                select(Workout)
                .where(
                    Workout.user_id == user_id,
                    Workout.date >= start,
                    Workout.date <= end,
                    Workout.status == "active",
                )
                .order_by(Workout.date.desc(), Workout.id.desc())
            )
            if w_type:
                q = q.where(Workout.type == w_type)
            result = await session.execute(q)
            rows = result.scalars().all()
        data = [_workout_to_dict(r) for r in rows]
        total_km = sum((r.get("distance_km") or 0) for r in data)
        total_min = sum((r.get("duration_min") or 0) for r in data)
        summary = f"共 {len(data)} 条运动记录"
        if total_km > 0 or total_min > 0:
            parts = []
            if total_km > 0:
                parts.append(f"总距离 {total_km}km")
            if total_min > 0:
                parts.append(f"总时长 {total_min} 分钟")
            summary += "，" + "，".join(parts)
        return {"ok": True, "data": data, "summary": summary, "error": None}

    async def _query_meals(
        self,
        user_id: str,
        payload: dict,
        ref: date,
    ) -> dict[str, Any]:
        start, end = _resolve_date_range(payload, ref)
        meal_type = payload.get("meal_type")

        async with async_mysql_pool.session() as session:
            q = (
                select(Meal)
                .where(
                    Meal.user_id == user_id,
                    Meal.date >= start,
                    Meal.date <= end,
                    Meal.status == "active",
                )
                .order_by(Meal.date.desc(), Meal.id.desc())
            )
            if meal_type:
                q = q.where(Meal.meal_type == meal_type)
            result = await session.execute(q)
            rows = result.scalars().all()
        data = [_meal_to_dict(r) for r in rows]
        total_cal = sum((r.get("estimated_calories") or 0) for r in data)
        summary = f"共 {len(data)} 条饮食记录"
        if total_cal > 0:
            summary += f"，预估总热量约 {total_cal} 千卡"
        return {"ok": True, "data": data, "summary": summary, "error": None}

    async def _query_body_metrics(
        self,
        user_id: str,
        payload: dict,
        ref: date,
    ) -> dict[str, Any]:
        start, end = _resolve_date_range(payload, ref)

        async with async_mysql_pool.session() as session:
            q = (
                select(BodyMetric)
                .where(
                    BodyMetric.user_id == user_id,
                    BodyMetric.date >= start,
                    BodyMetric.date <= end,
                    BodyMetric.status == "active",
                )
                .order_by(BodyMetric.date.desc(), BodyMetric.id.desc())
            )
            result = await session.execute(q)
            rows = result.scalars().all()
        data = [_body_metric_to_dict(r) for r in rows]
        summary = f"共 {len(data)} 条身体指标记录"
        return {"ok": True, "data": data, "summary": summary, "error": None}

    async def _query_summary(
        self,
        user_id: str,
        payload: dict,
        ref: date,
    ) -> dict[str, Any]:
        start, end = _resolve_date_range(payload, ref)

        async with async_mysql_pool.session() as session:
            w_count = await session.execute(
                select(func.count(Workout.id)).where(
                    Workout.user_id == user_id,
                    Workout.date >= start,
                    Workout.date <= end,
                    Workout.status == "active",
                )
            )
            m_count = await session.execute(
                select(func.count(Meal.id)).where(
                    Meal.user_id == user_id,
                    Meal.date >= start,
                    Meal.date <= end,
                    Meal.status == "active",
                )
            )
            b_count = await session.execute(
                select(func.count(BodyMetric.id)).where(
                    BodyMetric.user_id == user_id,
                    BodyMetric.date >= start,
                    BodyMetric.date <= end,
                    BodyMetric.status == "active",
                )
            )
            n_workouts = w_count.scalar() or 0
            n_meals = m_count.scalar() or 0
            n_body = b_count.scalar() or 0

        summary = f"在 {start} 至 {end} 内：运动 {n_workouts} 条，饮食 {n_meals} 条，身体指标 {n_body} 条。"
        return {
            "ok": True,
            "data": {
                "workouts_count": n_workouts,
                "meals_count": n_meals,
                "body_metrics_count": n_body,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            },
            "summary": summary,
            "error": None,
        }
