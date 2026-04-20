"""
V2 schema models for BetterMe / AutoAgent.

设计目标：
1. 与当前 V1 表并行存在，不直接破坏现有功能。
2. 用更清晰的领域边界重构数据层：用户、事实记录、目标、计划。
3. 为后续双写 / 平滑迁移提供稳定的 ORM 基础。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base


class User(Base):
    """统一用户主表：认证、业务、Agent 学习都依附于此。"""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("user_code", name="uq_users_user_code"),
        CheckConstraint("status in ('active','inactive')", name="ck_users_status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",
        server_default="active",
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )


class UserProfileV2(Base):
    """低频稳定的基础画像。"""

    __tablename__ = "user_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_profiles_user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nickname: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    birth_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height_cm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    baseline_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    activity_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="Asia/Shanghai",
        server_default="Asia/Shanghai",
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )


class UserPreference(Base):
    """长期偏好、限制和沟通风格。"""

    __tablename__ = "user_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_preferences_user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dietary_preferences_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    training_preferences_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    communication_preferences_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    constraints_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    reminder_preferences_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Record(Base):
    """所有事实记录的统一主表。"""

    __tablename__ = "records"
    __table_args__ = (
        Index("ix_records_user_type_date_status", "user_id", "record_type", "local_date", "status"),
        Index("ix_records_user_occurred_at", "user_id", "occurred_at"),
        Index("ix_records_conversation", "conversation_id"),
        Index("ix_records_supersedes", "supersedes_record_id"),
        CheckConstraint(
            "record_type in ('activity','nutrition','measurement','status')",
            name="ck_records_record_type",
        ),
        CheckConstraint(
            "source_type in ('chat','manual','imported','plan_generated')",
            name="ck_records_source_type",
        ),
        CheckConstraint(
            "status in ('active','superseded','deleted')",
            name="ck_records_status",
        ),
        CheckConstraint(
            "created_by in ('user','agent','system')",
            name="ck_records_created_by",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    record_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="chat",
        server_default="chat",
    )
    source_ref_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    conversation_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    raw_message_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="Asia/Shanghai",
        server_default="Asia/Shanghai",
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",
        server_default="active",
        index=True,
    )
    supersedes_record_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("records.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="user",
        server_default="user",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class ActivityRecordV2(Base):
    """运动/训练类记录明细。"""

    __tablename__ = "activity_records"
    __table_args__ = (
        Index("ix_activity_records_type", "activity_type"),
        Index("ix_activity_records_intensity", "intensity"),
    )

    record_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("records.id", ondelete="CASCADE"),
        primary_key=True,
    )
    activity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subtype: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    duration_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    distance_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_pace_sec_per_km: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    avg_hr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    calories: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    intensity: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    subjective_fatigue: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mood: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    motivation: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stress_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sleep_quality: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class NutritionRecordV2(Base):
    """一次饮食事件的头记录。"""

    __tablename__ = "nutrition_records"
    __table_args__ = (
        Index("ix_nutrition_records_meal_type", "meal_type"),
    )

    record_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("records.id", ondelete="CASCADE"),
        primary_key=True,
    )
    meal_type: Mapped[str] = mapped_column(String(32), nullable=False)
    estimated_calories: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    protein_g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    carb_g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fat_g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    satiety: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mood: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stress_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class NutritionItemV2(Base):
    """一顿饭中的单个食物项。"""

    __tablename__ = "nutrition_items"
    __table_args__ = (
        Index("ix_nutrition_items_record", "record_id"),
        Index("ix_nutrition_items_food_name", "food_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    record_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("nutrition_records.record_id", ondelete="CASCADE"),
        nullable=False,
    )
    food_name: Mapped[str] = mapped_column(String(128), nullable=False)
    quantity_text: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    estimated_calories: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    protein_g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    carb_g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fat_g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tags_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class MeasurementRecordV2(Base):
    """一次测量行为的头记录。"""

    __tablename__ = "measurement_records"
    __table_args__ = (
        CheckConstraint(
            "measurement_context in ('morning_fast','post_workout','before_sleep','manual')",
            name="ck_measurement_records_context",
        ),
    )

    record_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("records.id", ondelete="CASCADE"),
        primary_key=True,
    )
    measurement_context: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="manual",
        server_default="manual",
        index=True,
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class MeasurementItemV2(Base):
    """测量项：用 item 模型代替当前 body_metrics 宽表。"""

    __tablename__ = "measurement_items"
    __table_args__ = (
        Index("ix_measurement_items_record_metric", "record_id", "metric_code"),
        Index("ix_measurement_items_user_metric_date", "user_id", "metric_code", "local_date"),
        CheckConstraint(
            "metric_code in ('weight','body_fat','muscle_mass','resting_hr','sleep_hours','bp_systolic','bp_diastolic')",
            name="ck_measurement_items_metric_code",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    record_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("measurement_records.record_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    local_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    metric_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    numeric_value: Mapped[Optional[float]] = mapped_column(Numeric(10, 3), nullable=True)
    text_value: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)


class StatusRecordV2(Base):
    """整体状态、主观感受类记录。"""

    __tablename__ = "status_records"

    record_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("records.id", ondelete="CASCADE"),
        primary_key=True,
    )
    mood: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    motivation: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stress_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    energy_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recovery_state: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class UserGoal(Base):
    """用户目标实体：支持多目标并行。"""

    __tablename__ = "user_goals"
    __table_args__ = (
        Index("ix_user_goals_user_status_priority", "user_id", "status", "priority"),
        CheckConstraint(
            "goal_type in ('weight_loss','race','maintenance','muscle_gain')",
            name="ck_user_goals_goal_type",
        ),
        CheckConstraint(
            "status in ('draft','active','paused','completed','abandoned')",
            name="ck_user_goals_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    goal_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100")
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",
        server_default="active",
        index=True,
    )
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    target_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    success_definition_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    constraints_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )


class GoalCheckpoint(Base):
    """目标轨迹中的阶段节点。"""

    __tablename__ = "goal_checkpoints"
    __table_args__ = (
        Index("ix_goal_checkpoints_goal_date", "goal_id", "checkpoint_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_goals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    checkpoint_date: Mapped[date] = mapped_column(Date, nullable=False)
    target_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    actual_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Plan(Base):
    """计划实体：一个长期安排的容器。"""

    __tablename__ = "plans"
    __table_args__ = (
        Index("ix_plans_user_status_type", "user_id", "status", "plan_type"),
        CheckConstraint(
            "plan_type in ('training','nutrition','weekly_life')",
            name="ck_plans_plan_type",
        ),
        CheckConstraint(
            "status in ('draft','active','archived','completed')",
            name="ck_plans_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="draft",
        server_default="draft",
        index=True,
    )
    current_version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )


class PlanVersion(Base):
    """计划的具体版本。"""

    __tablename__ = "plan_versions"
    __table_args__ = (
        UniqueConstraint("plan_id", "version_no", name="uq_plan_versions_plan_version"),
        Index("ix_plan_versions_plan_created", "plan_id", "created_at"),
        CheckConstraint(
            "generated_by in ('agent','user','system')",
            name="ck_plan_versions_generated_by",
        ),
        CheckConstraint(
            "trigger_type in ('goal_created','weekly_review','fatigue_adjustment','manual_edit')",
            name="ck_plan_versions_trigger_type",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_by: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="agent",
        server_default="agent",
    )
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PlanGoalLink(Base):
    """计划与目标的多对多绑定。"""

    __tablename__ = "plan_goal_links"
    __table_args__ = (
        UniqueConstraint("plan_id", "goal_id", name="uq_plan_goal_links_plan_goal"),
        Index("ix_plan_goal_links_goal", "goal_id"),
        CheckConstraint(
            "role in ('primary','secondary','constraint')",
            name="ck_plan_goal_links_role",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    goal_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_goals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, server_default="1")
    role: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="primary",
        server_default="primary",
    )


class PlanItem(Base):
    """计划中的最小可执行单元。"""

    __tablename__ = "plan_items"
    __table_args__ = (
        Index("ix_plan_items_version_date_status", "plan_version_id", "item_date", "status"),
        Index("ix_plan_items_user_date", "user_id", "item_date"),
        CheckConstraint(
            "item_type in ('workout','nutrition_target','recovery','rest')",
            name="ck_plan_items_item_type",
        ),
        CheckConstraint(
            "day_type in ('rest_day','easy_day','key_workout_day')",
            name="ck_plan_items_day_type",
        ),
        CheckConstraint(
            "status in ('pending','done','skipped','rescheduled')",
            name="ck_plan_items_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    plan_version_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("plan_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    item_type: Mapped[str] = mapped_column(String(32), nullable=False)
    day_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    instruction_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    target_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
    order_in_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )


class PlanExecution(Base):
    """计划项与实际执行事实之间的桥接。"""

    __tablename__ = "plan_executions"
    __table_args__ = (
        UniqueConstraint("plan_item_id", "linked_record_id", name="uq_plan_executions_item_record"),
        Index("ix_plan_executions_plan_item", "plan_item_id"),
        CheckConstraint(
            "execution_status in ('matched','partial','missed','extra')",
            name="ck_plan_executions_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    plan_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("plan_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    linked_record_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    execution_status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    deviation_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    feedback_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PendingAction(Base):
    """统一的中间态表：确认保存、确认删除、补槽、确认计划等。"""

    __tablename__ = "pending_actions"
    __table_args__ = (
        Index("ix_pending_actions_user_conv", "user_id", "conversation_id"),
        CheckConstraint(
            "pending_type in ('confirm_save','confirm_delete','slot_fill','confirm_plan')",
            name="ck_pending_actions_type",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    pending_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    target_record_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("records.id", ondelete="SET NULL"),
        nullable=True,
    )
    snapshot_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
