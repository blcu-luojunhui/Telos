"""
LEGACY MODELS (V1) - Do not use for new development.

该文件仅用于历史迁移与数据回溯参考。
运行期默认模型入口已切换到：
- models_runtime.py （认证/会话/消息）
- models_v2.py      （用户/事实记录/目标/计划/pending_actions）

注意：
1) 新代码不要从本文件导入业务模型。
2) create_all 运行链路不应再依赖本文件，以避免 V1 旧表被重新建回。
3) 在完成 V2 全量切换与数据校验后，可配合 SQL 脚本删除 V1 表。
"""

from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base


class AuthUser(Base):
    """认证用户账号表：保存 user_id 与密码哈希。"""

    __tablename__ = "auth_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# 训练记录 workouts
# ---------------------------------------------------------------------------


class Workout(Base):
    """训练记录：跑步、篮球、力量等。主观体验为一等公民。"""

    __tablename__ = "workouts"
    __table_args__ = (
        Index("ix_workouts_user_date_type_status", "user_id", "date", "type", "status"),
        CheckConstraint(
            "status in ('active','replaced','deleted')",
            name="ck_workouts_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )  # run / basketball / strength / other
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",
        server_default="active",
        index=True,
    )  # active / replaced / deleted
    duration_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    distance_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_pace: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # min/km
    avg_hr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    calories: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 主观体验（1-10 或类似）
    subjective_fatigue: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sleep_quality: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mood: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    motivation: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stress_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# 身体指标 body_metrics
# ---------------------------------------------------------------------------


class BodyMetric(Base):
    """身体指标：体重、体脂、睡眠等。"""

    __tablename__ = "body_metrics"
    __table_args__ = (
        Index("ix_body_metrics_user_date_status", "user_id", "date", "status"),
        CheckConstraint(
            "status in ('active','replaced','deleted')",
            name="ck_body_metrics_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",
        server_default="active",
        index=True,
    )  # active / replaced / deleted
    weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # kg
    body_fat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # %
    muscle_mass: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # kg
    resting_hr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bp_systolic: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bp_diastolic: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sleep_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# 饮食记录 meals
# ---------------------------------------------------------------------------


class Meal(Base):
    """饮食记录。起步阶段可简化，主观体验（饱腹感、心情）一并记录。"""

    __tablename__ = "meals"
    __table_args__ = (
        Index("ix_meals_user_date_type_status", "user_id", "date", "meal_type", "status"),
        CheckConstraint(
            "status in ('active','replaced','deleted')",
            name="ck_meals_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",
        server_default="active",
        index=True,
    )  # active / replaced / deleted
    meal_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )  # breakfast / lunch / dinner / snack
    food_items: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_calories: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    protein_g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    carb_g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fat_g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    satiety: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-10
    mood: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-10
    stress_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# 个人配置与偏好 user_profile（单用户，通常一行）
# ---------------------------------------------------------------------------


class UserProfile(Base):
    """个人配置与偏好：身高、性别、活动水平、饮食偏好与忌口等。"""

    __tablename__ = "user_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    height: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="身高（cm）"
    )
    weight: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="体重（kg）"
    )
    gender: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    birth_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    activity_level: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True
    )  # sedentary / moderate / high
    # 饮食偏好与忌口：JSON，如 {"spicy": true, "dairy": false, "beef": true, "pork": false}
    dietary_preferences: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# 目标系统 goals（统一模型，type + target JSON 区分）
# ---------------------------------------------------------------------------


class Goal(Base):
    """目标：减脂、增肌、维持、比赛等。type 区分类型，target 存结构化内容（JSON）。"""

    __tablename__ = "goals"
    __table_args__ = (
        Index("ix_goals_user_status_type", "user_id", "status", "type"),
        CheckConstraint(
            "status in ('planning','ongoing','completed','abandoned')",
            name="ck_goals_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # weight_loss / muscle_gain / maintenance / race / ...
    target: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # 按 type 不同：e.g. { start_weight, target_weight } or { race_type, race_date, target_time, ... }
    deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="planning", index=True
    )  # planning / ongoing / completed / abandoned
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# 训练计划 training_plans（按用户+目标长期存储计划结构）
# ---------------------------------------------------------------------------


class TrainingPlan(Base):
    """训练计划：按天/阶段安排训练内容，关联目标；计划内单次训练见 TrainingPlanSession。"""

    __tablename__ = "training_plans"
    __table_args__ = (
        Index("ix_training_plans_user_goal_status", "user_id", "goal_id", "status"),
        CheckConstraint(
            "status in ('active','archived','completed')",
            name="ck_training_plans_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    goal_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("goals.id", ondelete="CASCADE"), nullable=True, index=True
    )  # 关联目标，新计划必填
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    goal_type: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )  # 如 half_marathon / 10k / weight_loss
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    plan: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # 可选摘要/快照；按次计划以 training_plan_sessions 为准
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", index=True
    )  # active / archived / completed
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# 计划内单次训练 training_plan_sessions（每次训练一条记录）
# ---------------------------------------------------------------------------


