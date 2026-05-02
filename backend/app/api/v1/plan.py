from datetime import date, datetime
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.core.security import get_current_user_id
from app.models.plan import MealPlan, DayPlan, Meal
from app.models.deviation import Deviation
from app.models.profile import Profile
from app.schemas.plan import MealStatusPatch, PlanGenerate
from app.services.ai_menu_service import AIMenuService
from app.services.meal_planner_service import MealPlannerService, recipe_details_by_name

router = APIRouter()

MEAL_ORDER = {"breakfast": 0, "lunch": 1, "snack": 2, "dinner": 3}
CONTAINER_WEEKDAY_CODES = {
    0: "ПН",
    1: "ВТ",
    2: "СР",
    3: "ЧТ",
    4: "ПТ",
    5: "СБ",
    6: "ВС",
}


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


def _container_label(day: DayPlan, meal: Meal, meal_meta: dict[str, dict]) -> str | None:
    if not meal.container:
        return None
    return meal.container.label


def _expected_container_label(day: DayPlan, meal: Meal, meal_meta: dict[str, dict]) -> str | None:
    order = meal_meta.get(meal.meal_type, {}).get("order", MEAL_ORDER.get(meal.meal_type, 0))
    weekday = CONTAINER_WEEKDAY_CODES.get(day.date.weekday(), "")
    return f"{int(order) + 1} {weekday}".strip()


def _looks_legacy_container_label(label: str | None) -> bool:
    if not label:
        return True
    return not any(code in label.upper() for code in CONTAINER_WEEKDAY_CODES.values())


def _serialize_plan(plan: MealPlan, meal_meta: dict[str, dict]) -> dict:
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
                        "container_label": _container_label(day, meal, meal_meta),
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


async def _normalize_container_labels(session: AsyncSession, plan: MealPlan, meal_meta: dict[str, dict]) -> None:
    labels_changed = False
    for day in plan.days:
        for meal in day.meals:
            if meal.container and _looks_legacy_container_label(meal.container.label):
                meal.container.label = _expected_container_label(day, meal, meal_meta) or meal.container.label
                labels_changed = True
    if labels_changed:
        await session.commit()


async def _auto_mark_elapsed_meals(session: AsyncSession, plan: MealPlan, meal_meta: dict[str, dict]) -> None:
    today = date.today()
    now_minutes = datetime.now().hour * 60 + datetime.now().minute
    changed = False
    for day in plan.days:
        for meal in day.meals:
            if meal.status != "planned":
                continue
            should_mark = day.date < today
            if day.date == today:
                raw_time = meal_meta.get(meal.meal_type, {}).get("time")
                match = re.match(r"^(\d{1,2}):(\d{2})", str(raw_time or ""))
                if match:
                    hour, minute = int(match.group(1)), int(match.group(2))
                    should_mark = now_minutes >= hour * 60 + minute + 30
            if should_mark:
                meal.status = "eaten"
                if meal.container:
                    meal.container.status = "eaten"
                    if not meal.kbzhu_actual and meal.container.kbzhu:
                        meal.kbzhu_actual = meal.container.kbzhu
                changed = True
    if changed:
        await session.commit()


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
    await _normalize_container_labels(session, plan, meal_meta)
    await _auto_mark_elapsed_meals(session, plan, meal_meta)
    return _serialize_plan(plan, meal_meta)


@router.get("/period/{period_start}")
async def get_plan_by_period(
    period_start: date,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(MealPlan)
        .where(MealPlan.user_id == user_id)
        .where(MealPlan.status == "active")
        .where(MealPlan.period_start == period_start)
        .order_by(MealPlan.created_at.desc(), MealPlan.id.desc())
        .options(
            selectinload(MealPlan.days).selectinload(DayPlan.meals).selectinload(Meal.container)
        )
    )
    plan = result.scalars().first()
    if not plan:
        raise HTTPException(status_code=404, detail="No active plan for period")

    profile_result = await session.execute(select(Profile).where(Profile.user_id == user_id))
    meal_meta = _profile_meal_meta(profile_result.scalar_one_or_none())
    await _normalize_container_labels(session, plan, meal_meta)
    return _serialize_plan(plan, meal_meta)


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


