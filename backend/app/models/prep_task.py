from datetime import datetime

from sqlalchemy import ForeignKey, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PrepTask(Base):
    __tablename__ = "prep_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    container_id: Mapped[int | None] = mapped_column(ForeignKey("containers.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(30))  # defrost / move / ripen / check_expiry
    description: Mapped[str] = mapped_column(String(500))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending / done / skipped
