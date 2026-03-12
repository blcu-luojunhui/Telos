"""
交互层：基于 LangChain 的自然语言理解 + 结构化落表 + 对话管理。

子模块：
- schemas: 意图枚举、ParsedRecord、各意图 payload Pydantic 模型
- nlu: 预处理 + 归一化 + 校验（确定性规则），通过 chains.nlu_chain 调用 LLM
- chains: LCEL 链 —— NLU 解析链、JSON 修复链、小聊天链
- tools: 记录/查询/编辑删除操作封装为 LangChain StructuredTool
- agents: 主交互 Agent，路由 NLU → 记录 / 查询 / 对话
- record: 各意图的落库函数
- chat: 回复模型 (ChatResponse)、展示格式化、slot 补全、表情包
- duplicate_checker: 重复检测领域模型
- ports: 领域端口 Protocol 定义
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
from .chat import ChatResponse
from .agents import run_interaction_agent

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
    "ChatResponse",
    "run_interaction_agent",
]
