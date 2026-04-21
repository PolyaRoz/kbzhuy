from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user_id
from app.schemas.prep_task import PrepTaskResponse
from app.services.prep_task_service import PrepTaskService

router = APIRouter()


@router.get("/today", response_model=list[PrepTaskResponse])
async def get_today_tasks(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    svc = PrepTaskService(session)
    return await svc.get_today(user_id)


@router.post("/{task_id}/done")
async def mark_task_done(
    task_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    svc = PrepTaskService(session)
    task = await svc.mark_done(task_id=task_id, user_id=user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "done", "task_id": task_id}
