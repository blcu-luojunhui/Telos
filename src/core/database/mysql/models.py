"""
ORM models (mappers) for better_me MySQL data layer.
Tables: workouts, body_metrics, meals, user_profile, goals.

使用方式：先 db.init(app) 或 db.init(dsn=...)，再通过 db.session() 取 Session，例如：
    from src.core.database.mysql import db, Workout
    from sqlalchemy import select
    async with db.session() as session:
        result = await session.execute(select(Workout).where(Workout.date >= ...))
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, Integer, String, Text, JSON
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
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )  # run / basketball / strength / other
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
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
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
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
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
    height: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # cm
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
