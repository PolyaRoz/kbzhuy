from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.services.inventory_service import InventoryService

router = APIRouter()


class InventoryCreate(BaseModel):
    name: str
    quantity: float
    unit: str
    location_type: str
    category: str | None = None
    raw: bool = False  # skip ingredient normalization (for pre-cooked meals)


class InventoryUpdate(BaseModel):
    quantity: float | None = None
    unit: str | None = None
    location_type: str | None = None


class InventoryUse(BaseModel):
    quantity: float


class InventoryUseByName(BaseModel):
    name: str
    quantity: float
    unit: str


def serialize_location(location):
    return {
        "id": location.id,
        "type": location.type,
        "name": location.name,
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "category": item.category,
                "quantity": item.quantity,
                "unit": item.unit,
            }
            for item in sorted(location.inventory_items, key=lambda x: (x.category, x.name))
        ],
    }


@router.get("")
async def get_all_storage(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    inventory = InventoryService(db)
    locations = await inventory.get_inventory(user_id)
    return {
        "locations": [serialize_location(location) for location in locations],
    }


@router.post("/items")
async def add_inventory_item(
    body: InventoryCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    inventory = InventoryService(db)
    item = await inventory.upsert_item(
        user_id=user_id,
        name=body.name,
        quantity=body.quantity,
        unit=body.unit,
        location_type=body.location_type,
        category=body.category,
        raw=body.raw,
    )
    await db.commit()
    if item is None:
        raise HTTPException(status_code=400, detail="Invalid inventory item")
    return {"status": "created", "item_id": item.id}


@router.patch("/items/{item_id}")
async def update_inventory_item(
    item_id: int,
    body: InventoryUpdate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    inventory = InventoryService(db)
    item = await inventory.update_item(
        user_id,
        item_id,
        location_type=body.location_type,
        quantity=body.quantity,
        unit=body.unit,
    )
    await db.commit()
    if item is None and body.quantity is not None and body.quantity <= 0:
        return {"status": "deleted", "item_id": item_id}
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "updated", "item_id": item_id}


@router.post("/items/{item_id}/use")
async def use_inventory_item(
    item_id: int,
    body: InventoryUse,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    inventory = InventoryService(db)
    item = await inventory.use_item(user_id, item_id, body.quantity)
    await db.commit()
    return {"status": "used", "item_id": item_id, "remaining": item.quantity if item else 0}


@router.post("/use-by-name")
async def use_inventory_by_name(
    body: InventoryUseByName,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    inventory = InventoryService(db)
    used = await inventory.use_by_name(user_id, body.name, body.quantity, body.unit)
    await db.commit()
    return {"status": "used", "name": body.name, "used": used}


@router.delete("/items/{item_id}")
async def delete_inventory_item(
    item_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    inventory = InventoryService(db)
    deleted = await inventory.delete_item(user_id, item_id)
    await db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "deleted", "item_id": item_id}


@router.delete("/clear")
async def clear_storage(
    location_type: Optional[str] = Query(default=None, description="fridge | freezer | pantry; omit to clear all"),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete all inventory items, optionally filtered by location type."""
    if location_type and location_type not in ("fridge", "freezer", "pantry"):
        raise HTTPException(status_code=400, detail="Invalid location_type")
    inventory = InventoryService(db)
    count = await inventory.delete_by_location(user_id, location_type or None)
    await db.commit()
    return {"status": "cleared", "deleted": count, "location_type": location_type}
