from __future__ import annotations

from datetime import date, time as dt_time, timedelta
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.database.mysql import Plan, PlanGoalLink, PlanItem, PlanVersion, UserGoal


def _safe_date(d: Optional[date], fallback: date) -> date:
    return d if isinstance(d, date) else fallback


def _phase_by_ratio(ratio: float) -> str:
    """根据进度比例粗略划分阶段。"""
    if ratio < 0.25:
        return "base"  # 打基础
    if ratio < 0.6:
        return "build"  # 提升期
    if ratio < 0.85:
        return "peak"  # 冲刺前
    return "taper"  # 减量/调整


def _race_type_title(race_type: str | None) -> str:
    mapping = {
        "half_marathon": "半程马拉松",
        "marathon": "全程马拉松",
        "full_marathon": "全程马拉松",
        "10k": "10 公里",
        "5k": "5 公里",
    }
    return mapping.get((race_type or "").lower(), race_type or "比赛")


def _build_simple_race_plan(
    goal: UserGoal,
    today: date,
) -> dict[str, Any] | None:
    target: dict[str, Any] = goal.success_definition_json or {}
    race_type = (target.get("race_type") or "").strip() or "race"
    # 优先使用 target.race_date，其次 goal.deadline
    race_date_str = (target.get("race_date") or "").strip() or None
    end_date = goal.target_date
    if race_date_str:
        try:
            y, m, d = [int(x) for x in race_date_str.replace(".", "-").replace("/", "-").split("-")[:3]]
            end_date = date(y, m, d)
        except Exception:
            pass
    end_date = _safe_date(end_date, today + timedelta(weeks=12))
    if end_date <= today:
        end_date = today + timedelta(weeks=4)

    start_date = today
    total_days = (end_date - start_date).days + 1
    if total_days <= 0:
        return None

    days: list[dict[str, Any]] = []
    for i in range(total_days):
        d = start_date + timedelta(days=i)
        dow = d.weekday()  # 0=Mon
        week_index = i // 7 + 1
        ratio = i / max(total_days - 1, 1)
        phase = _phase_by_ratio(ratio)

        # 简单模板：一周 4 天训练（周一、三、五、日）
        if dow in {0, 2, 4, 6}:
            if dow == 6:
                slot = "long_run"
            elif dow == 2:
                slot = "quality"
            else:
                slot = "easy"
        else:
            slot = "rest"

        if slot == "rest":
            summary = "休息或轻松散步 20-40 分钟，重点恢复。"
        elif slot == "easy":
            summary = "轻松跑 30-45 分钟，能轻松说话为宜。"
        elif slot == "quality":
            summary = "节奏跑 / 简单间歇（例如：10 分钟热身 + 3×8 分钟略快配速 + 10 分钟放松）。"
        else:  # long_run
            summary = "长距离慢跑，时间逐周微增，配速放松，不追求速度。"

        if phase == "taper":
            summary += "（减量期：在保证轻松的前提下，适当减少时长和强度。）"

        recovery = "睡眠不少于 7 小时，训练后做拉伸 10-15 分钟，注意补水。"

        days.append(
            {
                "date": d.isoformat(),
                "week_index": week_index,
                "day_of_week": dow,  # 0=周一
                "phase": phase,
                "slot": slot,
                "summary": summary,
                "recovery": recovery,
            }
        )

    title = f"{_race_type_title(race_type)} 训练计划（目标日 {end_date.isoformat()}）"
    return {
        "goal_id": goal.id,
        "goal_type": goal.goal_type,
        "race_type": race_type,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "title": title,
        "days": days,
    }


