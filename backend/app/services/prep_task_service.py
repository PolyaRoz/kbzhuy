"""
Prep-task generator: auto-creates daily preparation tasks from container lifecycle.

Generated task types:
  - defrost: container in freezer needs to be moved to fridge (12-24h before eating)
  - move: container needs to be relocated (e.g. fridge shelf change)
  - check_expiry: container expiring within 24h, needs decision
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.prep_task import PrepTask
from app.models.container import Container
from app.models.storage import StorageLocation


class PrepTaskService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_today(self, user_id: int) -> list[PrepTask]:
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        result = await self.session.execute(
            select(PrepTask)
            .where(PrepTask.user_id == user_id)
            .where(PrepTask.scheduled_at >= start)
            .where(PrepTask.scheduled_at < end)
            .order_by(PrepTask.scheduled_at)
        )
        return list(result.scalars().all())

    async def mark_done(self, task_id: int, user_id: int) -> PrepTask | None:
        result = await self.session.execute(
            select(PrepTask).where(PrepTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task or task.user_id != user_id:
            return None
        task.status = "done"
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def generate_for_user(self, user_id: int) -> list[PrepTask]:
        """
        Generate prep tasks for tomorrow based on current container state.
        Called by Celery beat daily at midnight.
        """
        tomorrow = date.today() + timedelta(days=1)
        tasks_created: list[PrepTask] = []

        # Find containers expiring tomorrow (need to eat or freeze today)
        result = await self.session.execute(
            select(Container)
            .where(Container.expiry_date == tomorrow)
            .where(Container.status == "filled")
        )
        expiring = result.scalars().all()
        for c in expiring:
            task = PrepTask(
                user_id=user_id,
                container_id=c.id,
                type="check_expiry",
                description=f"Контейнер {c.label} истекает завтра — съесть, заморозить или выбросить",
                scheduled_at=datetime.now(timezone.utc).replace(hour=8, minute=0, second=0, microsecond=0),
                status="pending",
            )
            self.session.add(task)
            tasks_created.append(task)

        # Find freezer containers scheduled for tomorrow's meals → defrost today
        result = await self.session.execute(
            select(Container)
            .join(StorageLocation, Container.location_id == StorageLocation.id, isouter=True)
            .where(Container.status == "filled")
        )
        all_containers = result.scalars().all()

        for c in all_containers:
            # Check if the container's location is freezer (location name contains "морозилк" or type="freezer")
            if c.location_id:
                loc_result = await self.session.execute(
                    select(StorageLocation).where(StorageLocation.id == c.location_id)
                )
                loc = loc_result.scalar_one_or_none()
                if loc and loc.type == "freezer":
                    # Schedule defrost task for today (move to fridge 12-24h before eating)
                    task = PrepTask(
                        user_id=user_id,
                        container_id=c.id,
                        type="defrost",
                        description=f"Переложить контейнер {c.label} из морозилки в холодильник для разморозки к завтрашнему приёму пищи",
                        scheduled_at=datetime.now(timezone.utc).replace(hour=20, minute=0, second=0, microsecond=0),
                        status="pending",
                    )
                    self.session.add(task)
                    tasks_created.append(task)

        await self.session.commit()
        return tasks_created
