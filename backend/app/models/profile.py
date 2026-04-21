from sqlalchemy import ForeignKey, String, Integer, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)

    name: Mapped[str | None] = mapped_column(String(100))

    # Physical params
    sex: Mapped[str] = mapped_column(String(10), default="male")  # male / female
    age: Mapped[int] = mapped_column(Integer, default=30)
    height_cm: Mapped[float] = mapped_column(Float, default=175.0)
    weight_kg: Mapped[float] = mapped_column(Float, default=80.0)
    activity_level: Mapped[str] = mapped_column(String(20), default="moderate")
    measurements: Mapped[dict] = mapped_column(JSON, default=dict)
    training_days: Mapped[list] = mapped_column(JSON, default=list)
    sport_types: Mapped[list] = mapped_column(JSON, default=list)

    # Goal
    goal: Mapped[str] = mapped_column(String(30), default="maintain")

    # Computed КБЖУ targets (recalculated on profile change)
    target_kcal: Mapped[int | None] = mapped_column(Integer)
    target_protein_g: Mapped[int | None] = mapped_column(Integer)
    target_fat_g: Mapped[int | None] = mapped_column(Integer)
    target_carbs_g: Mapped[int | None] = mapped_column(Integer)

    # Preferences (JSONB)
    allergies: Mapped[list] = mapped_column(JSON, default=list)
    disliked_foods: Mapped[list] = mapped_column(JSON, default=list)
    diet_type: Mapped[str | None] = mapped_column(String(30))

    # Lifestyle
    budget_rub_week: Mapped[int | None] = mapped_column(Integer)
    cooking_frequency: Mapped[str] = mapped_column(String(20), default="twice_a_week")
    cooking_time_budget: Mapped[dict] = mapped_column(JSON, default=dict)
    family_size: Mapped[int] = mapped_column(Integer, default=1)
    kitchen_equipment: Mapped[list] = mapped_column(JSON, default=list)

    # Eating schedule
    eating_schedule: Mapped[dict] = mapped_column(JSON, default=dict)

    # Flexibility & deviations
    flexibility_pct: Mapped[int] = mapped_column(Integer, default=10)
    planned_deviations: Mapped[list] = mapped_column(JSON, default=list)

    user: Mapped["User"] = relationship(back_populates="profile")