def _build_simple_weight_loss_plan(goal: UserGoal, today: date) -> dict[str, Any]:
    target = goal.success_definition_json or {}
    start_weight = target.get("start_weight")
    target_weight = target.get("target_weight")

    end_date = _safe_date(goal.target_date, today + timedelta(weeks=12))
    if end_date <= today:
        end_date = today + timedelta(weeks=8)

    start_date = today
    total_days = (end_date - start_date).days + 1

    days: list[dict[str, Any]] = []
    for i in range(total_days):
        d = start_date + timedelta(days=i)
        dow = d.weekday()
        week_index = i // 7 + 1
        ratio = i / max(total_days - 1, 1)
        phase = _phase_by_ratio(ratio)

        if dow in {0, 2, 4}:
            slot = "cardio"
            summary = "中等强度有氧 30-45 分钟（快走 / 慢跑 / 单车）。"
        elif dow in {1, 5}:
            slot = "strength"
            summary = "全身力量训练 30 分钟，优先大肌群，注意动作规范。"
        elif dow == 6:
            slot = "long_walk"
            summary = "长时间步行或轻松活动 45-60 分钟，保持轻微出汗即可。"
        else:
            slot = "rest"
            summary = "主动休息日，可拉伸、散步，避免整天久坐。"

        if phase == "taper":
            summary += "（调整期：更关注恢复和睡眠，避免过度节食和过度训练。）"

        recovery = "保证充足睡眠，保持稳定饮食节奏，避免极端节食或暴饮暴食。"

        days.append(
            {
                "date": d.isoformat(),
                "week_index": week_index,
                "day_of_week": dow,
                "phase": phase,
                "slot": slot,
                "summary": summary,
                "recovery": recovery,
            }
        )

    title = "减脂综合训练计划"
    if isinstance(start_weight, (int, float)) and isinstance(target_weight, (int, float)):
        title += f"（{start_weight}kg → {target_weight}kg）"

    return {
        "goal_id": goal.id,
        "goal_type": goal.goal_type,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "title": title,
        "days": days,
    }


def _to_preview_sessions(day: dict[str, Any]) -> list[dict[str, Any]]:
    """将计划中的一天转为前端需要的 sessions 数组（每天 1 条或休息 1 条）。"""
    slot = day.get("slot") or "rest"
    summary = day.get("summary") or ""
    return [
        {
            "slot_type": slot,
            "summary": summary,
            "scheduled_time": None,
            "remind_day_before": slot != "rest",
        }
    ]


def _plan_struct_to_preview(plan_struct: dict[str, Any]) -> dict[str, Any]:
    """将内部计划结构转为前端表格展示用的预览结构（含 days[].sessions[]）。"""
    days_in = plan_struct.get("days") or []
    days_out = []
    for d in days_in:
        days_out.append({
            "date": d.get("date"),
            "week_index": d.get("week_index"),
            "day_of_week": d.get("day_of_week"),
            "sessions": _to_preview_sessions(d),
        })
    return {
        "goal_id": plan_struct.get("goal_id"),
        "goal_type": plan_struct.get("goal_type"),
        "title": plan_struct.get("title") or "训练计划",
        "start_date": plan_struct.get("start_date"),
        "end_date": plan_struct.get("end_date"),
        "days": days_out,
    }


def build_plan_preview(
    goal: UserGoal,
    today: Optional[date] = None,
) -> Optional[dict[str, Any]]:
    """
    根据目标生成计划预览（不落库），供前端表格展示。
    返回结构见文档 4.1：goal_id, title, start_date, end_date, days[].sessions[]。
    """
    today = today or date.today()
    plan_struct: Optional[dict[str, Any]] = None
    if goal.goal_type == "race":
        plan_struct = _build_simple_race_plan(goal, today)
    elif goal.goal_type == "weight_loss":
        plan_struct = _build_simple_weight_loss_plan(goal, today)
    if not plan_struct:
        return None
    return _plan_struct_to_preview(plan_struct)


