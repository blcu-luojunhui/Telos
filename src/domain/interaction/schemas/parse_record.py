import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field
from .intent_type import IntentType


class ParsedRecord(BaseModel):
    """单条用户输入解析结果。"""

    intent: IntentType
    date: Optional[datetime.date] = Field(
        default=None, description="若用户未说日期则用当天"
    )
    payload: Optional[dict[str, Any]] = Field(
        default=None, description="与 intent 对应的结构化数据"
    )
    raw_message: str = Field(default="", description="用户原始输入")