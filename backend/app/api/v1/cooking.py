from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.core.security import get_current_user_id
from app.models.cooking import CookingPlan, CookingStep
from app.models.plan import MealPlan
from app.services.cooking_planner_service import CookingPlannerService

router = APIRouter()


@router.get("/plan")
async def get_cooking_plan(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(CookingPlan)
        .where(CookingPlan.user_id == user_id)
        .order_by(CookingPlan.created_at.desc())
        .options(selectinload(CookingPlan.steps))
    )
    plan = result.scalars().first()
    if not plan:
        raise HTTPException(status_code=404, detail="No cooking plan")
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
            for step in sorted(plan.steps, key=lambda s: s.step_number)
        ],
    }


@router.post("/generate")
async def generate_cooking_plan(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    today = date.today()
    result = await session.execute(
        select(MealPlan)
        .where(MealPlan.user_id == user_id)
        .where(MealPlan.period_start <= today)
        .where(MealPlan.period_end >= today)
    )
    meal_plan = result.scalar_one_or_none()
    if not meal_plan:
        raise HTTPException(status_code=404, detail="No active meal plan")

    svc = CookingPlannerService(session)
    cp = await svc.build_for_plan(user_id=user_id, meal_plan_id=meal_plan.id, scheduled_date=today)
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


@router.get("/containers")
async def get_container_distribution(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(CookingPlan)
        .where(CookingPlan.user_id == user_id)
        .order_by(CookingPlan.created_at.desc())
    )
    plan = result.scalars().first()
    if not plan:
        raise HTTPException(status_code=404, detail="No cooking plan")
    return plan.container_distribution