class TrainingPlanSession(Base):
    """计划内单次训练：每一条对应某天的一场训练，可关联实际执行 workout。"""

    __tablename__ = "training_plan_sessions"
    __table_args__ = (
        UniqueConstraint(
            "training_plan_id",
            "scheduled_date",
            "order_in_day",
            name="uq_tps_plan_date_order",
        ),
        Index(
            "ix_tps_user_plan_date_status",
            "user_id",
            "training_plan_id",
            "scheduled_date",
            "status",
        ),
        CheckConstraint(
            "status in ('pending','completed','skipped','rescheduled')",
            name="ck_tps_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    training_plan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("training_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    goal_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("goals.id", ondelete="CASCADE"), nullable=True, index=True
    )
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    scheduled_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    slot_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    remind_day_before: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )  # pending / completed / skipped / rescheduled
    workout_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("workouts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    order_in_day: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# Agent 人格 souls（每种人格一条，供小聊天注入；chat_messages 记录回复来自哪个人格）
# ---------------------------------------------------------------------------


class Soul(Base):
    """Agent 人格：名称、描述、人格文档内容（Markdown），供小聊天 system prompt 注入。"""

    __tablename__ = "souls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True
    )  # rude / gentle / professional / funny
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 人格文档正文（Markdown）
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default="active", index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# 会话 conversations（按会话维度隔离上下文）
# ---------------------------------------------------------------------------


class Conversation(Base):
    """会话：一个用户可有多个会话，每个会话有独立消息列表。"""

    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_user_status_updated", "user_id", "status", "updated_at"),
        CheckConstraint(
            "status in ('active','archived','pinned')",
            name="ck_conversations_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", server_default="active", index=True
    )  # active / archived
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# 对话消息 chat_messages（按 conversation_id 归属会话）
# ---------------------------------------------------------------------------


