from datetime import date, datetime

from sqlalchemy import ForeignKey, String, Integer, Boolean, Date, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CookingPlan(Base):
    __tablename__ = "cooking_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("meal_plans.id"), unique=True)
    scheduled_date: Mapped[date | None] = mapped_column(Date)
    estimated_time_min: Mapped[int] = mapped_column(Integer, default=0)
    active_time_min: Mapped[int] = mapped_column(Integer, default=0)
    parallel_groups: Mapped[list] = mapped_column(JSON, default=list)
    container_distribution: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    steps: Mapped[list["CookingStep"]] = relationship(back_populates="cooking_plan", cascade="all, delete-orphan")


class CookingStep(Base):
    __tablename__ = "cooking_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    cooking_plan_id: Mapped[int] = mapped_column(ForeignKey("cooking_plans.id"), index=True)
    step_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(1000))
    duration_minutes: Mapped[int] = mapped_column(Integer)
    is_parallel: Mapped[bool] = mapped_column(Boolean, default=False)
    parallel_group: Mapped[int | None] = mapped_column(Integer)
    done: Mapped[bool] = mapped_column(Boolean, default=False)

    cooking_plan: Mapped["CookingPlan"] = relationship(back_populates="steps")
