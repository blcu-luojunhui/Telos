""" """

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.mysql import Workout
from .utils import _get


async def insert_workout(
    session: AsyncSession, user_id: str, d: date, payload: dict
) -> Workout:
    w = Workout(
        user_id=user_id,
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
