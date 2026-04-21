from datetime import datetime

from pydantic import BaseModel

from app.schemas.container import ContainerResponse


class StorageLocationBase(BaseModel):
    name: str
    location_type: str  # fridge | freezer | pantry
    description: str | None = None


class StorageLocationCreate(StorageLocationBase):
    pass


class StorageLocationUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class StorageLocationResponse(StorageLocationBase):
    id: int
    user_id: int
    created_at: datetime
    containers: list[ContainerResponse] = []

    model_config = {"from_attributes": True}
