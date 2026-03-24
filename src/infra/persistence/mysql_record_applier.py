"""
MySQL 记录落库适配器：实现 IRecordApplier，支持覆盖时先软删再写入。
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import update

from src.infra.database.mysql import (
    async_mysql_pool,
    Record,
)
from src.domain.interaction.record import apply_parsed_record
from src.domain.interaction.schemas import ParsedRecord


async def _soft_delete_existing(
    record_id: int,
    user_id: str,  # user_code
) -> None:
    """V2 逻辑覆盖：统一 records.status= 'superseded'。"""
    from src.infra.persistence.mysql_user_identity import get_or_create_user_id

    if not (user_id or "").strip():
        return
    uid = await get_or_create_user_id(user_id)
    async with async_mysql_pool.session() as session:
        await session.execute(
            update(Record)
            .where(Record.id == record_id, Record.user_id == uid, Record.status == "active")
            .values(status="superseded", supersedes_record_id=None)
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
            await _soft_delete_existing(replace_id, parsed.user_id)
        return await apply_parsed_record(parsed)
