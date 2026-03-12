from typing import Optional

from pydantic import BaseModel, Field


class RecordStatusPayload(BaseModel):
    """记录当日整体状态/心情/感受（非单次训练或单餐）。"""

    mood: Optional[int] = Field(None, ge=1, le=10)
    energy: Optional[int] = Field(None, ge=1, le=10, description="精力/疲劳感")
    stress_level: Optional[int] = Field(None, ge=1, le=10)
    note: Optional[str] = Field(
        None, description="自由描述，如「今天很累」「心情一般」"
    )
