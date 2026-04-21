from datetime import date, datetime

from pydantic import BaseModel


class ShoppingItemResponse(BaseModel):
    id: int
    name: str
    quantity: str
    unit: str | None
    category: str | None
    priority: int
    at_home: bool
    checked: bool

    model_config = {"from_attributes": True}


class ShoppingItemCheck(BaseModel):
    checked: bool


class ShoppingListResponse(BaseModel):
    id: int
    user_id: int
    week_start: date | None
    items: list[ShoppingItemResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}
