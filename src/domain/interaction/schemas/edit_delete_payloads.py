"""
编辑/删除意图的 payload：指定要操作的记录。
"""

from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, Field


class EditLastPayload(BaseModel):
    """修改上一条记录：可指定类型或由上下文推断。"""

    record_type: Optional[str] = Field(
        None,
        description="workout | meal | body_metric | goal，空则从上文推断",
    )
    # 要修改的字段（只填要改的）
    updates: dict[str, Any] = Field(default_factory=dict)


class DeleteRecordPayload(BaseModel):
    """删除某条记录。"""

    record_type: Optional[str] = Field(
        None, description="workout | meal | body_metric | goal，可由上下文推断"
    )
    record_id: Optional[int] = Field(None, description="若已知 ID 直接删")
    # 或按日期+槽位定位（如 meal: date + meal_type）
    date: Optional[date] = None
    meal_type: Optional[str] = None  # 仅 record_type=meal 时
    workout_type: Optional[str] = None  # 仅 record_type=workout 时
