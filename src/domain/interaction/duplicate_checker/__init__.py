"""
重复检测：策略化引擎，根据 DomainRecord 查库并返回 DuplicateHit。

- to_domain_record(parsed, user_id, ref_date, history) 将 NLU 结果归一为 DomainRecord（含餐次推断）
- check_duplicate(dr) 走策略注册表，返回 None 或 DuplicateHit
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Sequence

from src.domain.interaction.duplicate_checker.domain_record import (
    DomainRecord,
    to_domain_record,
)
from src.domain.interaction.duplicate_checker.policies import POLICIES
from src.domain.interaction.schemas import IntentType, ParsedRecord


@dataclass
class DuplicateHit:
    existing_id: int
    table: str
    same_content: bool
    summary: str


async def check_duplicate(dr: DomainRecord) -> Optional[DuplicateHit]:
    """
    统一入口：按意图选用策略，查库并比较内容。
    若有同类记录则返回 DuplicateHit，否则返回 None。
    """
    policy = POLICIES.get(dr.intent)
    if not policy:
        return None

    stmt = policy.build_query(dr)
    if stmt is None:
        return None

    from src.core.database.mysql import async_mysql_pool

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


def build_domain_record_and_inject_meal(
    parsed: ParsedRecord,
    user_id: str,
    ref_date: date,
    history: Optional[Sequence[dict]] = None,
) -> DomainRecord:
    """
    将 ParsedRecord 转为 DomainRecord，并对 RECORD_MEAL 回写 meal_type 到 parsed.payload，
    保证落库与判重使用同一餐次。
    """
    dr = to_domain_record(parsed, user_id, ref_date, history)
    if parsed.intent == IntentType.RECORD_MEAL and "meal_type" in dr.primary_scope:
        if parsed.payload is None:
            parsed.payload = {}
        parsed.payload["meal_type"] = dr.primary_scope["meal_type"]
    return dr


__all__ = [
    "DuplicateHit",
    "DomainRecord",
    "to_domain_record",
    "check_duplicate",
    "build_domain_record_and_inject_meal",
]
