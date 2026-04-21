"""
Deviation engine: handles planned and spontaneous deviations from the diet plan.

Logic:
  - Planned deviation: pre-configured (beer on Fridays), already factored into the week
  - Spontaneous deviation: user ate something unplanned ("I ate pizza")
    → registers the extra kcal/macros
    → recalculates remaining daily targets for the rest of the week
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.deviation import Deviation
from app.models.plan import MealPlan, DayPlan
from app.models.profile import Profile
from app.services.nutri_service import NutriTarget


class DeviationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def register(
        self,
        user_id: int,
        description: str,
        deviation_type: str,
        kbzhu_impact: dict | None = None,
        deviation_date: date | None = None,
        plan_id: int | None = None,
        recurrence: str | None = None,
        day_of_week: int | None = None,
    ) -> Deviation:
        dev = Deviation(
            user_id=user_id,
            plan_id=plan_id,
            deviation_type=deviation_type,
            date=deviation_date or date.today(),
            description=description,
            kbzhu_impact=kbzhu_impact or {},
            recurrence=recurrence,
            day_of_week=day_of_week,
        )
        self.session.add(dev)
        await self.session.commit()
        await self.session.refresh(dev)
        return dev

    async def get_active_plan(self, user_id: int) -> MealPlan | None:
        today = date.today()
        result = await self.session.execute(
            select(MealPlan)
            .where(MealPlan.user_id == user_id)
            .where(MealPlan.period_start <= today)
            .where(MealPlan.period_end >= today)
        )
        return result.scalar_one_or_none()

    async def get_planned(self, user_id: int) -> list[Deviation]:
        result = await self.session.execute(
            select(Deviation)
            .where(Deviation.user_id == user_id)
            .where(Deviation.deviation_type == "planned")
        )
        return list(result.scalars().all())

    async def recalculate(self, user_id: int, deviation_id: int) -> dict:
        """
        After a spontaneous deviation, redistribute the extra kcal debt
        across the remaining days of the current week.

        Persists updated daily_targets to MealPlan and marks
        remaining DayPlans as "адаптировано".
        Returns updated daily targets for remaining days.
        """
        result = await self.session.execute(
            select(Deviation).where(Deviation.id == deviation_id)
        )
        dev = result.scalar_one_or_none()
        if not dev or dev.user_id != user_id:
            return {"error": "deviation not found"}

        plan = await self.get_active_plan(user_id)
        if not plan:
            return {"error": "no active plan"}

        impact = dev.kbzhu_impact or {}
        extra_kcal = impact.get("kcal", 0)

        today = date.today()
        days_remaining = (plan.period_end - today).days + 1  # include today
        if days_remaining <= 0:
            return {"adjusted": False, "reason": "no remaining days in plan"}

        # Spread the kcal debt over remaining days
        base_targets = plan.daily_targets or {}
        base_kcal = base_targets.get("kcal", 2000)
        adjusted_kcal = max(base_kcal - round(extra_kcal / days_remaining), 1200)

        # Proportionally adjust macros
        ratio = adjusted_kcal / base_kcal if base_kcal else 1.0
        adjusted = {
            "kcal": adjusted_kcal,
            "protein": round(base_targets.get("protein", 120) * ratio),
            "fat": round(base_targets.get("fat", 65) * ratio),
            "carbs": round(base_targets.get("carbs", 220) * ratio),
        }

        # Persist updated targets to the plan
        plan.daily_targets = adjusted
        self.session.add(plan)

        # Mark remaining days as "адаптировано"
        days_result = await self.session.execute(
            select(DayPlan)
            .where(DayPlan.plan_id == plan.id)
            .where(DayPlan.date >= today)
        )
        for day in days_result.scalars().all():
            note = f"адаптировано: {dev.description}"
            if day.notes and "адаптировано" not in day.notes:
                note = f"{day.notes} | {note}"
            day.notes = note
            self.session.add(day)

        await self.session.commit()

        return {
            "adjusted": True,
            "days_remaining": days_remaining,
            "extra_kcal_total": extra_kcal,
            "extra_kcal_per_day": round(extra_kcal / days_remaining),
            "new_daily_targets": adjusted,
            "original_daily_targets": base_targets,
        }
