""" """

from datetime import date
from typing import Any

from src.core.database.mysql import async_mysql_pool
from src.domain.interaction.schemas import IntentType, ParsedRecord

from ._body_metric import insert_body_metric
from ._body_metric import insert_status
from ._goal import insert_goal
from ._meal import insert_meal
from ._workout import insert_workout


async def apply_parsed_record(parsed: ParsedRecord) -> dict[str, Any]:
    """
    根据 ParsedRecord 落表，并返回本次写入摘要。

    :param parsed: parse_user_message 的返回
    :return: {"ok": True/False, "intent": ..., "table": ..., "id": ..., "error": ...}
    """
    if parsed.intent == IntentType.UNKNOWN:
        return {
            "ok": False,
            "intent": "unknown",
            "table": None,
            "id": None,
            "error": "意图无法识别",
        }

    payload = parsed.payload or {}
    d = parsed.date or date.today()
    uid = parsed.user_id

    async with async_mysql_pool.session() as session:
        try:
            if parsed.intent == IntentType.RECORD_WORKOUT:
                row = await insert_workout(session, uid, d, payload)
                await session.commit()
                return {
                    "ok": True,
                    "intent": "record_workout",
                    "table": "workouts",
                    "id": row.id,
                }

            if parsed.intent == IntentType.RECORD_MEAL:
                row = await insert_meal(session, uid, d, payload)
                await session.commit()
                return {
                    "ok": True,
                    "intent": "record_meal",
                    "table": "meals",
                    "id": row.id,
                }

            if parsed.intent == IntentType.RECORD_BODY_METRIC:
                row = await insert_body_metric(session, uid, d, payload)
                await session.commit()
                return {
                    "ok": True,
                    "intent": "record_body_metric",
                    "table": "body_metrics",
                    "id": row.id,
                }

            if parsed.intent == IntentType.SET_GOAL:
                row = await insert_goal(session, uid, payload)
                await session.commit()
                return {
                    "ok": True,
                    "intent": "set_goal",
                    "table": "goals",
                    "id": row.id,
                }

            if parsed.intent == IntentType.RECORD_STATUS:
                row = await insert_status(session, uid, d, payload, parsed.raw_message)
                await session.commit()
                return {
                    "ok": True,
                    "intent": "record_status",
                    "table": "body_metrics",
                    "id": row.id,
                }

        except Exception as e:
            await session.rollback()
            return {
                "ok": False,
                "intent": parsed.intent.value,
                "table": None,
                "id": None,
                "error": str(e),
            }

    return {
        "ok": False,
        "intent": parsed.intent.value,
        "table": None,
        "id": None,
        "error": "未处理意图",
    }


__all__ = ["apply_parsed_record"]
