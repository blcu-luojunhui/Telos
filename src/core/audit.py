"""
审计日志：为每次对话请求记录 trace_id 与关键步骤，便于排查「为什么记错了」。
"""

from __future__ import annotations

import json
import logging
import uuid

logger = logging.getLogger("better_me.audit")


def new_trace_id() -> str:
    return str(uuid.uuid4())


def log_chat_step(
    trace_id: str,
    user_id: str,
    step: str,
    intent: str | None = None,
    payload: dict | None = None,
    result: str | None = None,
    error: str | None = None,
):
    """记录对话流水中的一步（NLU 解析、重复检测、落库等）。"""
    record = {
        "trace_id": trace_id,
        "user_id": user_id,
        "step": step,
        "intent": intent,
        "payload": payload,
        "result": result,
        "error": error,
    }
    record = {k: v for k, v in record.items() if v is not None}
    try:
        logger.info("chat_audit %s", json.dumps(record, ensure_ascii=False))
    except Exception:
        logger.info("chat_audit %s", str(record))
