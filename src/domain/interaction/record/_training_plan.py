from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.database.mysql import TrainingPlan, Goal


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
    goal: Goal,
    today: date,
) -> dict[str, Any] | None:
    target: dict[str, Any] = goal.target or {}
    race_type = (target.get("race_type") or "").strip() or "race"
    # 优先使用 target.race_date，其次 goal.deadline
    race_date_str = (target.get("race_date") or "").strip() or None
    end_date = goal.deadline
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
        "goal_type": goal.type,
        "race_type": race_type,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "title": title,
        "days": days,
    }


def _build_simple_weight_loss_plan(goal: Goal, today: date) -> dict[str, Any]:
    target = goal.target or {}
    start_weight = target.get("start_weight")
    target_weight = target.get("target_weight")

    end_date = _safe_date(goal.deadline, today + timedelta(weeks=12))
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
        "goal_type": goal.type,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "title": title,
        "days": days,
    }


async def maybe_create_training_plan_for_goal(
    session: AsyncSession,
    user_id: str,
    goal: Goal,
    today: Optional[date] = None,
) -> Optional[TrainingPlan]:
    """
    根据 Goal 自动生成一个基础训练计划并写入 training_plans 表。
    若无法生成（例如缺少关键信息），则返回 None，不报错。
    """
    today = today or date.today()

    plan_struct: Optional[dict[str, Any]] = None
    if goal.type == "race":
        plan_struct = _build_simple_race_plan(goal, today)
    elif goal.type == "weight_loss":
        plan_struct = _build_simple_weight_loss_plan(goal, today)

    if not plan_struct:
        return None

    tp = TrainingPlan(
        user_id=user_id,
        title=plan_struct.get("title") or "训练计划",
        goal_type=plan_struct.get("goal_type") or goal.type,
        start_date=today,
        end_date=date.fromisoformat(plan_struct["end_date"])
        if plan_struct.get("end_date")
        else None,
        plan=plan_struct,
        status="active",
    )
    session.add(tp)
    # 由外层事务统一 flush/commit
    await session.flush()
    return tp

