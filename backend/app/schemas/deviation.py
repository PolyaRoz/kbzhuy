from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class DeviationRegister(BaseModel):
    deviation_type: str  # planned | spontaneous
    date: str | None = None   # ISO date; defaults to today if omitted
    description: str
    kbzhu_impact: dict[str, Any] | None = None
    recurrence: str | None = None  # e.g. "weekly:friday"


class DeviationResponse(BaseModel):
    id: int
    user_id: int
    deviation_type: str
    date: date | None
    description: str
    kbzhu_impact: dict[str, Any] | None
    recurrence: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RecalculateRequest(BaseModel):
    deviation_id: int
