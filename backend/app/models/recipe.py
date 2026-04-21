from sqlalchemy import String, Integer, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    ingredients: Mapped[list] = mapped_column(JSON)
    # [{"ingredient_id": 1, "name": "chicken breast", "grams": 500}, ...]
    steps: Mapped[list] = mapped_column(JSON)
    # [{"order": 1, "text": "Нарежьте куриную грудку", "time_min": 5}, ...]
    kbzhu_per_serving: Mapped[dict] = mapped_column(JSON)
    # {"kcal": 350, "protein": 40, "fat": 10, "carbs": 20}
    tags: Mapped[list] = mapped_column(JSON, default=list)
    # ["lunch", "high-protein", "batch-friendly", "russian"]
    time_min: Mapped[int] = mapped_column(Integer)
    servings: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[str | None] = mapped_column(String(300))
    storage_instructions: Mapped[str | None] = mapped_column(String(500))
    heating_instructions: Mapped[str | None] = mapped_column(String(500))


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    category: Mapped[str] = mapped_column(String(50))  # meat, dairy, vegetables, grains, etc.
    unit: Mapped[str] = mapped_column(String(20), default="g")
    kbzhu_per_100g: Mapped[dict] = mapped_column(JSON)
    avg_price_rub: Mapped[float | None] = mapped_column(Float)
