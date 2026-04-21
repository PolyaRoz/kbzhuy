from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_session
from app.core.security import get_current_user_id
from app.models.profile import Profile
from app.schemas.profile import ProfileCreate, ProfileUpdate, ProfileResponse
from app.services.nutri_service import calculate_targets, Goal, ActivityLevel

router = APIRouter()


@router.post("/onboarding", response_model=ProfileResponse, status_code=201)
async def onboarding(
    body: ProfileCreate,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Profile).where(Profile.user_id == user_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Profile already exists, use PATCH")

    targets = calculate_targets(
        weight_kg=body.weight_kg or 80.0,
        height_cm=body.height_cm or 175.0,
        age=body.age or 30,
        sex=body.sex or "male",
        activity=ActivityLevel(body.activity_level or "moderate"),
        goal=Goal(body.goal or "maintain"),
    )

    profile = Profile(
        user_id=user_id,
        name=body.name,
        sex=body.sex or "male",
        goal=body.goal,
        weight_kg=body.weight_kg,
        height_cm=body.height_cm,
        age=body.age,
        activity_level=body.activity_level,
        measurements=body.measurements or {},
        training_days=body.training_days or [],
        sport_types=body.sport_types or [],
        target_kcal=targets.kcal,
        target_protein_g=targets.protein,
        target_fat_g=targets.fat,
        target_carbs_g=targets.carbs,
        allergies=body.allergies,
        disliked_foods=body.disliked_foods,
        budget_rub_week=body.budget_rub_week,
        diet_type=body.diet_type,
        cooking_frequency=body.cooking_frequency,
        cooking_time_budget=body.cooking_time_budget or {},
        family_size=body.family_size,
        kitchen_equipment=body.kitchen_equipment or [],
        eating_schedule=body.eating_schedule,
        planned_deviations=body.planned_deviations,
        flexibility_pct=body.flexibility_pct or 10,
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile


@router.get("", response_model=ProfileResponse)
async def get_profile(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Profile).where(Profile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.patch("", response_model=ProfileResponse)
async def update_profile(
    body: ProfileUpdate,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Profile).where(Profile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    update_data = body.model_dump(exclude_unset=True)
    recalc_fields = {"sex", "weight_kg", "height_cm", "age", "activity_level", "goal"}
    if recalc_fields & set(update_data.keys()):
        targets = calculate_targets(
            weight_kg=update_data.get("weight_kg", profile.weight_kg) or 80.0,
            height_cm=update_data.get("height_cm", profile.height_cm) or 175.0,
            age=update_data.get("age", profile.age) or 30,
            sex=update_data.get("sex", profile.sex) or "male",
            activity=ActivityLevel(update_data.get("activity_level", profile.activity_level) or "moderate"),
            goal=Goal(update_data.get("goal", profile.goal) or "maintain"),
        )
        update_data.update(
            target_kcal=targets.kcal,
            target_protein_g=targets.protein,
            target_fat_g=targets.fat,
            target_carbs_g=targets.carbs,
        )

    for field, value in update_data.items():
        setattr(profile, field, value)
    await session.commit()
    await session.refresh(profile)
    return profile
