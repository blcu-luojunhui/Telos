"""
每日提醒内容生成：查询用户今日计划并生成个性化提醒消息。
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import select, and_

logger = logging.getLogger("jobs")


async def generate_daily_reminder(
    user_id: int,
    soul_id: Optional[str] = None,
) -> Optional[str]:
    """
    生成用户的每日计划提醒内容。

    :param user_id: 用户内部 ID
    :param soul_id: Agent 人格 ID（可选）
    :return: 提醒消息文本，如果没有计划则返回 None
    """
    from src.infra.database.mysql import async_mysql_pool
    from src.infra.database.mysql.models_v2 import (
        Plan,
        PlanItem,
        UserGoal,
        PlanGoalLink,
    )

    today = date.today()

    async with async_mysql_pool.session() as session:
        # 查询今日待完成的计划项
        result = await session.execute(
            select(PlanItem)
            .where(
                and_(
                    PlanItem.user_id == user_id,
                    PlanItem.item_date == today,
                    PlanItem.status == "pending",
                )
            )
            .order_by(PlanItem.order_in_day)
        )
        plan_items = result.scalars().all()

        if not plan_items:
            logger.info(f"No pending plan items for user {user_id} on {today}")
            return None

        # 查询活跃的目标
        goal_result = await session.execute(
            select(UserGoal)
            .where(
                and_(
                    UserGoal.user_id == user_id,
                    UserGoal.status == "active",
                )
            )
            .order_by(UserGoal.priority.desc())
            .limit(1)
        )
        active_goal = goal_result.scalar_one_or_none()

    # 构建提醒消息
    message_parts = []

    # 根据人格调整开场白
    if soul_id == "rude":
        greeting = "起来了？今天的计划别忘了啊"
    elif soul_id == "gentle":
        greeting = "早上好呀～今天也要加油哦"
    elif soul_id == "professional":
        greeting = "今日计划提醒"
    elif soul_id == "funny":
        greeting = "嘿！新的一天开始啦，看看今天要干啥"
    else:
        greeting = "早上好！今天的计划来了"

    message_parts.append(greeting)

    # 添加目标信息（如果有）
    if active_goal:
        goal_title = active_goal.title or "当前目标"
        if soul_id == "rude":
            message_parts.append(f"\n你的目标：{goal_title}，别忘了")
        elif soul_id == "gentle":
            message_parts.append(f"\n为了「{goal_title}」这个目标")
        elif soul_id == "professional":
            message_parts.append(f"\n目标：{goal_title}")
        else:
            message_parts.append(f"\n目标：{goal_title}")

    # 添加今日计划项
    message_parts.append("\n\n今日计划：")

    for idx, item in enumerate(plan_items, 1):
        item_type = item.item_type
        instruction = item.instruction_json or {}

        if item_type == "workout":
            # 运动计划
            workout_type = instruction.get("workout_type", "训练")
            duration = instruction.get("duration_minutes")
            distance = instruction.get("distance_km")

            if distance:
                desc = f"{workout_type} {distance}公里"
            elif duration:
                desc = f"{workout_type} {duration}分钟"
            else:
                desc = workout_type

            message_parts.append(f"{idx}. {desc}")

        elif item_type == "nutrition_target":
            # 饮食目标
            calories = instruction.get("target_calories")
            protein = instruction.get("target_protein_g")

            if calories and protein:
                desc = f"饮食控制：热量 {calories} 卡，蛋白质 {protein}g"
            elif calories:
                desc = f"饮食控制：热量 {calories} 卡"
            else:
                desc = "注意饮食"

            message_parts.append(f"{idx}. {desc}")

        elif item_type == "recovery":
            # 恢复日
            desc = instruction.get("description", "恢复休息")
            message_parts.append(f"{idx}. {desc}")

        elif item_type == "rest":
            # 休息日
            message_parts.append(f"{idx}. 休息日")

        else:
            # 其他类型
            desc = instruction.get("description", "待完成")
            message_parts.append(f"{idx}. {desc}")

    # 添加结尾鼓励语
    if soul_id == "rude":
        message_parts.append("\n\n别偷懒，干就完了")
    elif soul_id == "gentle":
        message_parts.append("\n\n慢慢来，一步一步完成就好～")
    elif soul_id == "professional":
        message_parts.append("\n\n请按计划执行")
    elif soul_id == "funny":
        message_parts.append("\n\n冲鸭！今天也要元气满满！")
    else:
        message_parts.append("\n\n加油，一起变得更好！")

    return "".join(message_parts)


async def get_yesterday_completion_summary(user_id: int) -> Optional[str]:
    """
    获取昨日计划完成情况摘要（可选功能）。

    :param user_id: 用户内部 ID
    :return: 昨日完成情况文本
    """
    from src.infra.database.mysql import async_mysql_pool
    from src.infra.database.mysql.models_v2 import PlanItem

    yesterday = date.today() - timedelta(days=1)

    async with async_mysql_pool.session() as session:
        result = await session.execute(
            select(PlanItem.status)
            .where(
                and_(
                    PlanItem.user_id == user_id,
                    PlanItem.item_date == yesterday,
                )
            )
        )
        statuses = [row[0] for row in result]

    if not statuses:
        return None

    total = len(statuses)
    done = statuses.count("done")
    skipped = statuses.count("skipped")

    if done == total:
        return f"昨天完成度 100%，全部搞定了！"
    elif done > 0:
        completion_rate = int((done / total) * 100)
        return f"昨天完成了 {done}/{total} 项（{completion_rate}%）"
    else:
        return "昨天没有完成计划项"
