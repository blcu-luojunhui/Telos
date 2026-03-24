from .base import Base, AsyncMySQL
from .models_runtime import (
    AuthUser,
    Soul,
    Conversation,
    ChatMessage,
)
from .models_v2 import (
    User,
    UserProfileV2,
    UserPreference,
    Record,
    ActivityRecordV2,
    NutritionRecordV2,
    NutritionItemV2,
    MeasurementRecordV2,
    MeasurementItemV2,
    StatusRecordV2,
    UserGoal,
    GoalCheckpoint,
    Plan,
    PlanVersion,
    PlanGoalLink,
    PlanItem,
    PlanExecution,
    PendingAction,
)

# 异步 Mysql POOL
async_mysql_pool = AsyncMySQL()

__all__ = [
    "async_mysql_pool",
    "Base",
    "AsyncMySQL",
    "AuthUser",
    "Soul",
    "Conversation",
    "ChatMessage",
    "User",
    "UserProfileV2",
    "UserPreference",
    "Record",
    "ActivityRecordV2",
    "NutritionRecordV2",
    "NutritionItemV2",
    "MeasurementRecordV2",
    "MeasurementItemV2",
    "StatusRecordV2",
    "UserGoal",
    "GoalCheckpoint",
    "Plan",
    "PlanVersion",
    "PlanGoalLink",
    "PlanItem",
    "PlanExecution",
    "PendingAction",
]
