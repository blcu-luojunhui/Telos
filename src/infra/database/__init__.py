"""
基础设施 - 数据库：MySQL、Redis、Elasticsearch、Milvus 连接与模型。
"""

from src.infra.database.mysql import (
    async_mysql_pool,
    Base,
    AsyncMySQL,
    Workout,
    BodyMetric,
    Meal,
    UserProfile,
    Goal,
    TrainingPlan,
    Conversation,
    ChatMessage,
    PendingConfirmation,
)

__all__ = [
    "async_mysql_pool",
    "Base",
    "AsyncMySQL",
    "Workout",
    "BodyMetric",
    "Meal",
    "UserProfile",
    "Goal",
    "TrainingPlan",
    "Conversation",
    "ChatMessage",
    "PendingConfirmation",
]
