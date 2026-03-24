"""
查询与编辑/删除类 LangChain Tools。

将查询、编辑、删除操作封装为 StructuredTool，供 Agent 通过 tool calling 调用。
实际执行委托给应用层注入的 IQueryRunner / IEditDeleteRunner 端口实现。
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from src.domain.interaction.ports import IEditDeleteRunner, IQueryRunner

_query_runner: Optional[IQueryRunner] = None
_edit_delete_runner: Optional[IEditDeleteRunner] = None


def configure_query_tools(
    *,
    query_runner: IQueryRunner,
    edit_delete_runner: IEditDeleteRunner,
) -> None:
    """
    配置查询/编辑/删除工具所依赖的基础设施实现。

    说明：为保持 domain 层纯净，这里不直接 import infra 的具体实现。
    应用层启动时（例如 create_app / register_routes）调用一次完成注入即可。
    """
    global _query_runner, _edit_delete_runner
    _query_runner = query_runner
    _edit_delete_runner = edit_delete_runner


# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------

class QueryRecordsInput(BaseModel):
    user_id: str = Field(description="用户 ID")
    intent: str = Field(description="查询类意图: query_workout | query_meal | query_body_metric | query_summary")
    date_range: str = Field(default="today", description="时间范围: today | yesterday | last_7_days | last_30_days")
    sub_type: Optional[str] = Field(None, description="可选子类型筛选，如 workout_type 或 meal_type")


class EditLastInput(BaseModel):
    user_id: str = Field(description="用户 ID")
    record_type: Optional[str] = Field(None, description="记录类型: workout | meal | body_metric | goal")
    updates: dict[str, Any] = Field(default_factory=dict, description="要修改的字段和值")
    reference_date: Optional[str] = Field(None, description="参考日期 YYYY-MM-DD")


class DeleteRecordInput(BaseModel):
    user_id: str = Field(description="用户 ID")
    record_type: str = Field(description="记录类型: workout | meal | body_metric | goal")
    record_id: Optional[int] = Field(None, description="记录 ID")
    record_date: Optional[str] = Field(None, description="记录日期 YYYY-MM-DD")
    meal_type: Optional[str] = Field(None, description="餐次（仅 meal 类型）")
    workout_type: Optional[str] = Field(None, description="运动类型（仅 workout 类型）")


# ---------------------------------------------------------------------------
# Tool 实现
# ---------------------------------------------------------------------------

async def _query_records(
    user_id: str,
    intent: str,
    date_range: str = "today",
    sub_type: Optional[str] = None,
) -> str:
    if _query_runner is None:
        raise RuntimeError(
            "query_records tool 未配置：请先调用 configure_query_tools(query_runner=..., edit_delete_runner=...)"
        )
    payload: dict[str, Any] = {"date_range": date_range}
    if sub_type:
        if "meal" in intent:
            payload["meal_type"] = sub_type
        elif "workout" in intent:
            payload["workout_type"] = sub_type

    result = await _query_runner.run(
        user_id=user_id,
        intent=intent,
        payload=payload,
        reference_date=date.today(),
    )

    if not result.get("ok"):
        return f"查询失败：{result.get('error', '未知错误')}"

    summary = result.get("summary", "")
    data = result.get("data")

    if isinstance(data, list) and data:
        lines = [summary]
        for item in data[:10]:
            if isinstance(item, dict):
                parts = [v for v in [
                    item.get("date"),
                    item.get("type") or item.get("meal_type"),
                    item.get("food_items"),
                    f"{item['distance_km']}km" if item.get("distance_km") is not None else None,
                    f"{item['duration_min']}分钟" if item.get("duration_min") is not None else None,
                    f"体重{item['weight']}kg" if item.get("weight") is not None else None,
                    f"睡眠{item['sleep_hours']}h" if item.get("sleep_hours") is not None else None,
                ] if v is not None]
                lines.append("· " + " ".join(str(p) for p in parts))
        if isinstance(data, list) and len(data) > 10:
            lines.append(f"… 共 {len(data)} 条")
        return "\n".join(lines)

    return summary or "查询完成，无数据。"


async def _edit_last(
    user_id: str,
    record_type: Optional[str] = None,
    updates: Optional[dict[str, Any]] = None,
    reference_date: Optional[str] = None,
) -> str:
    if _edit_delete_runner is None:
        raise RuntimeError(
            "edit_last tool 未配置：请先调用 configure_query_tools(query_runner=..., edit_delete_runner=...)"
        )

    ref = None
    if reference_date:
        try:
            ref = date.fromisoformat(reference_date[:10])
        except (ValueError, TypeError):
            ref = None

    result = await _edit_delete_runner.edit_last(
        user_id=user_id,
        record_type=record_type,
        updates=updates or {},
        reference_date=ref,
    )

    if result.get("ok"):
        return f"已修改记录（id={result.get('id')}）。"
    return f"修改失败：{result.get('error', '未知错误')}"


async def _delete_record(
    user_id: str,
    record_type: str,
    record_id: Optional[int] = None,
    record_date: Optional[str] = None,
    meal_type: Optional[str] = None,
    workout_type: Optional[str] = None,
) -> str:
    if _edit_delete_runner is None:
        raise RuntimeError(
            "delete_record tool 未配置：请先调用 configure_query_tools(query_runner=..., edit_delete_runner=...)"
        )

    d = None
    if record_date:
        try:
            d = date.fromisoformat(record_date[:10])
        except (ValueError, TypeError):
            d = None

    result = await _edit_delete_runner.delete_record(
        user_id=user_id,
        record_type=record_type,
        record_id=record_id,
        date=d,
        meal_type=meal_type,
        workout_type=workout_type,
    )

    if result.get("ok"):
        return f"已删除记录（id={result.get('id')}）。"
    return f"删除失败：{result.get('error', '未知错误')}"


# ---------------------------------------------------------------------------
# StructuredTool 注册
# ---------------------------------------------------------------------------

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
