"""
展示与格式化工具：将解析结果转为人类可读文本。
"""

from __future__ import annotations

from src.domain.interaction.schemas import IntentType, ParsedRecord


def parsed_dict(p: ParsedRecord) -> dict:
    return {
        "intent": p.intent.value,
        "date": p.date.isoformat() if p.date else None,
        "payload": p.payload,
        "raw_message": p.raw_message,
    }


def intent_cn(intent: IntentType) -> str:
    return {
        IntentType.RECORD_WORKOUT: "运动训练",
        IntentType.RECORD_MEAL: "饮食",
        IntentType.RECORD_BODY_METRIC: "身体指标",
        IntentType.SET_GOAL: "目标",
        IntentType.RECORD_STATUS: "今日状态",
        IntentType.QUERY_WORKOUT: "运动记录",
        IntentType.QUERY_MEAL: "饮食记录",
        IntentType.QUERY_BODY_METRIC: "身体指标",
        IntentType.QUERY_SUMMARY: "汇总",
        IntentType.REQUEST_PLAN: "训练计划",
        IntentType.EDIT_LAST: "修改上一条",
        IntentType.DELETE_RECORD: "删除记录",
    }.get(intent, str(intent.value))


def slot_type_cn(slot: str) -> str:
    """计划内训练类型中文。"""
    return {
        "rest": "休息",
        "easy": "轻松跑",
        "long_run": "长距离",
        "quality": "节奏/间歇",
        "cardio": "有氧",
        "strength": "力量",
        "long_walk": "长时间步行",
    }.get((slot or "").strip().lower(), slot or "训练")


def format_plan_preview_message(plan_preview: dict, max_days: int = 14) -> str:
    """
    将计划预览格式化为专业、简洁的说明文案，供对话展示。
    含标题、周期、及近期安排摘要（按周/日）。
    """
    if not plan_preview or not isinstance(plan_preview, dict):
        return "暂无计划预览。"
    title = (plan_preview.get("title") or "训练计划").strip()
    start = (plan_preview.get("start_date") or "").strip()
    end = (plan_preview.get("end_date") or "").strip()
    days = plan_preview.get("days") or []
    lines = [f"【{title}】", f"周期：{start} 至 {end}"]
    if not days:
        return "\n".join(lines)
    total_sessions = sum(len(d.get("sessions") or []) for d in days)
    lines.append(f"共 {len(days)} 天、{total_sessions} 次训练安排。")
    lines.append("")
    # 近期（最多 max_days 天）逐日摘要
    for i, day in enumerate(days[:max_days]):
        date_str = day.get("date") or ""
        week_idx = day.get("week_index")
        sessions = day.get("sessions") or []
        if not sessions:
            lines.append(f"  {date_str}  第{week_idx}周  休息")
        else:
            parts = [f"  {date_str}  第{week_idx}周"]
            for s in sessions:
                st = (s.get("slot_type") or "").strip() or "训练"
                parts.append(slot_type_cn(st))
            lines.append("  ".join(parts))
            for s in sessions:
                summary = (s.get("summary") or "").strip()
                if summary and len(summary) <= 80:
                    lines.append(f"    → {summary}")
                elif summary:
                    lines.append(f"    → {summary[:78]}…")
    if len(days) > max_days:
        lines.append(f"  … 后续 {len(days) - max_days} 天详见完整计划。")
    lines.append("")
    lines.append("确认后请点击「确认计划」保存；保存后训练日前一天会提醒你。")
    return "\n".join(lines)


def format_query_reply(
    intent: IntentType,
    query_result: dict,
    max_items: int = 5,
) -> str:
    """将查询结果格式化为给用户看的自然语言。"""
    if not query_result.get("ok"):
        return query_result.get("error") or "查询失败，请稍后再试。"
    summary = query_result.get("summary") or ""
    data = query_result.get("data")
    if isinstance(data, list) and data:
        lines = [summary]
        for i, item in enumerate(data[:max_items]):
            if isinstance(item, dict):
                if "food_items" in item:
                    lines.append(f"· {item.get('meal_type', '')} {item.get('food_items', '')}")
                elif "type" in item and "distance_km" in item:
                    dur = item.get('duration_min')
                    dur_str = f" {dur}分钟" if dur is not None else ""
                    lines.append(
                        f"· {item.get('date', '')} {workout_type_cn(item.get('type', ''))} "
                        f"{item.get('distance_km')}km{dur_str}"
                    )
                elif "weight" in item or "sleep_hours" in item:
                    parts = [item.get("date", "")]
                    if item.get("weight"):
                        parts.append(f"体重{item['weight']}kg")
                    if item.get("sleep_hours"):
                        parts.append(f"睡眠{item['sleep_hours']}h")
                    lines.append(" · ".join(parts))
                else:
                    lines.append(f"· {item}")
        if len(data) > max_items:
            lines.append(f"… 共 {len(data)} 条")
        return "\n".join(lines)
    if isinstance(data, dict):
        return summary
    return summary


def payload_summary(intent: IntentType, payload: dict) -> str:
    parts: list[str] = []
    if intent == IntentType.RECORD_MEAL:
        if payload.get("meal_type"):
            parts.append(meal_type_cn(payload["meal_type"]))
        if payload.get("food_items"):
            parts.append(payload["food_items"])
    elif intent == IntentType.RECORD_WORKOUT:
        if payload.get("type"):
            parts.append(workout_type_cn(payload["type"]))
        if payload.get("duration_min"):
            parts.append(f"{payload['duration_min']}分钟")
        if payload.get("distance_km"):
            parts.append(f"{payload['distance_km']}km")
    elif intent == IntentType.RECORD_BODY_METRIC:
        if payload.get("weight"):
            parts.append(f"体重{payload['weight']}kg")
        if payload.get("sleep_hours"):
            parts.append(f"睡眠{payload['sleep_hours']}h")
    elif intent == IntentType.SET_GOAL:
        if payload.get("type"):
            parts.append(payload["type"])
    elif intent == IntentType.RECORD_STATUS:
        if payload.get("note"):
            parts.append(payload["note"])
    return "、".join(parts)


def meal_type_cn(t: str) -> str:
    return {
        "breakfast": "早餐",
        "lunch": "午餐",
        "dinner": "晚餐",
        "snack": "加餐",
    }.get(t, t)


def workout_type_cn(t: str) -> str:
    return {"run": "跑步", "basketball": "篮球", "strength": "力量训练"}.get(t, t)
