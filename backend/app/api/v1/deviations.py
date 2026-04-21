from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user_id
from app.schemas.deviation import DeviationRegister, DeviationResponse, RecalculateRequest
from app.services.deviation_service import DeviationService

router = APIRouter()


@router.post("", response_model=DeviationResponse, status_code=201)
async def register_deviation(
    body: DeviationRegister,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    svc = DeviationService(session)
    plan = await svc.get_active_plan(user_id)
    dev = await svc.register(
        user_id=user_id,
        description=body.description,
        deviation_type=body.deviation_type,
        kbzhu_impact=body.kbzhu_impact,
        deviation_date=date.fromisoformat(body.date) if body.date else date.today(),
        plan_id=plan.id if plan else None,
        recurrence=body.recurrence,
    )
    return dev


@router.get("/planned", response_model=list[DeviationResponse])
async def get_planned_deviations(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    svc = DeviationService(session)
    return await svc.get_planned(user_id)


@router.post("/recalc")
async def recalculate_after_deviation(
    body: RecalculateRequest,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    svc = DeviationService(session)
    result = await svc.recalculate(user_id=user_id, deviation_id=body.deviation_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
