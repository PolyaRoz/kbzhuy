"""
Cooking-planner service: builds an optimised parallel batch-cooking schedule.

Algorithm (MVP rule-based):
  1. Collect unique recipes from the active meal plan
  2. Group steps by execution type: oven / stovetop / parallel / no-cook
  3. Sort by duration (longest first) for max parallelism
  4. Assign parallel_group IDs where steps can overlap
  5. Persist CookingPlan + CookingSteps
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.cooking import CookingPlan, CookingStep
from app.models.plan import MealPlan, DayPlan, Meal
from app.models.container import Container

# --- step templates per recipe tag -----------------------------------------

STEP_TEMPLATES: dict[str, list[dict]] = {
    "oven": [
        {"title": "Подготовка", "description": "Нарежьте и замаринуйте мясо.", "duration": 15, "parallel": False, "group": None},
        {"title": "Духовка", "description": "Разогрейте до 200°C, запекайте.", "duration": 45, "parallel": True,  "group": 1},
    ],
    "pan": [
        {"title": "Подготовка фарша", "description": "Смешайте фарш с луком и специями.", "duration": 10, "parallel": False, "group": None},
        {"title": "Жарка котлет", "description": "Жарьте на среднем огне 5-6 мин каждую сторону.", "duration": 25, "parallel": True, "group": 2},
    ],
    "grain": [
        {"title": "Варка гарниров", "description": "Поставьте гречку и рис вариться одновременно.", "duration": 20, "parallel": True, "group": 1},
    ],
}

DEFAULT_STEPS = [
    {"title": "Подготовка", "description": "Подготовьте ингредиенты.", "duration": 10, "parallel": False, "group": None},
    {"title": "Готовка", "description": "Приготовьте по рецепту.", "duration": 20, "parallel": False, "group": None},
]

PACKING_STEP = {
    "title": "Раскладка по контейнерам",
    "description": "Разложите готовые блюда по контейнерам согласно схеме.",
    "duration": 10,
    "parallel": False,
    "group": None,
}


class CookingPlannerService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def build_for_plan(self, user_id: int, meal_plan_id: int, scheduled_date: date) -> CookingPlan:
        """
        Build a parallel cooking plan for all batch-cookable recipes in a MealPlan.
        """
        # Collect containers (= unique recipes) for this plan
        result = await self.session.execute(
            select(Container)
            .where(Container.plan_id == meal_plan_id)
            .where(Container.status == "filled")
        )
        containers = list(result.scalars().all())

        # Derive unique recipe names to build steps from
        recipe_names = list({c.contents_description for c in containers if c.contents_description})
        container_distribution = self._build_distribution(containers)

        # Build ordered step list
        raw_steps = self._build_steps(recipe_names)
        raw_steps.append(PACKING_STEP)

        total_minutes = sum(s["duration"] for s in raw_steps)
        # Parallel optimisation: overlapping groups reduce active time
        parallel_groups = list({s["group"] for s in raw_steps if s["group"] is not None})
        parallel_savings = sum(
            s["duration"]
            for s in raw_steps
            if s["group"] is not None and (s["group"] != parallel_groups[0] if parallel_groups else False)
        )
        active_minutes = max(total_minutes - parallel_savings, total_minutes // 2)

        cooking_plan = CookingPlan(
            user_id=user_id,
            plan_id=meal_plan_id,
            scheduled_date=scheduled_date,
            estimated_time_min=total_minutes,
            active_time_min=active_minutes,
            parallel_groups=parallel_groups,
            container_distribution=container_distribution,
        )
        self.session.add(cooking_plan)
        await self.session.flush()

        for i, step_data in enumerate(raw_steps, start=1):
            step = CookingStep(
                cooking_plan_id=cooking_plan.id,
                step_number=i,
                title=step_data["title"],
                description=step_data["description"],
                duration_minutes=step_data["duration"],
                is_parallel=step_data["parallel"],
                parallel_group=step_data.get("group"),
            )
            self.session.add(step)

        await self.session.commit()
        await self.session.refresh(cooking_plan)
        return cooking_plan

    def _build_steps(self, recipe_names: list[str]) -> list[dict]:
        """Infer cooking steps from recipe names (tag-based heuristic)."""
        used_tags: set[str] = set()
        steps: list[dict] = []

        for name in recipe_names:
            name_lower = name.lower()
            if "котлет" in name_lower or "фарш" in name_lower:
                if "pan" not in used_tags:
                    steps.extend(STEP_TEMPLATES["pan"])
                    used_tags.add("pan")
            if any(w in name_lower for w in ["ножк", "грудк", "стейк"]):
                if "oven" not in used_tags:
                    steps.extend(STEP_TEMPLATES["oven"])
                    used_tags.add("oven")
            if any(w in name_lower for w in ["гречк", "рис", "овсянк"]):
                if "grain" not in used_tags:
                    steps.extend(STEP_TEMPLATES["grain"])
                    used_tags.add("grain")

        if not steps:
            steps = list(DEFAULT_STEPS)

        # Deduplicate by title keeping first occurrence
        seen: set[str] = set()
        unique: list[dict] = []
        for s in steps:
            if s["title"] not in seen:
                seen.add(s["title"])
                unique.append(s)
        return unique

    def _build_distribution(self, containers: list) -> dict:
        """Map label → {description, location} for the UI distribution card."""
        return {
            c.label: {
                "description": c.contents_description,
                "expiry_date": c.expiry_date.isoformat() if c.expiry_date else None,
                "kbzhu": c.kbzhu,
            }
            for c in containers
        }
