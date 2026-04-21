"""
每日提醒任务：定时检查并发送每日计划提醒。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

logger = logging.getLogger("jobs")


async def send_daily_reminders() -> None:
    """
    每小时执行一次，检查并发送每日计划提醒。
    """
    try:
        from src.infra.persistence.mysql_reminder_repository import (
            get_users_needing_reminder,
            update_reminder_sent_time,
        )
        from src.infra.persistence.mysql_session_store import MySQLSessionStore
        from src.domain.interaction.chains.daily_reminder_chain import (
            generate_daily_reminder,
        )

        current_hour = datetime.now().hour
        logger.info(f"Starting daily reminder check for hour {current_hour}")

        # 查询需要提醒的用户
        users = await get_users_needing_reminder(current_hour)

        if not users:
            logger.info("No users need reminder at this hour")
            return

        session_store = MySQLSessionStore()
        success_count = 0
        fail_count = 0

        for user_id, user_code, soul_id in users:
            try:
                # 生成提醒内容
                reminder_content = await generate_daily_reminder(user_id, soul_id)

                if not reminder_content:
                    logger.info(f"No plan items for user {user_code}, skipping reminder")
                    continue

                # 获取或创建会话
                conv_id = await session_store.get_or_create_conversation(user_code)
                user_session = session_store.get_user_session(user_code, conv_id)

                # 发送系统消息
                await user_session.add_turn(
                    role="system",
                    content=reminder_content,
                    msg_type="daily_reminder",
                    extra={
                        "reminder_type": "daily_plan",
                        "sent_at": datetime.utcnow().isoformat(),
                    },
                    soul_id=None,
                )

                # 更新最后发送时间
                await update_reminder_sent_time(user_id)

                success_count += 1
                logger.info(f"Sent daily reminder to user {user_code}")

            except Exception as e:
                fail_count += 1
                logger.error(f"Failed to send reminder to user {user_code}: {e}", exc_info=True)

        logger.info(
            f"Daily reminder task completed: {success_count} success, {fail_count} failed"
        )

    except Exception as e:
        logger.error(f"Daily reminder task failed: {e}", exc_info=True)


def run_daily_reminder_sync() -> None:
    """
    同步包装器，用于 APScheduler 调用。
    """
    try:
        # 获取或创建事件循环
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(send_daily_reminders())
    except Exception as e:
        logger.error(f"Failed to run daily reminder task: {e}", exc_info=True)
