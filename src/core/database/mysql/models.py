from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer
from .base import Base


class UserMealPreference(Base):
    __tablename__ = "user_meal_preference"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    meal_name: Mapped[str] = mapped_column(String(128))
    score: Mapped[int] = mapped_column(Integer, default=0)