class ChatMessage(Base):
    """对话消息记录：归属某会话，用于上下文感知；assistant 消息可记录来自哪个人格。"""

    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_conv_created", "conversation_id", "created_at"),
        Index("ix_chat_messages_user_created", "user_id", "created_at"),
        CheckConstraint(
            "role in ('user','assistant','system')",
            name="ck_chat_messages_role",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )  # 为空表示迁移前旧数据，新数据必填
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    role: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # user / assistant / system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    msg_type: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True
    )  # normal / saved / needs_confirm / confirmed / cancelled / error / unknown
    extra: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # 扩展：saved 结果等；pending 已迁至 pending_confirmations
    soul_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("souls.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )  # 仅 assistant 消息：回复来自哪个人格
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ---------------------------------------------------------------------------
# 待确认状态 pending_confirmations（与消息表解耦）
# ---------------------------------------------------------------------------


class PendingConfirmation(Base):
    """待用户确认的覆盖操作：进入需要确认时插入，确认/取消后删除。"""

    __tablename__ = "pending_confirmations"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "conversation_id",
            name="uq_pending_confirm_user_conversation",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    conversation_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    parsed_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    duplicate_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ---------------------------------------------------------------------------
# AutoAgent: 原子动作事件 agent_action_events
# ---------------------------------------------------------------------------


class AgentActionEvent(Base):
    """AutoAgent 每一步动作事件日志：用于可观测、回放、进化学习。"""

    __tablename__ = "agent_action_events"
    __table_args__ = (
        Index("ix_agent_action_events_trace", "trace_id"),
        Index("ix_agent_action_events_conv_step", "conversation_id", "step_index"),
        Index("ix_agent_action_events_action_created", "action_name", "created_at"),
        CheckConstraint(
            "action_type in ('emic','etic')",
            name="ck_agent_action_events_action_type",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    conversation_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    intent: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    action_type: Mapped[str] = mapped_column(String(16), nullable=False)  # emic / etic
    action_name: Mapped[str] = mapped_column(String(128), nullable=False)
    intent_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    params_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    outcome_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    error_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    token_in: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    token_out: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


# ---------------------------------------------------------------------------
# AutoAgent: step 级记忆 agent_step_memories
# ---------------------------------------------------------------------------


class AgentStepMemory(Base):
    """每一步的双轨记忆：raw_record + compressed_summary。"""

    __tablename__ = "agent_step_memories"
    __table_args__ = (
        Index("ix_agent_step_memories_event", "event_id"),
        Index("ix_agent_step_memories_importance", "importance_score"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("agent_action_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    conversation_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    raw_record: Mapped[str] = mapped_column(Text, nullable=False)
    compressed_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    importance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


# ---------------------------------------------------------------------------
# AutoAgent: episode 级记忆 agent_episodes
# ---------------------------------------------------------------------------


class AgentEpisode(Base):
    """多步骤事件压缩后的 episodic memory。"""

    __tablename__ = "agent_episodes"
    __table_args__ = (
        Index("ix_agent_episodes_user_conv", "user_id", "conversation_id"),
        Index("ix_agent_episodes_step_range", "conversation_id", "start_step", "end_step"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    conversation_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    start_step: Mapped[int] = mapped_column(Integer, nullable=False)
    end_step: Mapped[int] = mapped_column(Integer, nullable=False)
    goal_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    episode_summary: Mapped[str] = mapped_column(Text, nullable=False)
    resolution_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    success_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


# ---------------------------------------------------------------------------
# AutoAgent: 认知库（工具 / 技能 / 协作对象）
# ---------------------------------------------------------------------------


class AgentCognitionTool(Base):
    """工具认知画像：可持续更新的前置条件、失败模式、成功样例。"""

    __tablename__ = "agent_cognition_tools"
    __table_args__ = (
        UniqueConstraint("tool_name", name="uq_agent_cognition_tools_tool_name"),
        Index("ix_agent_cognition_tools_reliability", "reliability_score"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    preconditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    failure_patterns: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    success_examples: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    reliability_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5, server_default="0.5")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )


class AgentSkill(Base):
    """技能卡片：从高频成功轨迹抽象出的复合动作。"""

    __tablename__ = "agent_skills"
    __table_args__ = (
        UniqueConstraint("skill_name", name="uq_agent_skills_skill_name"),
        CheckConstraint(
            "status in ('draft','active','deprecated')",
            name="ck_agent_skills_status",
        ),
        Index("ix_agent_skills_status_success", "status", "success_rate"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    skill_name: Mapped[str] = mapped_column(String(128), nullable=False)
    trigger_conditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    procedure: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    io_contract: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )


class AgentCognitionPeer(Base):
    """外部协作认知：对外部代理/服务的能力与可靠性估计。"""

    __tablename__ = "agent_cognition_peers"
    __table_args__ = (
        UniqueConstraint("peer_name", name="uq_agent_cognition_peers_peer_name"),
        Index("ix_agent_cognition_peers_domain_reliability", "domain", "reliability_score"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    peer_name: Mapped[str] = mapped_column(String(128), nullable=False)
    domain: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    reliability_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5, server_default="0.5")
    response_style: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )


# ---------------------------------------------------------------------------
# AutoAgent: 认知补丁生命周期
# ---------------------------------------------------------------------------


class AgentCognitionPatch(Base):
    """认知补丁：支持 shadow/applied/rejected/rolled_back 生命周期。"""

    __tablename__ = "agent_cognition_patches"
    __table_args__ = (
        Index("ix_agent_cognition_patches_target", "target_type", "target_name"),
        Index("ix_agent_cognition_patches_status_created", "status", "created_at"),
        CheckConstraint(
            "status in ('shadow','applied','rejected','rolled_back')",
            name="ck_agent_cognition_patches_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)  # tool / skill / peer
    target_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    target_name: Mapped[str] = mapped_column(String(128), nullable=False)
    before_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    patch_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    evidence_event_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="shadow", server_default="shadow")
    validator_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
