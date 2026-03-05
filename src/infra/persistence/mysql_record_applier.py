"""
MySQL 记录落库适配器：实现 IRecordApplier，支持覆盖时先软删再写入。
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import update

from src.infra.database.mysql import (
    async_mysql_pool,
    Workout,
    Meal,
    BodyMetric,
    Goal,
)
from src.domain.interaction.record import apply_parsed_record
from src.domain.interaction.schemas import IntentType, ParsedRecord


async def _soft_delete_existing(
    intent: IntentType,
    record_id: int,
    user_id: str,
) -> None:
    """逻辑删除：将当前用户下该条旧记录 status 设为 'replaced'。"""
    model_map = {
        IntentType.RECORD_WORKOUT: Workout,
        IntentType.RECORD_MEAL: Meal,
        IntentType.RECORD_BODY_METRIC: BodyMetric,
        IntentType.SET_GOAL: Goal,
    }
    model = model_map.get(intent)
    if not model or not (user_id or "").strip():
        return
    async with async_mysql_pool.session() as session:
        await session.execute(
            update(model)
            .where(model.id == record_id, model.user_id == user_id)
            .values(status="replaced")
        )
        await session.commit()


class MySQLRecordApplier:
    """实现 IRecordApplier：落表并可选先软删旧记录。"""

    async def apply(
        self,
        parsed: ParsedRecord,
        replace_id: Optional[int] = None,
    ) -> dict[str, Any]:
        if replace_id is not None and (parsed.user_id or "").strip():
            await _soft_delete_existing(parsed.intent, replace_id, parsed.user_id)
        return await apply_parsed_record(parsed)
