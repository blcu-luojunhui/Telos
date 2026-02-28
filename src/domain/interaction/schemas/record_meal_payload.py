import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class RecordMealPayload(BaseModel):
    """记录饮食。"""

    meal_type: str = Field(..., description="breakfast / lunch / dinner / snack")
    food_items: str = Field(..., description="吃了什么，自由文本")
    estimated_calories: Optional[int] = None
    protein_g: Optional[float] = None
    carb_g: Optional[float] = None
    fat_g: Optional[float] = None
    satiety: Optional[int] = Field(None, ge=1, le=10)
    mood: Optional[int] = Field(None, ge=1, le=10)
    stress_level: Optional[int] = Field(None, ge=1, le=10)
    note: Optional[str] = None