async def save_plan(
    session: AsyncSession,
    user_id: str,
    goal_id: int,
    plan_payload: dict[str, Any],
) -> tuple[Plan, int]:
    """
    用户确认后，将计划写入 plans / plan_versions / plan_items。
    plan_payload 为预览接口返回的结构（含 title, start_date, end_date, days[].sessions[]）。
    返回 (training_plan, sessions_count)。
    """
    title = (plan_payload.get("title") or "训练计划").strip() or "训练计划"
    start_date_str = plan_payload.get("start_date")
    end_date_str = plan_payload.get("end_date")
    start_date = date.today()
    end_date = start_date
    if start_date_str:
        try:
            start_date = date.fromisoformat(str(start_date_str)[:10])
        except (ValueError, TypeError):
            pass
    if end_date_str:
        try:
            end_date = date.fromisoformat(str(end_date_str)[:10])
        except (ValueError, TypeError):
            pass

    user_row = await session.execute(select(UserGoal).where(UserGoal.id == goal_id).limit(1))
    goal = user_row.scalars().first()
    if goal is None:
        raise ValueError(f"goal_id {goal_id} not found")

    p = Plan(
        user_id=goal.user_id,
        plan_type="training",
        title=title,
        status="active",
    )
    session.add(p)
    await session.flush()
    pv = PlanVersion(
        plan_id=p.id,
        version_no=1,
        generated_by="agent",
        trigger_type="goal_created",
        summary=title,
        payload_json=plan_payload,
    )
    session.add(pv)
    await session.flush()
    session.add(
        PlanGoalLink(plan_id=p.id, goal_id=goal_id, role="primary", weight=1.0)
    )

    days = plan_payload.get("days") or []
    sessions_count = 0
    for day_item in days:
        day_date_str = day_item.get("date")
        if not day_date_str:
            continue
        try:
            day_date = date.fromisoformat(str(day_date_str)[:10])
        except (ValueError, TypeError):
            continue
        sessions = day_item.get("sessions") or []
        for order_in_day, sess in enumerate(sessions, start=1):
            slot_type = (sess.get("slot_type") or "rest").strip() or "rest"
            summary = (sess.get("summary") or "").strip() or slot_type
            scheduled_time = None
            if sess.get("scheduled_time"):
                t = sess["scheduled_time"]
                if isinstance(t, str) and ":" in t:
                    parts = t.replace(":", " ").split()[:3]
                    if len(parts) >= 2:
                        try:
                            scheduled_time = dt_time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
                        except (ValueError, TypeError):
                            pass
            remind = sess.get("remind_day_before", True)
            if not isinstance(remind, bool):
                remind = bool(remind)

            pi = PlanItem(
                plan_version_id=pv.id,
                user_id=goal.user_id,
                item_date=day_date,
                item_type="workout",
                day_type=(
                    "key_workout_day"
                    if slot_type in ("quality", "long_run")
                    else "easy_day" if slot_type == "easy" else "rest_day"
                ),
                title=summary[:255],
                instruction_json={
                    "slot_type": slot_type,
                    "scheduled_time": scheduled_time.isoformat() if scheduled_time else None,
                    "remind_day_before": remind,
                },
                target_json={"summary": summary},
                status="pending",
                order_in_day=order_in_day,
            )
            session.add(pi)
            sessions_count += 1
    await session.flush()
    return p, sessions_count


async def maybe_create_training_plan_for_goal(
    session: AsyncSession,
    user_id: str,
    goal: UserGoal,
    today: Optional[date] = None,
) -> Optional[Plan]:
    """
    根据 UserGoal 自动生成一个基础训练计划并写入 plans 表。
    若无法生成（例如缺少关键信息），则返回 None，不报错。
    """
    today = today or date.today()

    plan_struct: Optional[dict[str, Any]] = None
    if goal.goal_type == "race":
        plan_struct = _build_simple_race_plan(goal, today)
    elif goal.goal_type == "weight_loss":
        plan_struct = _build_simple_weight_loss_plan(goal, today)

    if not plan_struct:
        return None

    tp = Plan(
        user_id=goal.user_id,
        plan_type="training",
        title=plan_struct.get("title") or "训练计划",
        status="active",
    )
    session.add(tp)
    # 由外层事务统一 flush/commit
    await session.flush()
    return tp

