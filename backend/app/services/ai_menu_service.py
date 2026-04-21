from __future__ import annotations

import json
import logging
import re
from datetime import date, timedelta
from typing import Any

import anthropic
import openai
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.container import Container
from app.models.plan import DayPlan, Meal, MealPlan
from app.models.profile import Profile
from app.models.shopping import ShoppingItem, ShoppingList
from app.services.meal_planner_service import MEAL_SCHEDULE, _load_recipes
from app.services.nutri_service import ActivityLevel, Goal, calculate_targets

logger = logging.getLogger("kbzhuy.ai_menu")
settings = get_settings()


class AIMenuService:
    """Generate a validated weekly menu from profile inputs and optional user notes."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate(self, user_id: int, week_start: date, notes: str | None = None) -> dict:
        profile = await self._get_profile(user_id)
        targets = self._targets(profile)
        recipes = self._filtered_recipes(profile)
        blueprint = await self._build_blueprint_with_llm(profile, targets, recipes, week_start, notes)
        plan = await self._persist_blueprint(user_id, week_start, targets, blueprint, recipes)
        return {
            "plan": plan,
            "source": blueprint.get("source", "fallback"),
            "summary": blueprint.get("summary", "План построен автоматически по профилю."),
        }

    async def _get_profile(self, user_id: int) -> Profile:
        result = await self.session.execute(select(Profile).where(Profile.user_id == user_id))
        profile = result.scalar_one_or_none()
        if profile is None:
            raise ValueError("Profile not found")
        return profile

    def _targets(self, profile: Profile) -> dict:
        if profile.target_kcal and profile.target_protein_g and profile.target_fat_g and profile.target_carbs_g:
            return {
                "kcal": profile.target_kcal,
                "protein": profile.target_protein_g,
                "fat": profile.target_fat_g,
                "carbs": profile.target_carbs_g,
            }
        target = calculate_targets(
            weight_kg=profile.weight_kg or 80.0,
            height_cm=profile.height_cm or 175.0,
            age=profile.age or 30,
            sex=profile.sex or "male",
            activity=ActivityLevel(profile.activity_level or "moderate"),
            goal=Goal(profile.goal or "maintain"),
        )
        return {"kcal": target.kcal, "protein": target.protein, "fat": target.fat, "carbs": target.carbs}

    def _filtered_recipes(self, profile: Profile) -> list[dict]:
        avoid = [*self._as_list(profile.allergies), *self._as_list(profile.disliked_foods)]
        diet_type = (profile.diet_type or "").casefold()
        recipes = []
        for recipe in _load_recipes():
            haystack = json.dumps(recipe, ensure_ascii=False).casefold()
            if any(str(term).casefold() in haystack for term in avoid if term):
                continue
            tags = set(recipe.get("tags", []))
            if diet_type in {"vegetarian", "vegan"} and tags & {"chicken", "beef", "fish"}:
                continue
            recipes.append(recipe)
        return recipes or _load_recipes()

    async def _build_blueprint_with_llm(
        self,
        profile: Profile,
        targets: dict,
        recipes: list[dict],
        week_start: date,
        notes: str | None,
    ) -> dict:
        fallback = self._fallback_blueprint(recipes, profile, week_start)
        prompt = self._prompt(profile, targets, recipes, week_start, notes)
        try:
            text = await self._call_llm(prompt)
            if not text:
                return fallback
            blueprint = self._extract_json(text)
            self._validate_blueprint(blueprint, recipes)
            blueprint["source"] = "ai"
            return blueprint
        except Exception as exc:
            logger.warning("AI menu fallback: %s", exc)
            return fallback

    async def _call_llm(self, prompt: str) -> str | None:
        if settings.use_local_llm:
            client = openai.AsyncOpenAI(base_url=settings.local_llm_url, api_key="ollama")
            response = await client.chat.completions.create(
                model=settings.local_llm_model,
                messages=[
                    {"role": "system", "content": "Return only valid JSON. No markdown."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=4096,
            )
            return response.choices[0].message.content

        if not settings.anthropic_api_key:
            return None

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model=settings.ai_model,
            max_tokens=4096,
            temperature=0.4,
            system="Return only valid JSON. No markdown.",
            messages=[{"role": "user", "content": prompt}],
        )
        return "\n".join(block.text for block in response.content if hasattr(block, "text"))

    def _prompt(self, profile: Profile, targets: dict, recipes: list[dict], week_start: date, notes: str | None) -> str:
        catalog = [
            {
                "id": r["id"],
                "name": r["name"],
                "meal_types": r["meal_types"],
                "tags": r.get("tags", []),
                "kbzhu": r["kbzhu_per_serving"],
            }
            for r in recipes[:60]
        ]
        profile_payload = {
            "sex": profile.sex,
            "age": profile.age,
            "height_cm": profile.height_cm,
            "weight_kg": profile.weight_kg,
            "activity_level": profile.activity_level,
            "goal": profile.goal,
            "allergies": profile.allergies or [],
            "disliked_foods": profile.disliked_foods or [],
            "diet_type": profile.diet_type,
            "budget_rub_week": profile.budget_rub_week,
            "cooking_frequency": profile.cooking_frequency,
            "family_size": profile.family_size,
            "kitchen_equipment": profile.kitchen_equipment or [],
            "eating_schedule": profile.eating_schedule or {},
            "planned_deviations": profile.planned_deviations or [],
            "flexibility_pct": profile.flexibility_pct,
            "user_notes": notes or "",
        }
        return (
            "Собери недельное меню для batch-cooking приложения КБЖУЙ.\n"
            "Используй только recipe_id из каталога. Не выдумывай блюда.\n"
            "Каждый день должен содержать breakfast, lunch, snack, dinner.\n"
            "Учитывай аллергию, нелюбимые продукты, бюджет, цель, расписание и плановые отклонения.\n"
            "Верни JSON строго такого вида: "
            '{"summary":"...", "days":[{"date":"YYYY-MM-DD","meals":[{"meal_type":"breakfast","recipe_ids":[1],"reason":"..."}]}]}.\n'
            f"week_start={week_start.isoformat()}\n"
            f"daily_targets={json.dumps(targets, ensure_ascii=False)}\n"
            f"profile={json.dumps(profile_payload, ensure_ascii=False)}\n"
            f"recipes={json.dumps(catalog, ensure_ascii=False)}"
        )

    def _fallback_blueprint(self, recipes: list[dict], profile: Profile, week_start: date) -> dict:
        days = []
        for offset in range(7):
            meals = []
            for meal_type, _ in MEAL_SCHEDULE:
                candidates = [r for r in recipes if meal_type in r.get("meal_types", [])] or recipes
                candidates = self._prefer_by_profile(candidates, profile)
                recipe = candidates[(offset + len(meals)) % len(candidates)]
                meals.append({
                    "meal_type": meal_type,
                    "recipe_ids": [recipe["id"]],
                    "reason": "Подобрано автоматически по профилю и ограничениям.",
                })
            days.append({"date": (week_start + timedelta(days=offset)).isoformat(), "meals": meals})
        return {
            "source": "fallback",
            "summary": "AI недоступен, поэтому меню построено локальным планировщиком по профилю.",
            "days": days,
        }

    def _prefer_by_profile(self, recipes: list[dict], profile: Profile) -> list[dict]:
        goal = profile.goal or "maintain"
        if goal in {"loss", "recomp"}:
            return sorted(recipes, key=lambda r: (-r["kbzhu_per_serving"].get("protein", 0), r["kbzhu_per_serving"].get("kcal", 0)))
        if goal == "gain":
            return sorted(recipes, key=lambda r: -r["kbzhu_per_serving"].get("kcal", 0))
        return sorted(recipes, key=lambda r: r["id"])

    def _extract_json(self, text: str) -> dict:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.S)
            if not match:
                raise
            return json.loads(match.group(0))

    def _validate_blueprint(self, blueprint: dict, recipes: list[dict]) -> None:
        recipe_ids = {int(r["id"]) for r in recipes}
        days = blueprint.get("days")
        if not isinstance(days, list) or len(days) != 7:
            raise ValueError("AI blueprint must contain 7 days")
        valid_meals = {m[0] for m in MEAL_SCHEDULE}
        for day in days:
            meals = day.get("meals")
            if not isinstance(meals, list) or not meals:
                raise ValueError("AI blueprint day has no meals")
            seen = set()
            for meal in meals:
                meal_type = meal.get("meal_type")
                if meal_type not in valid_meals:
                    raise ValueError(f"invalid meal_type: {meal_type}")
                seen.add(meal_type)
                ids = meal.get("recipe_ids")
                if not isinstance(ids, list) or not ids:
                    raise ValueError("meal recipe_ids required")
                if any(int(recipe_id) not in recipe_ids for recipe_id in ids):
                    raise ValueError("unknown recipe_id in AI blueprint")
            if not valid_meals <= seen:
                raise ValueError("AI blueprint must include all meal types for every day")

    async def _persist_blueprint(
        self,
        user_id: int,
        week_start: date,
        targets: dict,
        blueprint: dict,
        recipes: list[dict],
    ) -> MealPlan:
        week_end = week_start + timedelta(days=6)
        await self.session.execute(
            update(MealPlan)
            .where(MealPlan.user_id == user_id)
            .where(MealPlan.status == "active")
            .where(MealPlan.period_start <= week_end)
            .where(MealPlan.period_end >= week_start)
            .values(status="cancelled")
        )
        recipe_by_id = {int(r["id"]): r for r in recipes}
        plan = MealPlan(
            user_id=user_id,
            period_start=week_start,
            period_end=week_end,
            daily_targets=targets,
            status="active",
        )
        self.session.add(plan)
        await self.session.flush()

        shopping_agg: dict[str, dict] = {}
        label_index = 0
        labels = [f"{row}{col}" for row in range(1, 8) for col in "АБВГ"]

        for day_payload in blueprint["days"]:
            day_date = date.fromisoformat(day_payload["date"])
            day_plan = DayPlan(plan_id=plan.id, date=day_date, notes=day_payload.get("notes"))
            self.session.add(day_plan)
            await self.session.flush()

            for meal_payload in sorted(day_payload["meals"], key=lambda m: self._meal_order(m["meal_type"])):
                selected = [recipe_by_id[int(recipe_id)] for recipe_id in meal_payload["recipe_ids"]]
                merged = self._merge_recipes(selected, meal_payload["meal_type"], targets)
                label = labels[label_index % len(labels)]
                label_index += 1
                container = Container(
                    user_id=user_id,
                    label=label,
                    plan_id=plan.id,
                    status="filled",
                    contents_description=merged["name"],
                    heating_instructions=merged.get("heating_instructions"),
                    expiry_date=day_date + timedelta(days=3),
                    kbzhu=merged["kbzhu_per_serving"],
                )
                self.session.add(container)
                await self.session.flush()
                self.session.add(Meal(
                    day_id=day_plan.id,
                    container_id=container.id,
                    meal_type=meal_payload["meal_type"],
                    status="planned",
                    kbzhu_actual=merged["kbzhu_per_serving"],
                ))
                self._agg_shopping(shopping_agg, merged)

        await self._create_shopping_list(user_id, plan.id, week_start, shopping_agg)
        await self.session.commit()
        await self.session.refresh(plan)
        return plan

    def _merge_recipes(self, recipes: list[dict], meal_type: str, targets: dict) -> dict:
        share = {"breakfast": 0.25, "lunch": 0.30, "snack": 0.15, "dinner": 0.30}.get(meal_type, 0.25)
        target_kcal = targets["kcal"] * share
        base_kcal = sum(r["kbzhu_per_serving"].get("kcal", 0) for r in recipes) or 1
        scale = max(0.5, min(target_kcal / base_kcal, 3.0))
        kbzhu = {"kcal": 0, "protein": 0, "fat": 0, "carbs": 0}
        ingredients = []
        tags = []
        for recipe in recipes:
            tags.extend(recipe.get("tags", []))
            for key in kbzhu:
                kbzhu[key] += recipe["kbzhu_per_serving"].get(key, 0) * scale
            for ingredient in recipe.get("ingredients", []):
                ingredients.append({
                    "name": ingredient["name"],
                    "quantity": ingredient.get("quantity", 0) * scale,
                    "unit": ingredient.get("unit", "g"),
                })
        return {
            "name": " + ".join(r["name"] for r in recipes),
            "kbzhu_per_serving": {key: round(value) for key, value in kbzhu.items()},
            "heating_instructions": next((r.get("heating_instructions") for r in recipes if r.get("heating_instructions")), None),
            "ingredients": ingredients,
            "tags": tags,
        }

    def _agg_shopping(self, agg: dict, recipe: dict) -> None:
        category_map = {
            "chicken": "Мясо и птица",
            "beef": "Мясо и птица",
            "fish": "Рыба",
            "dairy": "Молочные продукты",
            "eggs": "Молочные продукты",
            "grain": "Крупы",
            "vegetables": "Овощи",
        }
        tags = recipe.get("tags", [])
        category = next((category_map[tag] for tag in tags if tag in category_map), "Прочее")
        for ingredient in recipe.get("ingredients", []):
            key = ingredient["name"]
            if key not in agg:
                agg[key] = {"quantity": 0.0, "unit": ingredient.get("unit", "g"), "category": category}
            agg[key]["quantity"] += ingredient.get("quantity", 0)

    async def _create_shopping_list(self, user_id: int, plan_id: int, week_start: date, agg: dict) -> None:
        shopping_list = ShoppingList(user_id=user_id, plan_id=plan_id, week_start=week_start)
        self.session.add(shopping_list)
        await self.session.flush()
        priorities = {"Мясо и птица": 1, "Рыба": 1, "Крупы": 2, "Молочные продукты": 3, "Овощи": 4, "Прочее": 5}
        for name, item in agg.items():
            self.session.add(ShoppingItem(
                shopping_list_id=shopping_list.id,
                name=name,
                quantity=f"{round(item['quantity'])} {item['unit']}",
                unit=item["unit"],
                category=item["category"],
                priority=priorities.get(item["category"], 5),
            ))

    @staticmethod
    def _meal_order(meal_type: str) -> int:
        return {name: index for index, (name, _) in enumerate(MEAL_SCHEDULE)}.get(meal_type, 99)

    @staticmethod
    def _as_list(value: Any) -> list:
        return value if isinstance(value, list) else []
