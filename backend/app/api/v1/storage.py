from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter()


@router.get("")
async def get_all_storage(db: AsyncSession = Depends(get_db)):
    """Get all storage locations with contents."""
    ...


@router.get("/{location}")
async def get_location(location: str, db: AsyncSession = Depends(get_db)):
    """Get contents of a specific location (fridge/freezer/pantry)."""
    ...


@router.post("/containers")
async def add_container(db: AsyncSession = Depends(get_db)):
    """Add a container to storage."""
    ...


@router.patch("/containers/{container_id}")
async def update_container(container_id: int, db: AsyncSession = Depends(get_db)):
    """Move or update a container."""
    ...


@router.delete("/containers/{container_id}")
async def remove_container(container_id: int, db: AsyncSession = Depends(get_db)):
    """Remove / mark container as used."""
    ...


@router.get("/expiring")
async def get_expiring(db: AsyncSession = Depends(get_db)):
    """Get items expiring soon."""
    ...
