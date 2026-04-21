from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class ContainerBase(BaseModel):
    label: str
    location_id: int | None = None
    status: str = "empty"  # empty | filled | eaten | expired
    heating_instructions: str | None = None
    expiry_date: date | None = None
    kbzhu: dict[str, Any] | None = None


class ContainerCreate(ContainerBase):
    pass


class ContainerUpdate(BaseModel):
    status: str | None = None
    location_id: int | None = None
    expiry_date: date | None = None
    kbzhu: dict[str, Any] | None = None


class ContainerResponse(ContainerBase):
    id: int
    user_id: int
    plan_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
