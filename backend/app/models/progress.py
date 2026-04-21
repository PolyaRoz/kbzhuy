from datetime import date

from sqlalchemy import ForeignKey, Float, Integer, Date, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ProgressLog(Base):
    __tablename__ = "progress_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    meals_followed: Mapped[int | None] = mapped_column(Integer)
    meals_total: Mapped[int | None] = mapped_column(Integer)
    kbzhu_actual: Mapped[dict | None] = mapped_column(JSON)

    user: Mapped["User"] = relationship(back_populates="progress_logs")
