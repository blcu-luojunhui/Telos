import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class SetGoalPayload(BaseModel):
    """设定目标。"""

    type: str = Field(
        ..., description="weight_loss / muscle_gain / maintenance / race / ..."
    )
    target: Optional[dict[str, Any]] = (
        None  # 按 type 不同，如 race: race_type, race_date, target_time, ...
    )
    deadline: Optional[datetime.date] = None
    note: Optional[str] = None
