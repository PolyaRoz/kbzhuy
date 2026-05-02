from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.core.security import get_current_user_id
from app.models.shopping import ShoppingList, ShoppingItem
from app.models.plan import MealPlan
from app.services.meal_planner_service import MealPlannerService
from app.services.inventory_service import InventoryService


class ItemUpdate(BaseModel):
    checked: bool | None = None
    at_home: bool | None = None
    location_type: str | None = None


class BulkUpdate(BaseModel):
    checked: bool = True
    location_type: str | None = None


class ConfirmItems(BaseModel):
    item_ids: list[int]
    location_type: str | None = None

router = APIRouter()


@router.get("")
async def get_shopping_list(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    plan_result = await session.execute(
        select(MealPlan)
        .where(MealPlan.user_id == user_id)
        .where(MealPlan.status == "active")
        .order_by(MealPlan.created_at.desc())
    )
    plan = plan_result.scalars().first()
    if not plan:
        raise HTTPException(status_code=404, detail="No shopping list")

    planner = MealPlannerService(session)
    await planner._sync_shopping_list(plan.id, user_id, plan.period_start)
    await session.commit()

    result = await session.execute(
        select(ShoppingList)
        .where(ShoppingList.user_id == user_id)
        .where(ShoppingList.plan_id == plan.id)
        .options(selectinload(ShoppingList.items))
    )
    sl = result.scalar_one_or_none()
    if not sl:
        raise HTTPException(status_code=404, detail="No shopping list")
    return {
        "id": sl.id,
        "plan_id": sl.plan_id,
        "week_start": sl.week_start.isoformat() if sl.week_start else None,
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "category": item.category,
                "quantity": item.quantity,
                "unit": item.unit,
                "checked": item.checked,
                "at_home": item.at_home,
                "priority": item.priority,
            }
            for item in sl.items
        ],
    }


@router.patch("/items/{item_id}")
async def check_item(
    item_id: int,
    body: ItemUpdate,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ShoppingItem)
        .join(ShoppingList)
        .where(ShoppingItem.id == item_id)
        .where(ShoppingList.user_id == user_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if body.checked is not None:
        item.checked = body.checked
    if body.at_home is not None:
        item.at_home = body.at_home
    if body.checked:
        inventory = InventoryService(session)
        await inventory.add_from_shopping_item(user_id, item, body.location_type)
        item.at_home = True
    await session.commit()
    return {"status": "updated", "item_id": item_id}


@router.post("/mark-all")
async def mark_all_items(
    body: BulkUpdate,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ShoppingList)
        .join(MealPlan, ShoppingList.plan_id == MealPlan.id)
        .where(ShoppingList.user_id == user_id)
        .where(MealPlan.status == "active")
        .order_by(ShoppingList.created_at.desc())
        .options(selectinload(ShoppingList.items))
    )
    sl = result.scalars().first()
    if not sl:
        raise HTTPException(status_code=404, detail="No shopping list")
    inventory = InventoryService(session)
    updated = 0
    for item in sl.items:
        item.checked = body.checked
        if body.checked:
            await inventory.add_from_shopping_item(user_id, item, body.location_type)
            item.at_home = True
        updated += 1
    await session.commit()
    return {"status": "updated", "count": updated}


@router.post("/confirm")
async def confirm_items(
    body: ConfirmItems,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    item_ids = sorted({item_id for item_id in body.item_ids if item_id > 0})
    if not item_ids:
        return {"status": "updated", "count": 0}

    result = await session.execute(
        select(ShoppingItem)
        .join(ShoppingList)
        .where(ShoppingItem.id.in_(item_ids))
        .where(ShoppingList.user_id == user_id)
    )
    items = result.scalars().all()
    if not items:
        raise HTTPException(status_code=404, detail="Items not found")

    inventory = InventoryService(session)
    updated = 0
    for item in items:
        item.checked = True
        await inventory.add_from_shopping_item(user_id, item, body.location_type)
        item.at_home = True
        updated += 1

    await session.commit()
    return {"status": "updated", "count": updated}
