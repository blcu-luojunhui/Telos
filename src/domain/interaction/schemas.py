"""
自然语言解析后的结构化 Schema。

意图类型与各意图对应的 payload，与数据层表结构（workouts / meals / body_metrics / goals）对齐。
"""

import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class IntentType(str, Enum):
    """用户一句话可能表达的意图（记录类 + 后续可扩展查询等）。"""

    RECORD_WORKOUT = "record_workout"  # 做了什么运动/训练
    RECORD_MEAL = "record_meal"  # 吃了什么
    RECORD_BODY_METRIC = "record_body_metric"  # 体重、体脂、睡眠等身体指标
    SET_GOAL = "set_goal"  # 目标（减脂、半马等）
    RECORD_STATUS = "record_status"  # 状态/心情/感受（今日整体）
    UNKNOWN = "unknown"


# ---------- 各意图的 Payload ----------


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


class RecordStatusPayload(BaseModel):
    """记录当日整体状态/心情/感受（非单次训练或单餐）。"""

    mood: Optional[int] = Field(None, ge=1, le=10)
    energy: Optional[int] = Field(None, ge=1, le=10, description="精力/疲劳感")
    stress_level: Optional[int] = Field(None, ge=1, le=10)
    note: Optional[str] = Field(
        None, description="自由描述，如「今天很累」「心情一般」"
    )


# ---------- 解析结果 ----------


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
