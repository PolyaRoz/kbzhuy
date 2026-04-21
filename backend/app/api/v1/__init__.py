from fastapi import APIRouter

from app.api.v1.profile import router as profile_router
from app.api.v1.plan import router as plan_router
from app.api.v1.shopping import router as shopping_router
from app.api.v1.cooking import router as cooking_router
from app.api.v1.storage import router as storage_router
from app.api.v1.containers import router as containers_router
from app.api.v1.prep_tasks import router as prep_tasks_router
from app.api.v1.deviations import router as deviations_router
from app.api.v1.agent import router as agent_router
from app.api.v1.progress import router as progress_router
from app.api.v1.auth import router as auth_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(profile_router, prefix="/profile", tags=["profile"])
router.include_router(plan_router, prefix="/plan", tags=["plan"])
router.include_router(shopping_router, prefix="/shopping-list", tags=["shopping"])
router.include_router(cooking_router, prefix="/cooking", tags=["cooking"])
router.include_router(storage_router, prefix="/storage", tags=["storage"])
router.include_router(containers_router, prefix="/containers", tags=["containers"])
router.include_router(prep_tasks_router, prefix="/prep-tasks", tags=["prep-tasks"])
router.include_router(deviations_router, prefix="/deviations", tags=["deviations"])
router.include_router(agent_router, prefix="/agent", tags=["agent"])
router.include_router(progress_router, prefix="/progress", tags=["progress"])
