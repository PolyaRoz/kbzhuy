"""Celery tasks: cooking plan generation."""
from app.worker import celery_app


@celery_app.task(name="app.tasks.cooking.build_cooking_plan")
def build_cooking_plan(user_id: int, recipe_ids: list[int]) -> dict:
    """Build an optimised parallel cooking plan for a batch session."""
    # TODO: call CookingService.build_plan(user_id, recipe_ids)
    return {"status": "ok", "user_id": user_id}
