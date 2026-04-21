from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter()


@router.get("")
async def get_progress(db: AsyncSession = Depends(get_db)):
    """Get progress dashboard: KBZHU adherence, weight, streaks."""
    ...


@router.post("/log")
async def log_progress(db: AsyncSession = Depends(get_db)):
    """Log a meal or weighing event."""
    ...
