"""
重复检测领域模型与归一化（不依赖数据库）。

- to_domain_record(parsed, user_id, ref_date, history) 将 NLU 结果归一为 DomainRecord（含餐次推断）
- build_domain_record_and_inject_meal 同上并对 RECORD_MEAL 回写 meal_type 到 parsed.payload
- 实际查库与判重由基础设施层实现 IDuplicateChecker（见 infra.persistence）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Sequence

from src.domain.interaction.duplicate_checker.domain_record import (
    DomainRecord,
    to_domain_record,
)
from src.domain.interaction.schemas import IntentType, ParsedRecord


@dataclass
class DuplicateHit:
    existing_id: int
    table: str
    same_content: bool
    summary: str


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
    "build_domain_record_and_inject_meal",
]
