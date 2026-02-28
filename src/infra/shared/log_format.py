"""
统一日志格式配置：带表情、易读。
"""

import logging
import sys


class PrettyFormatter(logging.Formatter):
    """带表情的日志格式，便于快速扫读"""

    LEVEL_EMOJI = {
        logging.DEBUG: "🔍",
        logging.INFO: "📌",
        logging.WARNING: "⚠️ ",
        logging.ERROR: "❌",
        logging.CRITICAL: "💥",
    }

    def format(self, record: logging.LogRecord) -> str:
        emoji = self.LEVEL_EMOJI.get(record.levelno, "  ")
        time = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        msg = record.getMessage()
        return f"  {emoji}  {time}  ›  {msg}"


def setup_logging(level: int = logging.INFO) -> None:
    """配置根 logger：输出到 stdout，使用 PrettyFormatter。"""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(PrettyFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
