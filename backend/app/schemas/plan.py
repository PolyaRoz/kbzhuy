from datetime import date
from pydantic import BaseModel


class KbzhuTarget(BaseModel):
    kcal: int
    protein: int
    fat: int
    carbs: int


class PlanGenerate(BaseModel):
    period_start: date
    period_end: date
    override_targets: KbzhuTarget | None = None
    use_ai: bool = False
    notes: str | None = None


class MealResponse(BaseModel):
    id: int
    meal_type: str
    recipe_id: int | None
    container_id: int | None
    portions: float
    status: str
    kbzhu_actual: KbzhuTarget | None

    class Config:
        from_attributes = True


class DayPlanResponse(BaseModel):
    id: int
    date: date
    meals: list[MealResponse]

    class Config:
        from_attributes = True


class PlanResponse(BaseModel):
    id: int
    period_start: date
    period_end: date
    status: str
    daily_targets: KbzhuTarget
    days: list[DayPlanResponse]

    class Config:
        from_attributes = True


class DayPatchRequest(BaseModel):
    meal_type: str
    new_recipe_id: int
