"""
用户活跃时间分析：分析用户历史活跃时间，推荐最佳提醒时间。
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.sql import and_

logger = logging.getLogger("jobs")


async def analyze_user_active_hours(user_id: int) -> dict[int, int]:
    """
    分析用户最近 30 天的活跃时间分布。

    :param user_id: 用户内部 ID
    :return: {hour: count} 字典，hour 为 0-23
    """
    from src.infra.database.mysql import async_mysql_pool
    from src.infra.database.mysql.models_runtime import ChatMessage
    from src.infra.database.mysql.models_v2 import Record, UserProfileV2

    # 获取用户时区
    async with async_mysql_pool.session() as session:
        result = await session.execute(
            select(UserProfileV2.timezone).where(UserProfileV2.user_id == user_id)
        )
        timezone = result.scalar_one_or_none() or "Asia/Shanghai"

    # 查询最近 30 天的活动
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    hour_counter = Counter()

    async with async_mysql_pool.session() as session:
        # 分析聊天消息时间
        chat_result = await session.execute(
            select(ChatMessage.created_at)
            .where(
                and_(
                    ChatMessage.user_id == user_id,
                    ChatMessage.role == "user",
                    ChatMessage.created_at >= thirty_days_ago,
                )
            )
        )
        for (created_at,) in chat_result:
            # 简化处理：假设 created_at 已经是 UTC，转换为用户本地时间
            # 实际应该使用 pytz 进行时区转换
            local_hour = created_at.hour
            hour_counter[local_hour] += 1

        # 分析记录创建时间
        record_result = await session.execute(
            select(Record.created_at)
            .where(
                and_(
                    Record.user_id == user_id,
                    Record.created_at >= thirty_days_ago,
                )
            )
        )
        for (created_at,) in record_result:
            local_hour = created_at.hour
            hour_counter[local_hour] += 1

    return dict(hour_counter)


async def recommend_reminder_time(user_id: int) -> str:
    """
    根据用户活跃时间推荐最佳提醒时间。

    :param user_id: 用户内部 ID
    :return: 推荐时间字符串，格式 "HH:MM"
    """
    try:
        hour_distribution = await analyze_user_active_hours(user_id)

        if not hour_distribution:
            # 没有历史数据，返回默认时间
            logger.info(f"No activity data for user {user_id}, using default time 08:00")
            return "08:00"

        # 找到活跃度最高的时段
        most_active_hour = max(hour_distribution, key=hour_distribution.get)

        # 提前 1 小时提醒（如果用户 9 点最活跃，8 点提醒）
        reminder_hour = (most_active_hour - 1) % 24

        logger.info(
            f"User {user_id} most active at {most_active_hour}:00, "
            f"recommending reminder at {reminder_hour:02d}:00"
        )

        return f"{reminder_hour:02d}:00"

    except Exception as e:
        logger.error(f"Failed to analyze user {user_id} activity: {e}")
        return "08:00"


async def get_or_create_reminder_preference(user_id: int) -> dict:
    """
    获取或创建用户的提醒偏好设置。

    :param user_id: 用户内部 ID
    :return: 提醒偏好字典
    """
    from sqlalchemy import update
    from src.infra.database.mysql import async_mysql_pool
    from src.infra.database.mysql.models_v2 import UserPreference

    async with async_mysql_pool.session() as session:
        result = await session.execute(
            select(UserPreference.reminder_preferences_json)
            .where(UserPreference.user_id == user_id)
        )
        prefs = result.scalar_one_or_none()

        if prefs and isinstance(prefs, dict):
            # 已有偏好设置
            if "preferred_reminder_time" not in prefs:
                # 补充推荐时间
                prefs["preferred_reminder_time"] = await recommend_reminder_time(user_id)
            return prefs

        # 创建新的偏好设置
        recommended_time = await recommend_reminder_time(user_id)
        new_prefs = {
            "daily_plan_reminder_enabled": True,
            "preferred_reminder_time": recommended_time,
            "last_reminder_sent_at": None,
            "reminder_timezone": "Asia/Shanghai",
        }

        # 更新或插入
        existing = await session.execute(
            select(UserPreference.id).where(UserPreference.user_id == user_id)
        )
        if existing.scalar_one_or_none():
            await session.execute(
                update(UserPreference)
                .where(UserPreference.user_id == user_id)
                .values(reminder_preferences_json=new_prefs)
            )
        else:
            session.add(
                UserPreference(
                    user_id=user_id,
                    reminder_preferences_json=new_prefs,
                )
            )

        await session.commit()
        logger.info(f"Created reminder preference for user {user_id}: {new_prefs}")

        return new_prefs