@router.patch("/meal/{meal_id}/status")
async def patch_meal_status(
    meal_id: int,
    body: MealStatusPatch,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    status = body.status.strip().casefold()
    if status not in {"planned", "eaten", "skipped"}:
        raise HTTPException(status_code=400, detail="Invalid meal status")

    result = await session.execute(
        select(Meal)
        .join(DayPlan, Meal.day_id == DayPlan.id)
        .join(MealPlan, DayPlan.plan_id == MealPlan.id)
        .where(Meal.id == meal_id)
        .where(MealPlan.user_id == user_id)
        .options(selectinload(Meal.container), selectinload(Meal.day))
    )
    meal = result.scalar_one_or_none()
    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found")

    profile_result = await session.execute(select(Profile).where(Profile.user_id == user_id))
    meal_meta = _profile_meal_meta(profile_result.scalar_one_or_none())

    meal.status = status
    if meal.container:
        meal.container.status = "eaten" if status == "eaten" else "filled"
        if status == "eaten" and not meal.kbzhu_actual and meal.container.kbzhu:
            meal.kbzhu_actual = meal.container.kbzhu

    await session.commit()
    return {
        "status": status,
        "meal": {
            "id": meal.id,
            "meal_type": meal.meal_type,
            "container_id": meal.container_id,
            "container_label": _container_label(meal.day, meal, meal_meta),
            "description": meal.container.contents_description if meal.container else None,
            "heating_instructions": meal.container.heating_instructions if meal.container else None,
            "status": meal.status,
            "kbzhu_actual": meal.kbzhu_actual,
        },
    }


@router.post("/meal/{meal_id}/swap-prepared")
async def swap_prepared_meal(
    meal_id: int,
    body: dict,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    target_meal_id = int(body.get("target_meal_id") or 0)
    if target_meal_id <= 0 or target_meal_id == meal_id:
        raise HTTPException(status_code=400, detail="Invalid target meal")

    result = await session.execute(
        select(Meal)
        .join(DayPlan, Meal.day_id == DayPlan.id)
        .join(MealPlan, DayPlan.plan_id == MealPlan.id)
        .where(Meal.id.in_([meal_id, target_meal_id]))
        .where(MealPlan.user_id == user_id)
        .where(MealPlan.status == "active")
        .options(selectinload(Meal.container), selectinload(Meal.day))
    )
    meals = result.scalars().all()
    if len(meals) != 2:
        raise HTTPException(status_code=404, detail="Meal not found")

    first = next(meal for meal in meals if meal.id == meal_id)
    second = next(meal for meal in meals if meal.id == target_meal_id)
    if first.day.date < date.today() or second.day.date < date.today():
        raise HTTPException(status_code=400, detail="Only today or future prepared meals can be swapped")
    if first.status == "eaten" or second.status == "eaten":
        raise HTTPException(status_code=400, detail="Only uneaten prepared meals can be swapped")
    if not first.container_id or not second.container_id:
        raise HTTPException(status_code=400, detail="Both meals must have prepared containers")

    first.container_id, second.container_id = second.container_id, first.container_id
    first.kbzhu_actual, second.kbzhu_actual = second.kbzhu_actual, first.kbzhu_actual
    first.status = "planned"
    second.status = "planned"

    await session.commit()
    return {"status": "swapped", "meal_id": meal_id, "target_meal_id": target_meal_id}


@router.post("/meal/{meal_id}/manual-replacement")
async def manual_replacement(
    meal_id: int,
    body: dict,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    description = str(body.get("description") or "").strip()
    if not description:
        raise HTTPException(status_code=400, detail="Description is required")

    result = await session.execute(
        select(Meal)
        .join(DayPlan, Meal.day_id == DayPlan.id)
        .join(MealPlan, DayPlan.plan_id == MealPlan.id)
        .where(Meal.id == meal_id)
        .where(MealPlan.user_id == user_id)
        .where(MealPlan.status == "active")
        .options(selectinload(Meal.day))
    )
    meal = result.scalar_one_or_none()
    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found")
    if meal.day.date < date.today():
        raise HTTPException(status_code=400, detail="Past meals cannot be replaced")

    meal.status = "eaten"
    session.add(
        Deviation(
            user_id=user_id,
            plan_id=meal.day.plan_id,
            deviation_type="spontaneous",
            date=meal.day.date,
            description=f"Вместо запланированного приема пищи: {description}",
            kbzhu_impact=None,
        )
    )
    await session.commit()
    return {"status": "recorded", "meal_id": meal_id, "description": description}


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
