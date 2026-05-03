import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.core.security import get_current_user_id
from app.models.cooking import CookingPlan, CookingStep
from app.models.plan import DayPlan, Meal, MealPlan
from app.services.cooking_planner_service import COOKING_PLAN_VERSION, CookingPlannerService
from app.services.inventory_service import InventoryService

router = APIRouter()


def _ingredients_from_step_description(description: str) -> list[tuple[str, float, str]]:
    match = re.search(r"(?m)^Количество:\s*(.+?)\.\s*$", description or "")
    if not match:
        return []
    ingredients: list[tuple[str, float, str]] = []
    for raw_item in re.split(r",\s+(?=[А-ЯЁA-Z])", match.group(1)):
        item_match = re.match(r"(.+?)\s+([\d.,]+)\s*([^\d\s.,]+)\s*$", raw_item.strip())
        if not item_match:
            continue
        name = item_match.group(1).strip()
        quantity = float(item_match.group(2).replace(",", "."))
        unit = item_match.group(3).strip()
        ingredients.append((name, quantity, unit))
    return ingredients


async def _sync_step_inventory(session: AsyncSession, user_id: int, step: CookingStep, done: bool) -> None:
    ingredients = _ingredients_from_step_description(step.description)
    if not ingredients:
        return
    inventory = InventoryService(session)
    for name, quantity, unit in ingredients:
        if done:
            await inventory.use_by_name(user_id, name, quantity, unit)
        else:
            await inventory.upsert_item(
                user_id=user_id,
                name=name,
                quantity=quantity,
                unit=unit,
                location_type=None,
            )


async def _active_meal_plan(session: AsyncSession, user_id: int) -> MealPlan | None:
    result = await session.execute(
        select(MealPlan)
        .where(MealPlan.user_id == user_id)
        .where(MealPlan.status == "active")
        .order_by(MealPlan.period_start.desc(), MealPlan.created_at.desc(), MealPlan.id.desc())
        .options(
            selectinload(MealPlan.days)
            .selectinload(DayPlan.meals)
            .selectinload(Meal.container)
        )
    )
    return result.scalars().first()


def _serialize_cooking_plan(plan: CookingPlan) -> dict:
    visible_steps = sorted(plan.steps, key=lambda s: s.step_number)
    return {
        "id": plan.id,
        "scheduled_date": plan.scheduled_date.isoformat() if plan.scheduled_date else None,
        "estimated_time_min": plan.estimated_time_min,
        "active_time_min": plan.active_time_min,
        "parallel_groups": plan.parallel_groups,
        "container_distribution": plan.container_distribution,
        "steps": [
            {
                "id": step.id,
                "step_number": step.step_number,
                "title": step.title,
                "description": step.description,
                "duration_minutes": step.duration_minutes,
                "is_parallel": step.is_parallel,
                "parallel_group": step.parallel_group,
                "done": step.done,
            }
            for step in visible_steps
        ],
    }


@router.get("/plan")
async def get_cooking_plan(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    meal_plan = await _active_meal_plan(session, user_id)
    if not meal_plan:
        raise HTTPException(status_code=404, detail="No active meal plan")

    result = await session.execute(
        select(CookingPlan)
        .where(CookingPlan.user_id == user_id)
        .where(CookingPlan.plan_id == meal_plan.id)
        .options(selectinload(CookingPlan.steps))
    )
    plan = result.scalars().first()
    meta = plan.container_distribution if plan else {}
    if not plan or not isinstance(meta, dict) or meta.get("version") != COOKING_PLAN_VERSION:
        svc = CookingPlannerService(session)
        plan = await svc.build_for_plan(user_id=user_id, meal_plan_id=meal_plan.id, scheduled_date=meal_plan.period_start)
        result = await session.execute(
            select(CookingPlan)
            .where(CookingPlan.id == plan.id)
            .options(selectinload(CookingPlan.steps))
        )
        plan = result.scalar_one()
    return _serialize_cooking_plan(plan)


@router.get("/plan/period/{period_start}")
async def get_cooking_plan_by_period(
    period_start: str,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    from datetime import date as date_type
    try:
        period_start_date = date_type.fromisoformat(period_start)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    result = await session.execute(
        select(MealPlan)
        .where(MealPlan.user_id == user_id)
        .where(MealPlan.status == "active")
        .where(MealPlan.period_start == period_start_date)
    )
    meal_plan = result.scalars().first()
    if not meal_plan:
        raise HTTPException(status_code=404, detail="No meal plan for this period")

    result = await session.execute(
        select(CookingPlan)
        .where(CookingPlan.user_id == user_id)
        .where(CookingPlan.plan_id == meal_plan.id)
        .options(selectinload(CookingPlan.steps))
    )
    plan = result.scalars().first()
    meta = plan.container_distribution if plan else {}
    if not plan or not isinstance(meta, dict) or meta.get("version") != COOKING_PLAN_VERSION:
        svc = CookingPlannerService(session)
        plan = await svc.build_for_plan(
            user_id=user_id,
            meal_plan_id=meal_plan.id,
            scheduled_date=meal_plan.period_start,
        )
        result = await session.execute(
            select(CookingPlan)
            .where(CookingPlan.id == plan.id)
            .options(selectinload(CookingPlan.steps))
        )
        plan = result.scalar_one()
    return _serialize_cooking_plan(plan)


@router.post("/generate")
async def generate_cooking_plan(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    meal_plan = await _active_meal_plan(session, user_id)
    if not meal_plan:
        raise HTTPException(status_code=404, detail="No active meal plan")

    svc = CookingPlannerService(session)
    cp = await svc.build_for_plan(user_id=user_id, meal_plan_id=meal_plan.id, scheduled_date=meal_plan.period_start)
    return {"status": "generated", "cooking_plan_id": cp.id}


@router.post("/steps/{step_id}/done")
async def mark_step_done(
    step_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(CookingStep)
        .join(CookingPlan)
        .where(CookingStep.id == step_id)
        .where(CookingPlan.user_id == user_id)
    )
    step = result.scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    step.done = True
    await session.commit()
    return {"status": "done", "step_id": step_id}


@router.patch("/steps/{step_id}")
async def set_step_done(
    step_id: int,
    body: dict,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(CookingStep)
        .join(CookingPlan)
        .where(CookingStep.id == step_id)
        .where(CookingPlan.user_id == user_id)
    )
    step = result.scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    done = bool(body.get("done"))
    step.done = done
    await session.commit()
    return {"status": "updated", "step_id": step_id, "done": step.done}


@router.get("/containers")
async def get_container_distribution(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    meal_plan = await _active_meal_plan(session, user_id)
    if not meal_plan:
        raise HTTPException(status_code=404, detail="No active meal plan")
    result = await session.execute(
        select(CookingPlan)
        .where(CookingPlan.user_id == user_id)
        .where(CookingPlan.plan_id == meal_plan.id)
    )
    plan = result.scalars().first()
    if not plan:
        svc = CookingPlannerService(session)
        plan = await svc.build_for_plan(user_id=user_id, meal_plan_id=meal_plan.id, scheduled_date=meal_plan.period_start)
    return plan.container_distribution
