from datetime import date, datetime

from sqlalchemy import ForeignKey, String, Integer, Date, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Deviation(Base):
    __tablename__ = "deviations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("meal_plans.id"), index=True)
    deviation_type: Mapped[str] = mapped_column(String(20))  # planned / spontaneous
    date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(500))
    kbzhu_impact: Mapped[dict | None] = mapped_column(JSON)
    recurrence: Mapped[str | None] = mapped_column(String(50))  # "every_friday", "weekly", null for one-time
    day_of_week: Mapped[int | None] = mapped_column(Integer)  # 0=Mon, 6=Sun
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    plan: Mapped["MealPlan"] = relationship(back_populates="deviations")
