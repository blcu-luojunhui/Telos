""" """

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.database.mysql import Meal
from .utils import _get


async def insert_meal(
    session: AsyncSession, user_id: str, d: date, payload: dict
) -> Meal:
    m = Meal(
        user_id=user_id,
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
