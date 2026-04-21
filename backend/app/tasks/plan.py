"""Celery tasks: plan generation and prep tasks."""
import asyncio

from app.worker import celery_app


@celery_app.task(name="app.tasks.plan.generate_plan_for_user")
def generate_plan_for_user(user_id: int) -> dict:
    """Generate a weekly meal plan for a user (async)."""
    from datetime import date
    from app.core.database import async_session
    from app.services.meal_planner_service import MealPlannerService

    async def _run():
        async with async_session() as session:
            svc = MealPlannerService(session)
            plan = await svc.generate(user_id=user_id, week_start=date.today())
            return plan.id

    plan_id = asyncio.run(_run())
    return {"status": "ok", "user_id": user_id, "plan_id": plan_id}


@celery_app.task(name="app.tasks.plan.generate_prep_tasks_for_today")
def generate_prep_tasks_for_today() -> dict:
    """Daily job at midnight: create defrost/move prep tasks for all active users."""
    from datetime import date
    from sqlalchemy import select
    from app.core.database import async_session
    from app.models.plan import MealPlan
    from app.services.prep_task_service import PrepTaskService

    async def _run():
        today = date.today()
        async with async_session() as session:
            result = await session.execute(
                select(MealPlan.user_id)
                .where(MealPlan.period_start <= today)
                .where(MealPlan.period_end >= today)
                .distinct()
            )
            user_ids = [row[0] for row in result.all()]

        tasks_count = 0
        for uid in user_ids:
            async with async_session() as session:
                svc = PrepTaskService(session)
                tasks = await svc.generate_for_user(uid)
                tasks_count += len(tasks)

        return tasks_count

    count = asyncio.run(_run())
    return {"status": "ok", "tasks_created": count}
