from .base import Base, AsyncMySQL
from .models import (
    Workout,
    BodyMetric,
    Meal,
    UserProfile,
    Goal,
    TrainingPlan,
    TrainingPlanSession,
    Soul,
    Conversation,
    ChatMessage,
    PendingConfirmation,
)

# 异步 Mysql POOL
async_mysql_pool = AsyncMySQL()

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
    "TrainingPlanSession",
    "Soul",
    "Conversation",
    "ChatMessage",
    "PendingConfirmation",
]
