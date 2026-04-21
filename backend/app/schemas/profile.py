from pydantic import BaseModel


class EatingSchedule(BaseModel):
    breakfast: str = "08:00"
    lunch: str = "13:00"
    snack: str | None = "16:00"
    dinner: str = "19:00"


class PlannedDeviation(BaseModel):
    type: str          # "beer", "restaurant", "dessert"
    description: str
    day_of_week: int | None = None  # 0=Mon, 6=Sun
    recurrence: str | None = None   # "weekly", "biweekly"
    kcal_extra: int = 0


class ProfileCreate(BaseModel):
    name: str | None = None
    sex: str = "male"
    age: int = 30
    height_cm: float = 175.0
    weight_kg: float = 80.0
    activity_level: str = "moderate"
    measurements: dict | None = None
    training_days: list[str] = []
    sport_types: list[str] = []
    goal: str = "maintain"
    allergies: list[str] = []
    disliked_foods: list[str] = []
    diet_type: str | None = None
    budget_rub_week: int | None = None
    cooking_frequency: str = "twice_a_week"
    cooking_time_budget: dict | None = None
    family_size: int = 1
    kitchen_equipment: list[str] = []
    eating_schedule: dict | None = None
    planned_deviations: list[dict] = []
    flexibility_pct: int = 10


class ProfileUpdate(BaseModel):
    name: str | None = None
    sex: str | None = None
    age: int | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    activity_level: str | None = None
    measurements: dict | None = None
    training_days: list[str] | None = None
    sport_types: list[str] | None = None
    goal: str | None = None
    allergies: list[str] | None = None
    disliked_foods: list[str] | None = None
    diet_type: str | None = None
    budget_rub_week: int | None = None
    cooking_frequency: str | None = None
    cooking_time_budget: dict | None = None
    family_size: int | None = None
    kitchen_equipment: list[str] | None = None
    eating_schedule: dict | None = None
    planned_deviations: list[dict] | None = None
    flexibility_pct: int | None = None


class ProfileResponse(BaseModel):
    id: int
    user_id: int
    name: str | None = None
    sex: str | None
    goal: str | None
    weight_kg: float | None
    height_cm: float | None
    age: int | None
    activity_level: str | None
    measurements: dict | None = None
    training_days: list | None = None
    sport_types: list | None = None
    target_kcal: int | None
    target_protein_g: int | None
    target_fat_g: int | None
    target_carbs_g: int | None
    allergies: list | None
    disliked_foods: list | None
    budget_rub_week: int | None
    eating_schedule: dict | None
    planned_deviations: list | None
    flexibility_pct: int | None
    diet_type: str | None = None
    cooking_frequency: str | None = None
    cooking_time_budget: dict | None = None
    family_size: int | None = None
    kitchen_equipment: list | None = None

    model_config = {"from_attributes": True}
