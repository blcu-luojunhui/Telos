from enum import Enum


class IntentType(str, Enum):
    """用户一句话可能表达的意图（记录类 + 后续可扩展查询等）。"""

    RECORD_WORKOUT = "record_workout"  # 做了什么运动/训练
    RECORD_MEAL = "record_meal"  # 吃了什么
    RECORD_BODY_METRIC = "record_body_metric"  # 体重、体脂、睡眠等身体指标
    SET_GOAL = "set_goal"  # 目标（减脂、半马等）
    RECORD_STATUS = "record_status"  # 状态/心情/感受（今日整体）
    UNKNOWN = "unknown"
