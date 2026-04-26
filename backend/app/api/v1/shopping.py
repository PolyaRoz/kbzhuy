from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.core.security import get_current_user_id
from app.models.shopping import ShoppingList, ShoppingItem
from app.models.plan import MealPlan


class ItemUpdate(BaseModel):
    checked: bool | None = None
    at_home: bool | None = None

router = APIRouter()


@router.get("")
async def get_shopping_list(
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
    await session.commit()
    return {"status": "updated", "item_id": item_id}
