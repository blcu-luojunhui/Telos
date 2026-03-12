from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.database.mysql import BodyMetric
from .utils import _get


async def insert_body_metric(
    session: AsyncSession, user_id: str, d: date, payload: dict
) -> BodyMetric:
    b = BodyMetric(
        user_id=user_id,
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


async def insert_status(
    session: AsyncSession, user_id: str, d: date, payload: dict, raw: str
) -> BodyMetric:
    """今日状态写入 body_metrics：用 note 存描述，可选 mood/精力/压力。"""
    note = _get(payload, "note") or raw
    b = BodyMetric(
        user_id=user_id,
        date=d,
        note=note,
        # 若后续 body_metrics 表加 mood/energy/stress 字段可在这里填
    )
    session.add(b)
    await session.flush()
    return b
