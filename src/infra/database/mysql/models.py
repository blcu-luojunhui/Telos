"""
ORM models (mappers) for better_me MySQL data layer.
Tables: workouts, body_metrics, meals, user_profile, goals, conversations, chat_messages, pending_confirmations.

使用方式：先 async_mysql_pool.init(app) 或 init(dsn=...)，再通过 async_mysql_pool.session() 取 Session，例如：
    from src.infra.database.mysql import async_mysql_pool, Workout
    from sqlalchemy import select
    async with async_mysql_pool.session() as session:
        result = await session.execute(select(Workout).where(Workout.date >= ...))
"""

from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, JSON, Time, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base


# ---------------------------------------------------------------------------
# 训练记录 workouts
# ---------------------------------------------------------------------------


class Workout(Base):
    """训练记录：跑步、篮球、力量等。主观体验为一等公民。"""

    __tablename__ = "workouts"

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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    conversation_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    parsed_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    duplicate_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
