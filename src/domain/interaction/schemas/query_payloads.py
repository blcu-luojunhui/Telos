"""
查询类意图的 payload 结构：时间范围、筛选条件等。
"""

from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, Field


class QueryWorkoutPayload(BaseModel):
    """查询运动记录。"""

    date_range: Optional[str] = Field(
        None,
        description="today | yesterday | last_7_days | last_30_days",
    )
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    workout_type: Optional[str] = None  # run | basketball | strength | other，空表示全部


class QueryMealPayload(BaseModel):
    """查询饮食记录。"""

    date_range: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    meal_type: Optional[str] = None  # breakfast | lunch | dinner | snack，空表示全部


class QueryBodyMetricPayload(BaseModel):
    """查询身体指标。"""

    date_range: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class QuerySummaryPayload(BaseModel):
    """查询汇总/今日概览。"""

    date_range: Optional[str] = Field(default="today")
    start_date: Optional[date] = None
    end_date: Optional[date] = None
