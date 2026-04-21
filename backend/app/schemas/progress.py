from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class ProgressLogCreate(BaseModel):
    log_date: date
    actual_kbzhu: dict[str, Any]
    weight_kg: float | None = None
    notes: str | None = None


class ProgressLogResponse(BaseModel):
    id: int
    user_id: int
    log_date: date
    actual_kbzhu: dict[str, Any]
    weight_kg: float | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DashboardResponse(BaseModel):
    period_days: int
    avg_kcal: float
    avg_protein: float
    avg_fat: float
    avg_carbs: float
    weight_start: float | None
    weight_current: float | None
    logs: list[ProgressLogResponse]
