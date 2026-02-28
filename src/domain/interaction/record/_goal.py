""" """

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.mysql import Goal
from .utils import _get, _parse_date


async def insert_goal(session: AsyncSession, payload: dict) -> Goal:
    g = Goal(
        type=_get(payload, "type") or "maintenance",
        target=_get(payload, "target"),
        deadline=_parse_date(_get(payload, "deadline")),
        status="ongoing",
        note=_get(payload, "note"),
    )
    session.add(g)
    await session.flush()
    return g
