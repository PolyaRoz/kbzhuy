from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.core.security import get_current_user_id
from app.models.plan import MealPlan, DayPlan, Meal
from app.models.container import Container

router = APIRouter()

MEAL_ORDER = {"breakfast": 0, "lunch": 1, "snack": 2, "dinner": 3}


async def _get_today_meals_with_containers(user_id: int, session: AsyncSession):
    today = date.today()
    result = await session.execute(
        select(MealPlan)
        .where(MealPlan.user_id == user_id)
        .where(MealPlan.status == "active")
        .where(MealPlan.period_start <= today)
        .where(MealPlan.period_end >= today)
        .order_by(MealPlan.created_at.desc(), MealPlan.id.desc())
    )
    plan = result.scalars().first()
    if not plan:
        return []

    result = await session.execute(
        select(DayPlan)
        .where(DayPlan.plan_id == plan.id)
        .where(DayPlan.date == today)
        .options(
            selectinload(DayPlan.meals)
            .selectinload(Meal.container)
            .selectinload(Container.location)
        )
    )
    day = result.scalars().first()
    if not day:
        return []

    return sorted(day.meals, key=lambda m: MEAL_ORDER.get(m.meal_type, 99))


def _format_container(meal: Meal) -> dict | None:
    c = meal.container
    if not c:
        return None
    location_name = c.location.name if c.location else None
    return {
        "id": c.id,
        "label": c.label,
        "meal_type": meal.meal_type,
        "meal_id": meal.id,
        "status": meal.status,
        "contents_description": c.contents_description,
        "heating_instructions": c.heating_instructions,
        "kbzhu": c.kbzhu or meal.kbzhu_actual,
        "location": location_name,
    }


@router.get("/current")
async def get_current_container(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Return the first non-eaten container for today (current meal)."""
    meals = await _get_today_meals_with_containers(user_id, session)
    for meal in meals:
        if meal.status != "eaten" and meal.container:
            return _format_container(meal)
    return None


@router.get("/today")
async def get_today_containers(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Return all containers for today ordered by meal type."""
    meals = await _get_today_meals_with_containers(user_id, session)
    return [
        fmt
        for meal in meals
        if meal.container and (fmt := _format_container(meal))
    ]


@router.post("/{container_id}/eaten")
async def mark_container_eaten(
    container_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Mark container as eaten and update linked meal status."""
    result = await session.execute(
        select(Container)
        .where(Container.id == container_id)
        .where(Container.user_id == user_id)
        .options(selectinload(Container.meal))
    )
    container = result.scalar_one_or_none()
    if not container:
        raise HTTPException(status_code=404, detail="Container not found")

    container.status = "eaten"
    if container.meal:
        container.meal.status = "eaten"
        if not container.meal.kbzhu_actual and container.kbzhu:
            container.meal.kbzhu_actual = container.kbzhu

    await session.commit()
    return {"status": "eaten", "container_id": container_id}
