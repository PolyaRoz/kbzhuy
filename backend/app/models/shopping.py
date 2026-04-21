from datetime import date, datetime

from sqlalchemy import ForeignKey, String, Float, Boolean, Integer, Date, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ShoppingList(Base):
    __tablename__ = "shopping_lists"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("meal_plans.id"), unique=True)
    week_start: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["ShoppingItem"]] = relationship(back_populates="shopping_list", cascade="all, delete-orphan")


class ShoppingItem(Base):
    __tablename__ = "shopping_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    shopping_list_id: Mapped[int] = mapped_column(ForeignKey("shopping_lists.id"), index=True)
    ingredient_id: Mapped[int | None] = mapped_column(ForeignKey("ingredients.id"))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(50))
    quantity: Mapped[str] = mapped_column(String(50))  # e.g. "300 г"
    unit: Mapped[str] = mapped_column(String(20))
    checked: Mapped[bool] = mapped_column(Boolean, default=False)
    at_home: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[int] = mapped_column(Integer, default=1)

    shopping_list: Mapped["ShoppingList"] = relationship(back_populates="items")
