from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.core.security import get_current_user_id
from app.models.plan import MealPlan, DayPlan, Meal
from app.models.deviation import Deviation
from app.models.profile import Profile
from app.schemas.plan import PlanGenerate
from app.services.ai_menu_service import AIMenuService
from app.services.meal_planner_service import MealPlannerService, recipe_details_by_name

router = APIRouter()

MEAL_ORDER = {"breakfast": 0, "lunch": 1, "snack": 2, "dinner": 3}


def _profile_meal_meta(profile: Profile | None) -> dict[str, dict]:
    raw_meals = (profile.eating_schedule or {}).get("meals") if profile else None
    if isinstance(raw_meals, list) and raw_meals:
        return {
            str(meal.get("id") or f"meal_{index + 1}"): {
                "order": index,
                "name": str(meal.get("name") or f"Прием {index + 1}"),
                "time": str(meal.get("time") or "12:00"),
            }
            for index, meal in enumerate(raw_meals)
            if isinstance(meal, dict)
        }
    return {
        "breakfast": {"order": 0, "name": "Завтрак", "time": "08:00"},
        "lunch": {"order": 1, "name": "Обед", "time": "13:00"},
        "snack": {"order": 2, "name": "Перекус", "time": "16:00"},
        "dinner": {"order": 3, "name": "Ужин", "time": "19:00"},
    }


@router.post("/generate", status_code=202)
async def generate_plan(
    body: PlanGenerate,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    week_start = date.fromisoformat(str(body.period_start))

    if body.use_ai:
        svc = AIMenuService(session)
        result = await svc.generate(user_id=user_id, week_start=week_start, notes=body.notes)
        plan = result["plan"]
        return {
            "status": "generated",
            "plan_id": plan.id,
            "source": result["source"],
            "ai_reply": result["summary"],
        }

    svc = MealPlannerService(session)
    plan = await svc.generate(user_id=user_id, week_start=week_start)
    return {"status": "generated", "plan_id": plan.id}


@router.get("/current")
async def get_current_plan(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    today = date.today()
    result = await session.execute(
        select(MealPlan)
        .where(MealPlan.user_id == user_id)
        .where(MealPlan.status == "active")
        .where(MealPlan.period_start <= today)
        .where(MealPlan.period_end >= today)
        .order_by(MealPlan.created_at.desc(), MealPlan.id.desc())
        .options(
            selectinload(MealPlan.days).selectinload(DayPlan.meals).selectinload(Meal.container)
        )
    )
    plan = result.scalars().first()
    if not plan:
        raise HTTPException(status_code=404, detail="No active plan")

    profile_result = await session.execute(select(Profile).where(Profile.user_id == user_id))
    meal_meta = _profile_meal_meta(profile_result.scalar_one_or_none())

    return {
        "id": plan.id,
        "period_start": plan.period_start.isoformat(),
        "period_end": plan.period_end.isoformat(),
        "status": plan.status,
        "daily_targets": plan.daily_targets,
        "days": [
            {
                "id": day.id,
                "date": day.date.isoformat(),
                "meals": [
                    {
                        "id": meal.id,
                        "meal_type": meal.meal_type,
                        "meal_name": meal_meta.get(meal.meal_type, {}).get("name", meal.meal_type),
                        "meal_time": meal_meta.get(meal.meal_type, {}).get("time"),
                        "container_id": meal.container_id,
                        "container_label": meal.container.label if meal.container else None,
                        "description": meal.container.contents_description if meal.container else None,
                        "recipe_details": recipe_details_by_name(meal.container.contents_description if meal.container else None),
                        "heating_instructions": meal.container.heating_instructions if meal.container else None,
                        "status": meal.status,
                        "kbzhu_actual": meal.kbzhu_actual,
                    }
                    for meal in sorted(day.meals, key=lambda m: meal_meta.get(m.meal_type, {}).get("order", MEAL_ORDER.get(m.meal_type, 99)))
                ],
            }
            for day in sorted(plan.days, key=lambda d: d.date)
        ],
    }


@router.patch("/day/{day_id}")
async def patch_day(
    day_id: int,
    body: dict,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(DayPlan)
        .join(MealPlan, DayPlan.plan_id == MealPlan.id)
        .where(DayPlan.id == day_id)
        .where(MealPlan.user_id == user_id)
    )
    day = result.scalar_one_or_none()
    if not day:
        raise HTTPException(status_code=404, detail="Day not found")
    allowed = {"notes"}
    for k, v in body.items():
        if k in allowed:
            setattr(day, k, v)
    await session.commit()
    return {"status": "updated"}


@router.post("/day/{day_id}/rebuild")
async def rebuild_day(
    day_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    svc = MealPlannerService(session)
    try:
        day = await svc.rebuild_day(user_id=user_id, day_id=day_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"status": "updated", "day_id": day.id}


@router.post("/meal/{meal_id}/replace")
async def replace_meal(
    meal_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    svc = MealPlannerService(session)
    try:
        meal = await svc.replace_meal(user_id=user_id, meal_id=meal_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    await session.refresh(meal, attribute_names=["container"])
    return {
        "status": "updated",
        "meal": {
            "id": meal.id,
            "meal_type": meal.meal_type,
            "container_id": meal.container_id,
            "description": meal.container.contents_description if meal.container else None,
            "heating_instructions": meal.container.heating_instructions if meal.container else None,
            "status": meal.status,
            "kbzhu_actual": meal.kbzhu_actual,
        },
    }


@router.get("/deviations")
async def get_deviations(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Deviation)
        .where(Deviation.user_id == user_id)
        .where(Deviation.deviation_type == "planned")
    )
    return [
        {
            "id": d.id,
            "user_id": d.user_id,
            "plan_id": d.plan_id,
            "deviation_type": d.deviation_type,
            "date": d.date.isoformat() if d.date else None,
            "description": d.description,
            "kbzhu_impact": d.kbzhu_impact,
            "recurrence": d.recurrence,
            "day_of_week": d.day_of_week,
        }
        for d in result.scalars().all()
    ]
