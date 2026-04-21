from datetime import date, datetime

from sqlalchemy import ForeignKey, String, Integer, Float, Date, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MealPlan(Base):
    __tablename__ = "meal_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active / completed / cancelled
    daily_targets: Mapped[dict] = mapped_column(JSON)
    # {"kcal": 2200, "protein": 150, "fat": 70, "carbs": 250}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="plans")
    days: Mapped[list["DayPlan"]] = relationship(back_populates="plan", cascade="all, delete-orphan")
    deviations: Mapped[list["Deviation"]] = relationship(back_populates="plan")


class DayPlan(Base):
    __tablename__ = "day_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("meal_plans.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(String(500))

    plan: Mapped["MealPlan"] = relationship(back_populates="days")
    meals: Mapped[list["Meal"]] = relationship(back_populates="day", cascade="all, delete-orphan")


class Meal(Base):
    __tablename__ = "meals"

    id: Mapped[int] = mapped_column(primary_key=True)
    day_id: Mapped[int] = mapped_column(ForeignKey("day_plans.id"), index=True)
    recipe_id: Mapped[int | None] = mapped_column(ForeignKey("recipes.id"))
    container_id: Mapped[int | None] = mapped_column(ForeignKey("containers.id"))
    meal_type: Mapped[str] = mapped_column(String(20))  # breakfast / lunch / snack / dinner
    portions: Mapped[float] = mapped_column(Float, default=1.0)
    kbzhu_actual: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="planned")  # planned / eaten / skipped

    day: Mapped["DayPlan"] = relationship(back_populates="meals")
    recipe: Mapped["Recipe"] = relationship()
    container: Mapped["Container"] = relationship(back_populates="meal")
