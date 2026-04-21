from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class StorageLocation(Base):
    __tablename__ = "storage_locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(20))  # fridge / freezer / pantry
    name: Mapped[str] = mapped_column(String(100))  # user-friendly name

    user: Mapped["User"] = relationship(back_populates="storage_locations")
    containers: Mapped[list["Container"]] = relationship(back_populates="location")
