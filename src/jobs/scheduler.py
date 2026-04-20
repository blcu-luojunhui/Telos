"""
APScheduler 调度器初始化：管理后台定时任务。
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("jobs")

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """获取全局调度器实例。"""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
    return _scheduler


def init_scheduler() -> None:
    """
    初始化并启动调度器，注册所有定时任务。

    应在应用启动时调用（app.py 的 before_serving 钩子中）。
    """
    from src.jobs.daily_reminder import send_daily_reminders

    scheduler = get_scheduler()

    # 每小时整点执行一次每日提醒检查
    scheduler.add_job(
        send_daily_reminders,
        trigger=CronTrigger(minute=0),
        id="daily_reminder_check",
        name="每日计划提醒检查",
        replace_existing=True,
        misfire_grace_time=300,
    )

    scheduler.start()
    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))


def shutdown_scheduler() -> None:
    """关闭调度器。应在应用关闭时调用。"""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")
        _scheduler = None
