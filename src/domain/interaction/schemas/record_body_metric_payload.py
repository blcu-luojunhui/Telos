import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class RecordBodyMetricPayload(BaseModel):
    """记录身体指标。"""

    weight: Optional[float] = None  # kg
    body_fat: Optional[float] = None  # %
    muscle_mass: Optional[float] = None
    resting_hr: Optional[int] = None
    bp_systolic: Optional[int] = None
    bp_diastolic: Optional[int] = None
    sleep_hours: Optional[float] = None
    note: Optional[str] = None
