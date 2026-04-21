from datetime import date, datetime

from sqlalchemy import ForeignKey, String, Integer, Date, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Container(Base):
    __tablename__ = "containers"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    label: Mapped[str] = mapped_column(String(10))  # e.g. "1А", "2Г", "3Б"
    plan_id: Mapped[int] = mapped_column(ForeignKey("meal_plans.id"), index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("storage_locations.id"))
    status: Mapped[str] = mapped_column(String(20), default="empty")
    # empty / filled / eaten / expired
    contents_description: Mapped[str | None] = mapped_column(String(300))
    heating_instructions: Mapped[str | None] = mapped_column(String(500))
    expiry_date: Mapped[date | None] = mapped_column(Date)
    kbzhu: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    location: Mapped["StorageLocation"] = relationship(back_populates="containers")
    meal: Mapped["Meal"] = relationship(back_populates="container", uselist=False)
