from enum import Enum


class IntentType(str, Enum):
    """用户一句话可能表达的意图（记录类 + 查询类 + 编辑删除）。"""

    # 记录类
    RECORD_WORKOUT = "record_workout"  # 做了什么运动/训练
    RECORD_MEAL = "record_meal"  # 吃了什么
    RECORD_BODY_METRIC = "record_body_metric"  # 体重、体脂、睡眠等身体指标
    SET_GOAL = "set_goal"  # 目标（减脂、半马等）
    RECORD_STATUS = "record_status"  # 状态/心情/感受（今日整体）
    # 查询类
    QUERY_WORKOUT = "query_workout"  # 查运动记录
    QUERY_MEAL = "query_meal"  # 查饮食记录
    QUERY_BODY_METRIC = "query_body_metric"  # 查身体指标
    QUERY_SUMMARY = "query_summary"  # 查汇总（多类/今日概览）
    REQUEST_PLAN = "request_plan"  # 要求制定/查看训练计划（可与 set_goal 同时出现）
    # 编辑/删除
    EDIT_LAST = "edit_last"  # 修改上一条记录
    DELETE_RECORD = "delete_record"  # 删除某条记录
    UNKNOWN = "unknown"
