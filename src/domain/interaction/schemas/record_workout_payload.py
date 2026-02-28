from typing import Optional

from pydantic import BaseModel, Field


class RecordWorkoutPayload(BaseModel):
    """记录训练：跑步、篮球、力量等。"""

    type: str = Field(..., description="run / basketball / strength / other")
    duration_min: Optional[int] = None
    distance_km: Optional[float] = None
    avg_pace: Optional[float] = None  # min/km
    avg_hr: Optional[int] = None
    calories: Optional[int] = None
    subjective_fatigue: Optional[int] = Field(None, ge=1, le=10)
    sleep_quality: Optional[int] = Field(None, ge=1, le=10)
    mood: Optional[int] = Field(None, ge=1, le=10)
    motivation: Optional[int] = Field(None, ge=1, le=10)
    stress_level: Optional[int] = Field(None, ge=1, le=10)
    note: Optional[str] = None