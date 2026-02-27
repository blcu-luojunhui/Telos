"""
交互层：自然语言理解 + 结构化落表。

- nlu.parser: 用户自然语言 → 意图 + 结构化 payload
- schemas: 意图与 payload 的 Pydantic 模型
- record_service: 根据解析结果写入 MySQL（workouts / meals / body_metrics / goals）
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
from .nlu.parser import parse_user_message
from .record_service import apply_parsed_record

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
]

