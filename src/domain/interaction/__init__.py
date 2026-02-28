"""
交互层：自然语言理解 + 结构化落表 + 对话管理。

- nlu.parser: 用户自然语言 → 意图 + 结构化 payload
- schemas: 意图与 payload 的 Pydantic 模型
- record: 根据解析结果写入 MySQL
- duplicate_checker: 重复记录检测
- chat: 带上下文的对话管理 + 确认流程
"""

from .schemas import (
    ParsedRecord,
    IntentType,
    RecordWorkoutPayload,
    RecordMealPayload,
    RecordBodyMetricPayload,
    SetGoalPayload,
    RecordStatusPayload,
)
from .nlu import parse_user_message
from .record import apply_parsed_record
from .chat import handle_chat_message

__all__ = [
    "ParsedRecord",
    "IntentType",
    "RecordWorkoutPayload",
    "RecordMealPayload",
    "RecordBodyMetricPayload",
    "SetGoalPayload",
    "RecordStatusPayload",
    "parse_user_message",
    "apply_parsed_record",
    "handle_chat_message",
]
