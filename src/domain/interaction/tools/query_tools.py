"""
查询与编辑/删除类 LangChain Tools。

将查询、编辑、删除操作封装为 StructuredTool，供 Agent 通过 tool calling 调用。
实际执行委托给 ports.py 中定义的 IQueryRunner / IEditDeleteRunner 端口。
"""

from __future__ import annotations

from typing import Any, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


class QueryRecordsInput(BaseModel):
    user_id: str = Field(description="用户 ID")
    intent: str = Field(description="查询类意图: query_workout | query_meal | query_body_metric | query_summary")
    date_range: str = Field(default="today", description="时间范围: today | yesterday | last_7_days | last_30_days")
    sub_type: Optional[str] = Field(None, description="可选子类型筛选，如 workout_type 或 meal_type")


class EditLastInput(BaseModel):
    user_id: str = Field(description="用户 ID")
    record_type: Optional[str] = Field(None, description="记录类型: workout | meal | body_metric")
    updates: dict[str, Any] = Field(default_factory=dict, description="要修改的字段和值")
    reference_date: Optional[str] = Field(None, description="参考日期 YYYY-MM-DD")


class DeleteRecordInput(BaseModel):
    user_id: str = Field(description="用户 ID")
    record_type: str = Field(description="记录类型: workout | meal | body_metric | goal")
    record_id: Optional[int] = Field(None, description="记录 ID")
    record_date: Optional[str] = Field(None, description="记录日期 YYYY-MM-DD")
    meal_type: Optional[str] = Field(None, description="餐次（仅 meal 类型）")
    workout_type: Optional[str] = Field(None, description="运动类型（仅 workout 类型）")


# TODO: 以下为占位实现，实际应通过 IQueryRunner / IEditDeleteRunner 端口注入

async def _query_records(
    user_id: str,
    intent: str,
    date_range: str = "today",
    sub_type: Optional[str] = None,
) -> str:
    raise NotImplementedError(
        f"query_records 尚未对接 IQueryRunner 端口 (intent={intent}, user_id={user_id})"
    )


async def _edit_last(
    user_id: str,
    record_type: Optional[str] = None,
    updates: Optional[dict[str, Any]] = None,
    reference_date: Optional[str] = None,
) -> str:
    raise NotImplementedError(
        f"edit_last 尚未对接 IEditDeleteRunner 端口 (record_type={record_type})"
    )


async def _delete_record(
    user_id: str,
    record_type: str,
    record_id: Optional[int] = None,
    record_date: Optional[str] = None,
    meal_type: Optional[str] = None,
    workout_type: Optional[str] = None,
) -> str:
    raise NotImplementedError(
        f"delete_record 尚未对接 IEditDeleteRunner 端口 (record_type={record_type})"
    )


query_records_tool = StructuredTool.from_function(
    coroutine=_query_records,
    name="query_records",
    description="查询用户的运动、饮食、身体指标或汇总记录。",
    args_schema=QueryRecordsInput,
)

edit_last_tool = StructuredTool.from_function(
    coroutine=_edit_last,
    name="edit_last",
    description="修改用户上一条记录的指定字段。",
    args_schema=EditLastInput,
)

delete_record_tool = StructuredTool.from_function(
    coroutine=_delete_record,
    name="delete_record",
    description="删除用户的指定记录。",
    args_schema=DeleteRecordInput,
)


def get_query_tools() -> list[StructuredTool]:
    """返回所有查询/编辑/删除类 Tools。"""
    return [query_records_tool, edit_last_tool, delete_record_tool]
