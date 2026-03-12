"""
记录类 LangChain Tools：将 record/ 模块的落库操作封装为 StructuredTool。

每个 Tool 接受 Pydantic schema 定义的参数，内部调用 record 子模块的插入函数。
Agent 可通过 tool calling 来执行这些记录操作。
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from src.infra.database.mysql import async_mysql_pool
from src.domain.interaction.record.workout import insert_workout
from src.domain.interaction.record.meal import insert_meal
from src.domain.interaction.record.body_metric import insert_body_metric, insert_status
from src.domain.interaction.record.goal import insert_goal


# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------

class RecordWorkoutInput(BaseModel):
    user_id: str = Field(description="用户 ID")
    record_date: str = Field(description="记录日期，格式 YYYY-MM-DD")
    workout_type: str = Field(description="运动类型: run | basketball | strength | other")
    duration_min: Optional[int] = Field(None, description="时长（分钟）")
    distance_km: Optional[float] = Field(None, description="距离（公里）")
    avg_pace: Optional[float] = Field(None, description="配速（分钟/公里）")
    avg_hr: Optional[int] = Field(None, description="平均心率")
    calories: Optional[int] = Field(None, description="消耗卡路里")
    note: Optional[str] = Field(None, description="备注")


class RecordMealInput(BaseModel):
    user_id: str = Field(description="用户 ID")
    record_date: str = Field(description="记录日期，格式 YYYY-MM-DD")
    meal_type: str = Field(description="餐次: breakfast | lunch | dinner | snack")
    food_items: str = Field(description="吃了什么")
    estimated_calories: Optional[int] = Field(None, description="预估热量")
    note: Optional[str] = Field(None, description="备注")


class RecordBodyMetricInput(BaseModel):
    user_id: str = Field(description="用户 ID")
    record_date: str = Field(description="记录日期，格式 YYYY-MM-DD")
    weight: Optional[float] = Field(None, description="体重（kg）")
    body_fat: Optional[float] = Field(None, description="体脂（%）")
    sleep_hours: Optional[float] = Field(None, description="睡眠时长（小时）")
    note: Optional[str] = Field(None, description="备注")


class RecordStatusInput(BaseModel):
    user_id: str = Field(description="用户 ID")
    record_date: str = Field(description="记录日期，格式 YYYY-MM-DD")
    mood: Optional[int] = Field(None, ge=1, le=10, description="心情 1-10")
    energy: Optional[int] = Field(None, ge=1, le=10, description="精力 1-10")
    stress_level: Optional[int] = Field(None, ge=1, le=10, description="压力 1-10")
    note: Optional[str] = Field(None, description="自由描述")


class SetGoalInput(BaseModel):
    user_id: str = Field(description="用户 ID")
    goal_type: str = Field(description="目标类型: weight_loss | muscle_gain | maintenance | race")
    target: Optional[dict[str, Any]] = Field(None, description="目标详情")
    deadline: Optional[str] = Field(None, description="截止日期，格式 YYYY-MM-DD")
    note: Optional[str] = Field(None, description="备注")


# ---------------------------------------------------------------------------
# 通用落库辅助
# ---------------------------------------------------------------------------

async def _insert_and_commit(insert_fn, label: str, session, *args) -> str:
    """调用 insert_fn 落库并 commit，统一异常处理。"""
    try:
        row = await insert_fn(session, *args)
        await session.commit()
        return f"{label}已保存，ID={row.id}"
    except Exception as e:
        await session.rollback()
        return f"保存失败：{e}"


def _compact(payload: dict) -> dict:
    """去掉值为 None 的字段。"""
    return {k: v for k, v in payload.items() if v is not None}


# ---------------------------------------------------------------------------
# Tool 实现
# ---------------------------------------------------------------------------

async def _record_workout(
    user_id: str,
    record_date: str,
    workout_type: str,
    duration_min: Optional[int] = None,
    distance_km: Optional[float] = None,
    avg_pace: Optional[float] = None,
    avg_hr: Optional[int] = None,
    calories: Optional[int] = None,
    note: Optional[str] = None,
) -> str:
    d = date.fromisoformat(record_date)
    payload = _compact({
        "type": workout_type,
        "duration_min": duration_min,
        "distance_km": distance_km,
        "avg_pace": avg_pace,
        "avg_hr": avg_hr,
        "calories": calories,
        "note": note,
    })
    async with async_mysql_pool.session() as session:
        return await _insert_and_commit(insert_workout, "运动记录", session, user_id, d, payload)


async def _record_meal(
    user_id: str,
    record_date: str,
    meal_type: str,
    food_items: str,
    estimated_calories: Optional[int] = None,
    note: Optional[str] = None,
) -> str:
    d = date.fromisoformat(record_date)
    payload = _compact({
        "meal_type": meal_type,
        "food_items": food_items,
        "estimated_calories": estimated_calories,
        "note": note,
    })
    async with async_mysql_pool.session() as session:
        return await _insert_and_commit(insert_meal, "饮食记录", session, user_id, d, payload)


async def _record_body_metric(
    user_id: str,
    record_date: str,
    weight: Optional[float] = None,
    body_fat: Optional[float] = None,
    sleep_hours: Optional[float] = None,
    note: Optional[str] = None,
) -> str:
    d = date.fromisoformat(record_date)
    payload = _compact({"weight": weight, "body_fat": body_fat, "sleep_hours": sleep_hours, "note": note})
    async with async_mysql_pool.session() as session:
        return await _insert_and_commit(insert_body_metric, "身体指标", session, user_id, d, payload)


async def _record_status(
    user_id: str,
    record_date: str,
    mood: Optional[int] = None,
    energy: Optional[int] = None,
    stress_level: Optional[int] = None,
    note: Optional[str] = None,
) -> str:
    d = date.fromisoformat(record_date)
    payload = _compact({"mood": mood, "energy": energy, "stress_level": stress_level, "note": note})
    async with async_mysql_pool.session() as session:
        return await _insert_and_commit(
            lambda s, uid, dt, p: insert_status(s, uid, dt, p, note or ""),
            "状态记录", session, user_id, d, payload,
        )


async def _set_goal(
    user_id: str,
    goal_type: str,
    target: Optional[dict[str, Any]] = None,
    deadline: Optional[str] = None,
    note: Optional[str] = None,
) -> str:
    payload = _compact({"type": goal_type, "target": target, "deadline": deadline, "note": note})
    async with async_mysql_pool.session() as session:
        return await _insert_and_commit(insert_goal, "目标", session, user_id, payload)


# ---------------------------------------------------------------------------
# StructuredTool 注册
# ---------------------------------------------------------------------------

record_workout_tool = StructuredTool.from_function(
    coroutine=_record_workout,
    name="record_workout",
    description="记录一次运动/训练（跑步、篮球、力量等），写入数据库。",
    args_schema=RecordWorkoutInput,
)

record_meal_tool = StructuredTool.from_function(
    coroutine=_record_meal,
    name="record_meal",
    description="记录一餐饮食，写入数据库。",
    args_schema=RecordMealInput,
)

record_body_metric_tool = StructuredTool.from_function(
    coroutine=_record_body_metric,
    name="record_body_metric",
    description="记录身体指标（体重、体脂、睡眠等），写入数据库。",
    args_schema=RecordBodyMetricInput,
)

record_status_tool = StructuredTool.from_function(
    coroutine=_record_status,
    name="record_status",
    description="记录今日整体状态/心情/感受，写入数据库。",
    args_schema=RecordStatusInput,
)

set_goal_tool = StructuredTool.from_function(
    coroutine=_set_goal,
    name="set_goal",
    description="设定一个目标（减脂、增肌、半马等），写入数据库。",
    args_schema=SetGoalInput,
)


def get_record_tools() -> list[StructuredTool]:
    """返回所有记录类 Tools。"""
    return [
        record_workout_tool,
        record_meal_tool,
        record_body_metric_tool,
        record_status_tool,
        set_goal_tool,
    ]
