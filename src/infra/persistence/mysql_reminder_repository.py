"""
提醒相关数据库操作：查询需要提醒的用户、更新提醒状态。
"""

from __future__ import annotations

import logging
from datetime import datetime, date
from typing import List, Tuple

from sqlalchemy import select, update, and_, or_

logger = logging.getLogger("jobs")


async def get_users_needing_reminder(current_hour: int) -> List[Tuple[int, str, str]]:
    """
    查询当前小时需要发送提醒的用户列表。

    :param current_hour: 当前小时（0-23）
    :return: [(user_id, user_code, soul_id), ...]
    """
    from src.infra.database.mysql import async_mysql_pool
    from src.infra.database.mysql.models_v2 import (
        UserPreference,
        UserProfileV2,
        Plan,
    )

    today = date.today()
    current_hour_str = f"{current_hour:02d}:00"

    users_to_remind = []

    async with async_mysql_pool.session() as session:
        # 查询提醒偏好匹配当前小时的用户
        result = await session.execute(
            select(
                UserPreference.user_id,
                UserPreference.reminder_preferences_json,
                UserProfileV2.user_code,
                UserProfileV2.soul_id,
            )
            .join(UserProfileV2, UserPreference.user_id == UserProfileV2.user_id)
            .where(
                and_(
                    UserPreference.reminder_preferences_json.isnot(None),
                )
            )
        )

        for user_id, prefs, user_code, soul_id in result:
            if not prefs or not isinstance(prefs, dict):
                continue

            # 检查是否启用提醒
            if not prefs.get("daily_plan_reminder_enabled", False):
                continue

            # 检查提醒时间是否匹配
            preferred_time = prefs.get("preferred_reminder_time", "08:00")
            if preferred_time != current_hour_str:
                continue

            # 检查今天是否已发送
            last_sent = prefs.get("last_reminder_sent_at")
            if last_sent:
                try:
                    last_sent_date = datetime.fromisoformat(last_sent).date()
                    if last_sent_date >= today:
                        logger.debug(f"User {user_id} already received reminder today")
                        continue
                except (ValueError, TypeError):
                    pass

            # 检查是否有活跃的计划
            plan_result = await session.execute(
                select(Plan.id)
                .where(
                    and_(
                        Plan.user_id == user_id,
                        Plan.status == "active",
                    )
                )
                .limit(1)
            )
            if not plan_result.scalar_one_or_none():
                logger.debug(f"User {user_id} has no active plan")
                continue

            users_to_remind.append((user_id, user_code, soul_id or "gentle"))

    logger.info(f"Found {len(users_to_remind)} users needing reminder at {current_hour_str}")
    return users_to_remind


async def update_reminder_sent_time(user_id: int) -> None:
    """
    更新用户的最后提醒发送时间。

    :param user_id: 用户内部 ID
    """
    from src.infra.database.mysql import async_mysql_pool
    from src.infra.database.mysql.models_v2 import UserPreference

    now = datetime.utcnow().isoformat()

    async with async_mysql_pool.session() as session:
        # 获取当前偏好
        result = await session.execute(
            select(UserPreference.reminder_preferences_json)
            .where(UserPreference.user_id == user_id)
        )
        prefs = result.scalar_one_or_none()

        if prefs and isinstance(prefs, dict):
            prefs["last_reminder_sent_at"] = now

            await session.execute(
                update(UserPreference)
                .where(UserPreference.user_id == user_id)
                .values(reminder_preferences_json=prefs)
            )
            await session.commit()
            logger.debug(f"Updated reminder sent time for user {user_id}")
