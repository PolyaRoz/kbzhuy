from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class CookingStepResponse(BaseModel):
    id: int
    step_number: int
    title: str
    description: str
    duration_minutes: int
    is_parallel: bool
    parallel_group: int | None

    model_config = {"from_attributes": True}


class CookingPlanResponse(BaseModel):
    id: int
    user_id: int
    scheduled_date: date | None
    estimated_time_min: int
    active_time_min: int
    parallel_groups: list[Any]
    container_distribution: dict[str, Any]
    steps: list[CookingStepResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class MarkStepDone(BaseModel):
    step_id: int
