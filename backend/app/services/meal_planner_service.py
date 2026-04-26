"""
Meal-planner service — rule-based MVP generator.

Logic:
  1. Load user profile → compute КБЖУ targets (nutri_service)
  2. Select recipes from DB that fit meal_type + kcal target
  3. Assign containers (labels 1А..3Б)
  4. Build ShoppingList from aggregated ingredients
  5. Persist MealPlan, DayPlans, Meals, Containers, ShoppingList
"""
from __future__ import annotations

import json
import random
import re
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.models.plan import MealPlan, DayPlan, Meal
from app.models.container import Container
from app.models.shopping import ShoppingList, ShoppingItem
from app.models.profile import Profile
from app.services.nutri_service import calculate_targets, Goal, ActivityLevel, NutriTarget

# --- helpers -----------------------------------------------------------------

JSON_RECIPES_PATHS = [
    Path(__file__).parents[2] / "data" / "recipes" / "basic_recipes.json",
    Path(__file__).parents[3] / "data" / "recipes" / "basic_recipes.json",
]

MARKDOWN_RECIPE_PATHS = [
    *Path("/app/culinary").glob("*/kbzhuy_recipes_structured (1).md"),
    *[
        match
        for parent in Path(__file__).parents
        for match in (parent / "data" / "culinary").glob("*/kbzhuy_recipes_structured (1).md")
    ],
    Path("/app/culinary/Рецепты - читаемая база/kbzhuy_recipes_structured (1).md"),
    *[
        parent / "Кулинария" / "Рецепты - читаемая база" / "kbzhuy_recipes_structured (1).md"
        for parent in Path(__file__).parents
    ],
]

_RECIPES: list[dict] | None = None
_RECIPES_BY_NAME: dict[str, dict] | None = None


def _load_recipes() -> list[dict]:
    global _RECIPES
    if _RECIPES is None:
        markdown_path = next((path for path in MARKDOWN_RECIPE_PATHS if path.exists()), None)
        if markdown_path:
            _RECIPES = _load_markdown_recipes(markdown_path)
            if _RECIPES:
                return _RECIPES

        json_path = next((path for path in JSON_RECIPES_PATHS if path.exists()), None)
        if not json_path:
            raise FileNotFoundError("Recipe database not found")
        _RECIPES = json.loads(json_path.read_text(encoding="utf-8"))
    return _RECIPES


def _recipe_by_name(name: str | None) -> dict | None:
    global _RECIPES_BY_NAME
    if not name:
        return None
    if _RECIPES_BY_NAME is None:
        _RECIPES_BY_NAME = {recipe["name"].casefold(): recipe for recipe in _load_recipes()}
    return _RECIPES_BY_NAME.get(name.casefold())


def _load_markdown_recipes(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    sections = re.split(r"(?m)^##\s+", text)
    recipes: list[dict] = []
    current_category = ""
    next_id = 1

    for raw in sections:
        raw = raw.strip()
        if not raw:
            continue
        if raw.startswith("#"):
            category_match = re.findall(r"(?m)^#\s+(.+)$", raw)
            if category_match:
                current_category = category_match[-1].strip()
            continue

        title, _, body = raw.partition("\n")
        title = title.strip()
        if not title or title.startswith("#"):
            continue

        tags = _extract_tags(body)
        meal_types = _meal_types_from_text(" ".join(tags))
        if not meal_types and current_category:
            meal_types = _meal_types_from_text(current_category)
        if not meal_types:
            meal_types = ["lunch", "dinner"]

        total_minutes = _extract_int(r"Общее:\s*(\d+)\s*мин", body, default=30)
        active_minutes = _extract_int(r"Активное:\s*(\d+)\s*мин", body, default=min(total_minutes, 20))
        output_g = _extract_float(r"Выход:\s*~?([\d.,]+)\s*г", body, default=400)
        portions = max(1, _extract_int(r"Порции:\s*(\d+)", body, default=2))
        per100 = _extract_kbzhu_per_100g(body)
        if output_g <= 0 or per100.get("kcal", 0) <= 0:
            continue
        serving_grams = round(output_g / portions)
        scale = serving_grams / 100
        kbzhu = {key: round(value * scale) for key, value in per100.items()}

        ingredients = _extract_ingredients(body)
        storage = _extract_section_text(body, "Хранение")
        steps = _extract_steps(body)

        recipes.append({
            "id": next_id,
            "name": title,
            "meal_types": meal_types,
            "prep_time_minutes": active_minutes,
            "cook_time_minutes": max(total_minutes - active_minutes, 0),
            "servings": portions,
            "serving_grams": serving_grams,
            "kbzhu_per_serving": kbzhu,
            "storage_instructions": storage or "Хранить в холодильнике по готовности блюда.",
            "heating_instructions": "Разогреть по необходимости.",
            "tags": [*tags, *meal_types],
            "ingredients": ingredients,
            "steps": steps,
        })
        next_id += 1

    return recipes


def _extract_tags(body: str) -> list[str]:
    match = re.search(r"\*\*Теги:\*\*\s*(.+)", body)
    if not match:
        return []
    return [tag.strip().casefold() for tag in match.group(1).split(",") if tag.strip()]


def _meal_types_from_text(value: str) -> list[str]:
    value = value.casefold()
    meal_types = []
    if "завтрак" in value:
        meal_types.append("breakfast")
    if any(word in value for word in ("обед", "ужин", "основн", "горяч")):
        meal_types.extend(["lunch", "dinner"])
    if any(word in value for word in ("перекус", "десерт", "закуск")):
        meal_types.append("snack")
    return list(dict.fromkeys(meal_types))


def _extract_int(pattern: str, body: str, default: int) -> int:
    match = re.search(pattern, body, flags=re.I)
    return int(match.group(1)) if match else default


def _extract_float(pattern: str, body: str, default: float) -> float:
    match = re.search(pattern, body, flags=re.I)
    return float(match.group(1).replace(",", ".")) if match else default


def _parse_quantity_value(raw_quantity: str) -> float:
    value = raw_quantity.strip().replace(",", ".")
    if "/" in value:
        parts = value.split("/", 1)
        try:
            numerator = float(parts[0])
            denominator = float(parts[1])
            if denominator:
                return numerator / denominator
        except ValueError:
            return 1.0
    try:
        return float(value)
    except ValueError:
        return 1.0


def _extract_kbzhu_per_100g(body: str) -> dict:
    match = re.search(
        r"КБЖУ на 100 г:\s*([\d.,]+)\s*ккал\s*/\s*Б\s*([\d.,]+)\s*г\s*/\s*Ж\s*([\d.,]+)\s*г\s*/\s*У\s*([\d.,]+)\s*г",
        body,
        flags=re.I,
    )
    if not match:
        return {"kcal": 150, "protein": 8, "fat": 6, "carbs": 15}
    kcal, protein, fat, carbs = (float(item.replace(",", ".")) for item in match.groups())
    return {"kcal": kcal, "protein": protein, "fat": fat, "carbs": carbs}


def _extract_section_text(body: str, title: str) -> str | None:
    match = re.search(rf"\*\*{re.escape(title)}:\*\*\s*(.*?)(?=\n\*\*|\n---|\Z)", body, flags=re.S)
    if not match:
        return None
    lines = [re.sub(r"^\s*[-\d.]+\s*", "", line).strip() for line in match.group(1).splitlines()]
    return " ".join(line for line in lines if line)


def _extract_steps(body: str) -> list[dict]:
    recipe_text = _extract_section_text(body, "Рецепт") or ""
    steps = []
    for index, line in enumerate(re.split(r"(?=\d+\.\s)", recipe_text), start=1):
        clean = re.sub(r"^\d+\.\s*", "", line).strip()
        if clean:
            steps.append({"order": index, "text": clean, "time_min": 5})
    return steps


def _extract_ingredients(body: str) -> list[dict]:
    match = re.search(r"\*\*Ингредиенты:\*\*\s*(.*?)(?=\n\*\*Рецепт:\*\*|\n---|\Z)", body, flags=re.S)
    if not match:
        return []
    ingredients = []
    for line in match.group(1).splitlines():
        clean = re.sub(r"^\s*-\s*", "", line).strip()
        clean = clean.strip("* ")
        if not clean or clean.endswith(":"):
            continue
        amount = re.search(r"(.+?)\s+([\d.,/]+)\s*(г|гр|мл|шт|головк[аи]?|зубчик[а-я]*)\b", clean, flags=re.I)
        if not amount:
            amount = re.search(r"(.+?)\s+([\d.,/]+)\s*(кг|л|стакан[а-я]*|ст\.?\s*л\.?|ч\.?\s*л\.?|упак[а-я]*|пачк[а-я]*)\b", clean, flags=re.I)
        if amount:
            name = amount.group(1).strip()
            quantity = _parse_quantity_value(amount.group(2))
            unit = amount.group(3)
        else:
            name, quantity, unit = clean, 1.0, "шт"
        ingredients.append({"name": name, "quantity": quantity, "unit": unit})
    return ingredients


def _recipes_for_meal(meal_type: str) -> list[dict]:
    return [r for r in _load_recipes() if meal_type in r["meal_types"]]


def _valid_recipe(recipe: dict) -> bool:
    kbzhu = recipe.get("kbzhu_per_serving") or {}
    return all(kbzhu.get(key, 0) > 0 for key in ("kcal", "protein", "fat", "carbs"))


def recipe_details_by_name(name: str | None) -> dict | None:
    recipe = _recipe_by_name(name)
    if not recipe:
        return None
    return {
        "serving_grams": recipe.get("serving_grams"),
        "ingredients": recipe.get("ingredients", []),
        "steps": recipe.get("steps", []),
    }


def _random_tiebreak() -> float:
    return random.random() * 0.05


# Container label matrix: row = week-slot (1..3), col = А/Б/В/Г
_LABELS = [f"{row}{col}" for row in range(1, 4) for col in "АБВГ"]


MEAL_SCHEDULE = [
    ("breakfast", "08:00"),
    ("lunch",     "13:00"),
    ("snack",     "16:00"),
    ("dinner",    "19:00"),
]

MEAL_LABEL_TO_TYPE = {
    "завтрак": "breakfast",
    "обед": "lunch",
    "перекус": "snack",
    "ужин": "dinner",
}

MEAL_ID_TO_TYPE = {
    "meal_1": "breakfast",
    "meal_2": "lunch",
    "meal_3": "snack",
    "meal_4": "dinner",
}

SNACK_INCLUDE_TAGS = {
    "snack",
    "\u0434\u0435\u0441\u0435\u0440\u0442",
    "dessert",
    "\u0441\u0430\u043b\u0430\u0442",
    "salad",
    "\u043d\u0430\u043f\u0438\u0442\u043e\u043a",
    "drink",
    "\u0441\u043c\u0443\u0437\u0438",
    "smoothie",
    "\u0439\u043e\u0433\u0443\u0440\u0442",
    "yogurt",
    "\u0442\u0432\u043e\u0440\u043e\u0433",
    "fruit",
    "\u0444\u0440\u0443\u043a\u0442",
    "\u043f\u0435\u0440\u0435\u043a\u0443\u0441",
    "\u0437\u0430\u043a\u0443\u0441\u043a\u0430",
    "\u0432\u044b\u043f\u0435\u0447\u043a\u0430",
}

SNACK_EXCLUDE_TAGS = {
    "lunch",
    "dinner",
    "\u043e\u0431\u0435\u0434",
    "\u0443\u0436\u0438\u043d",
    "\u043e\u0441\u043d\u043e\u0432\u043d\u043e\u0435",
    "\u0433\u043e\u0440\u044f\u0447\u0435\u0435",
    "\u0441\u0443\u043f",
    "main",
    "main_course",
}

SNACK_INCLUDE_KEYWORDS = (
    "\u0441\u0430\u043b\u0430\u0442",
    "\u0434\u0435\u0441\u0435\u0440\u0442",
    "\u043d\u0430\u043f\u0438\u0442",
    "\u0441\u043c\u0443\u0437\u0438",
    "\u0439\u043e\u0433\u0443\u0440",
    "\u0442\u0432\u043e\u0440",
    "\u0444\u0440\u0443\u043a\u0442",
    "\u044f\u0431\u043b\u043e\u043a",
    "\u0433\u0440\u0443\u0448",
    "\u044f\u0433\u043e\u0434",
    "\u0431\u0430\u043d\u0430\u043d",
    "\u043a\u043e\u043a\u0442\u0435\u0439\u043b",
    "\u043c\u0443\u0441\u0441",
    "\u043f\u0443\u0434\u0438\u043d\u0433",
    "\u0436\u0435\u043b\u0435",
    "\u0441\u044b\u0440\u043d\u0438\u043a",
    "\u043e\u043b\u0430\u0434",
    "\u043f\u0435\u0447\u0435\u043d\u044c\u0435",
    "\u0431\u0430\u0442\u043e\u043d\u0447\u0438\u043a",
    "\u0437\u0430\u043a\u0443\u0441\u043a\u0430",
    "\u0433\u0430\u043b\u0435\u0442",
    "\u0441\u0443\u0444\u043b\u0435",
    "\u043f\u0438\u0440\u043e\u0436",
    "\u043c\u0430\u0444\u0444\u0438\u043d",
    "\u043a\u0435\u043a\u0441",
    "\u043a\u0440\u0430\u043c\u0431\u043b",
    "\u043f\u0430\u0440\u0444\u0435",
    "\u0442\u0430\u0440\u0442",
    "\u043a\u043b\u0430\u0444\u0444\u0443\u0442\u0438",
    "\u0430\u0434\u0436\u0438\u043a",
    "\u043a\u0440\u043e\u043a\u0435\u0442",
)

SNACK_EXCLUDE_KEYWORDS = (
    "\u0441\u0443\u043f",
    "\u043b\u0430\u043f\u0448",
    "\u043f\u0430\u0441\u0442\u0430",
    "\u043a\u043e\u0442\u043b\u0435\u0442",
    "\u0442\u0435\u0444\u0442\u0435\u043b",
    "\u0448\u0430\u0448\u043b\u044b\u043a",
    "\u043f\u044e\u0440\u0435",
    "\u0436\u0430\u0440\u0435\u043d",
    "\u0437\u0430\u043f\u0435\u043a\u0430\u043d",
    "\u0440\u0430\u0433\u0443",
    "\u043f\u043b\u043e\u0432",
    "\u0441\u0442\u0435\u0439\u043a",
    "\u0444\u0438\u043b\u0435",
    "\u043c\u0438\u0434\u0438\u0438",
    "\u0440\u044b\u0431\u043d",
    "\u043a\u0443\u0440\u0438\u043d",
    "\u0441\u0432\u0438\u043d\u0438\u043d",
    "\u0433\u043e\u0432\u044f\u0436",
    "\u0444\u0430\u0440\u0448",
    "\u043e\u043a\u043e\u0440\u043e\u043a",
    "\u043a\u0430\u043b\u044c\u043c\u0430\u0440",
    "\u043a\u0440\u0435\u0432\u0435\u0442",
    "\u043c\u044f\u0441",
    "\u043f\u0442\u0438\u0446",
    "\u043a\u0443\u0440\u043d\u0438\u043a",
    "\u043f\u0438\u0440\u043e\u0433 \u0441 \u0441\u044b\u0440",
    "\u043f\u0438\u0440\u043e\u0433 \u0441 \u043c\u044f\u0441",
    "\u0442\u043e\u0440\u0442 \u0441 \u0444\u0430\u0440\u0448",
    "\u043e\u0441\u043d\u043e\u0432",
)


# --- service -----------------------------------------------------------------

class MealPlannerService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate(self, user_id: int, week_start: date) -> MealPlan:
        """
        Generate a 7-day meal plan for the user.
        Uses the user's profile to calculate targets, then fills meals
        from the local recipe JSON using a simple best-fit algorithm.
        """
        # Load profile
        result = await self.session.execute(
            select(Profile).where(Profile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            raise ValueError(f"Profile not found for user_id={user_id}")

        targets = calculate_targets(
            weight_kg=profile.weight_kg or 80.0,
            height_cm=profile.height_cm or 175.0,
            age=profile.age or 30,
            sex=profile.sex or "male",
            activity=ActivityLevel(profile.activity_level or "moderate"),
            goal=Goal(profile.goal or "maintain"),
        )

        week_end = week_start + timedelta(days=6)
        await self._deactivate_overlapping_plans(user_id, week_start, week_end)
        plan = MealPlan(
            user_id=user_id,
            period_start=week_start,
            period_end=week_end,
            daily_targets={"kcal": targets.kcal, "protein": targets.protein,
                           "fat": targets.fat, "carbs": targets.carbs},
            status="active",
        )
        self.session.add(plan)
        await self.session.flush()

        containers_created: list[Container] = []
        shopping_agg: dict[str, dict] = {}  # name → {qty, unit, category}
        label_idx = 0
        meal_schedule = self._profile_meal_schedule(profile)
        used_week_names: dict[str, int] = {}

        for day_offset in range(7):
            day_date = week_start + timedelta(days=day_offset)
            day_plan = DayPlan(
                plan_id=plan.id,
                date=day_date,
            )
            self.session.add(day_plan)
            await self.session.flush()

            day_meals = self._compose_day_meals(meal_schedule, targets, profile, used_week_names)
            for scheduled_meal, recipe in day_meals:
                # Container label (cycle through 1А..3Б)
                label = _LABELS[label_idx % len(_LABELS)]
                label_idx += 1

                container = Container(
                    user_id=user_id,
                    label=label,
                    plan_id=plan.id,
                    status="filled",
                    contents_description=recipe["name"],
                    heating_instructions=recipe.get("heating_instructions"),
                    expiry_date=day_date + timedelta(days=3),
                    kbzhu=recipe["kbzhu_per_serving"],
                )
                self.session.add(container)
                await self.session.flush()
                containers_created.append(container)

                meal = Meal(
                    day_id=day_plan.id,
                    container_id=container.id,
                    meal_type=scheduled_meal["id"],
                    status="planned",
                    kbzhu_actual=recipe["kbzhu_per_serving"],
                )
                self.session.add(meal)

        await self._sync_shopping_list(plan.id, user_id, week_start)

        await self.session.commit()
        await self.session.refresh(plan)
        return plan

    async def _deactivate_overlapping_plans(self, user_id: int, week_start: date, week_end: date) -> None:
        await self.session.execute(
            update(MealPlan)
            .where(MealPlan.user_id == user_id)
            .where(MealPlan.status == "active")
            .where(MealPlan.period_start <= week_end)
            .where(MealPlan.period_end >= week_start)
            .values(status="cancelled")
        )

    async def replace_meal(self, user_id: int, meal_id: int) -> Meal:
        result = await self.session.execute(
            select(Meal)
            .join(DayPlan, Meal.day_id == DayPlan.id)
            .join(MealPlan, DayPlan.plan_id == MealPlan.id)
            .where(Meal.id == meal_id)
            .where(MealPlan.user_id == user_id)
            .options(
                selectinload(Meal.container),
                selectinload(Meal.day).selectinload(DayPlan.plan),
                selectinload(Meal.day).selectinload(DayPlan.meals).selectinload(Meal.container),
            )
        )
        meal = result.scalar_one_or_none()
        if meal is None:
            raise ValueError("Meal not found")

        profile_result = await self.session.execute(select(Profile).where(Profile.user_id == user_id))
        profile = profile_result.scalar_one_or_none()
        if profile is None:
            raise ValueError(f"Profile not found for user_id={user_id}")

        schedule = self._profile_meal_schedule(profile)
        schedule_meal = next((item for item in schedule if item["id"] == meal.meal_type), {"id": meal.meal_type})
        recipe_type = self._recipe_type_for_meal(schedule_meal)
        raw_targets = meal.day.plan.daily_targets
        targets = NutriTarget(
            kcal=raw_targets["kcal"],
            protein=raw_targets["protein"],
            fat=raw_targets["fat"],
            carbs=raw_targets["carbs"],
            bmr=0,
            tdee=0,
        )
        current_name = meal.container.contents_description if meal.container else None
        candidates = self._filtered_recipes(profile, recipe_type)
        excluded = {current_name.casefold()} if current_name else set()
        candidates = [recipe for recipe in candidates if recipe["name"].casefold() not in excluded]
        if not candidates:
            candidates = [recipe for recipe in _load_recipes() if _valid_recipe(recipe) and recipe["name"].casefold() not in excluded]
        recipe = self._pick_replacement_recipe(meal, candidates, targets)
        if recipe is None:
            raise ValueError("Recipe not found")

        container = meal.container
        if container is None:
            container = Container(
                user_id=user_id,
                label="R",
                plan_id=meal.day.plan_id,
                status="filled",
                expiry_date=meal.day.date + timedelta(days=3),
            )
            self.session.add(container)
            await self.session.flush()
            meal.container_id = container.id

        container.contents_description = recipe["name"]
        container.heating_instructions = recipe.get("heating_instructions")
        container.kbzhu = recipe["kbzhu_per_serving"]
        meal.kbzhu_actual = recipe["kbzhu_per_serving"]
        meal.status = "planned"

        await self.session.flush()
        await self._sync_shopping_list(meal.day.plan_id, user_id, meal.day.plan.period_start)
        await self.session.commit()
        await self.session.refresh(meal)
        return meal

    async def rebuild_day(self, user_id: int, day_id: int) -> DayPlan:
        result = await self.session.execute(
            select(DayPlan)
            .join(MealPlan, DayPlan.plan_id == MealPlan.id)
            .where(DayPlan.id == day_id)
            .where(MealPlan.user_id == user_id)
            .options(
                selectinload(DayPlan.plan).selectinload(MealPlan.days).selectinload(DayPlan.meals).selectinload(Meal.container),
                selectinload(DayPlan.meals).selectinload(Meal.container),
            )
        )
        day = result.scalar_one_or_none()
        if day is None:
            raise ValueError("Day not found")

        profile_result = await self.session.execute(select(Profile).where(Profile.user_id == user_id))
        profile = profile_result.scalar_one_or_none()
        if profile is None:
            raise ValueError(f"Profile not found for user_id={user_id}")

        raw_targets = day.plan.daily_targets
        targets = NutriTarget(
            kcal=raw_targets["kcal"],
            protein=raw_targets["protein"],
            fat=raw_targets["fat"],
            carbs=raw_targets["carbs"],
            bmr=0,
            tdee=0,
        )

        current_names = {
            meal.container.contents_description.casefold()
            for meal in day.meals
            if meal.container and meal.container.contents_description
        }
        used_week_names: dict[str, int] = {}
        for plan_day in day.plan.days:
            if plan_day.id == day.id:
                continue
            for meal in plan_day.meals:
                if meal.container and meal.container.contents_description:
                    name = meal.container.contents_description
                    used_week_names[name] = used_week_names.get(name, 0) + 1

        meal_schedule = self._profile_meal_schedule(profile)
        day_meals = self._compose_day_meals(
            meal_schedule,
            targets,
            profile,
            used_week_names,
            exclude_names=current_names,
            diversity_boost=True,
        )
        if not day_meals:
            raise ValueError("Recipes not found")

        existing_meals = sorted(
            day.meals,
            key=lambda meal: next((index for index, item in enumerate(meal_schedule) if item["id"] == meal.meal_type), 999),
        )
        for index, (scheduled_meal, recipe) in enumerate(day_meals):
            if index < len(existing_meals):
                meal = existing_meals[index]
                container = meal.container
            else:
                meal = Meal(day_id=day.id, meal_type=scheduled_meal["id"], status="planned")
                self.session.add(meal)
                await self.session.flush()
                container = None

            if container is None:
                container = Container(
                    user_id=user_id,
                    label=f"D{index + 1}",
                    plan_id=day.plan_id,
                    status="filled",
                    expiry_date=day.date + timedelta(days=3),
                )
                self.session.add(container)
                await self.session.flush()
                meal.container_id = container.id

            meal.meal_type = scheduled_meal["id"]
            meal.status = "planned"
            meal.kbzhu_actual = recipe["kbzhu_per_serving"]
            container.contents_description = recipe["name"]
            container.heating_instructions = recipe.get("heating_instructions")
            container.kbzhu = recipe["kbzhu_per_serving"]

        for meal in existing_meals[len(day_meals):]:
            if meal.container:
                await self.session.delete(meal.container)
            await self.session.delete(meal)

        await self.session.flush()
        await self._sync_shopping_list(day.plan_id, user_id, day.plan.period_start)
        await self.session.commit()
        await self.session.refresh(day)
        return day

    def _profile_meal_schedule(self, profile: Profile) -> list[dict]:
        raw_meals = (profile.eating_schedule or {}).get("meals")
        if isinstance(raw_meals, list) and raw_meals:
            return [
                {
                    "id": str(meal.get("id") or f"meal_{index + 1}"),
                    "name": str(meal.get("name") or f"Прием {index + 1}"),
                    "time": str(meal.get("time") or "12:00"),
                }
                for index, meal in enumerate(raw_meals)
                if isinstance(meal, dict)
            ]
        return [
            {"id": meal_type, "name": self._default_meal_name(meal_type), "time": time}
            for meal_type, time in MEAL_SCHEDULE
        ]

    @staticmethod
    def _default_meal_name(meal_type: str) -> str:
        return {
            "breakfast": "Завтрак",
            "lunch": "Обед",
            "snack": "Перекус",
            "dinner": "Ужин",
        }.get(meal_type, "Прием пищи")

    def _recipe_type_for_meal(self, meal: dict) -> str:
        meal_id = str(meal.get("id") or "").casefold()
        if meal_id in MEAL_ID_TO_TYPE:
            mapped = MEAL_ID_TO_TYPE[meal_id]
            return "breakfast" if mapped == "breakfast" else "snack" if mapped == "snack" else "main"
        name = str(meal.get("name") or "").casefold()
        if "завтрак" in name:
            return "breakfast"
        if "перекус" in name or "snack" in meal_id:
            return "snack"
        if "обед" in name or "ужин" in name:
            return "main"
        if "snack" in meal_id or "перекус" in meal_id:
            return "snack"
        return "main"

    def _filtered_recipes(self, profile: Profile, meal_type: str) -> list[dict]:
        avoid = [*(profile.allergies or []), *(profile.disliked_foods or [])]
        equipment = {str(item).casefold() for item in (profile.kitchen_equipment or [])}
        max_minutes = None
        if isinstance(profile.cooking_time_budget, dict):
            raw_minutes = profile.cooking_time_budget.get("minutes")
            if isinstance(raw_minutes, (int, float)) and raw_minutes > 0:
                max_minutes = raw_minutes

        recipes = []
        all_recipes = _load_recipes()
        if meal_type == "breakfast":
            source_recipes = [recipe for recipe in all_recipes if "breakfast" in recipe.get("meal_types", [])]
        elif meal_type == "main":
            source_recipes = [recipe for recipe in all_recipes if "breakfast" not in recipe.get("meal_types", [])]
        elif meal_type == "snack":
            source_recipes = [
                recipe for recipe in all_recipes
                if self._is_light_snack(recipe)
            ]
        else:
            source_recipes = _recipes_for_meal(meal_type)

        for recipe in source_recipes:
            if not _valid_recipe(recipe):
                continue
            haystack = json.dumps(recipe, ensure_ascii=False).casefold()
            if any(str(term).casefold() in haystack for term in avoid if term):
                continue
            tags = {str(tag).casefold() for tag in recipe.get("tags", [])}
            if "oven" in tags and equipment and "духовка" not in equipment:
                continue
            if "grill" in tags and equipment and "гриль" not in equipment:
                continue
            total_minutes = recipe.get("prep_time_minutes", 0) + recipe.get("cook_time_minutes", 0)
            if max_minutes and total_minutes > max_minutes * 1.5 and "batch" not in tags:
                continue
            recipes.append(recipe)
        return recipes

    @staticmethod
    def _is_light_snack(recipe: dict) -> bool:
        tags = {str(tag).casefold() for tag in recipe.get("tags", [])}
        meal_types = {str(tag).casefold() for tag in recipe.get("meal_types", [])}
        name = str(recipe.get("name") or "").casefold()
        haystack = " ".join([name, *tags, *meal_types])
        kbzhu = recipe.get("kbzhu_per_serving") or {}
        kcal = float(kbzhu.get("kcal", 0) or 0)

        if tags & SNACK_EXCLUDE_TAGS:
            return False
        if any(keyword in haystack for keyword in SNACK_EXCLUDE_KEYWORDS):
            return False
        if "lunch" in meal_types or "dinner" in meal_types:
            return False
        if "breakfast" in meal_types and not (
            "\u0434\u0435\u0441\u0435\u0440\u0442" in haystack
            or "\u0432\u044b\u043f\u0435\u0447\u043a\u0430" in tags
            or "\u0441\u043c\u0443\u0437\u0438" in haystack
            or "\u0439\u043e\u0433\u0443\u0440" in haystack
            or "\u0442\u0432\u043e\u0440" in haystack
            or "\u0444\u0440\u0443\u043a\u0442" in haystack
            or "\u044f\u0433\u043e\u0434" in haystack
        ):
            return False

        include_match = bool(tags & SNACK_INCLUDE_TAGS) or any(keyword in haystack for keyword in SNACK_INCLUDE_KEYWORDS)
        if not include_match:
            return False
        if kcal < 30:
            return False

        if "\u043d\u0430\u043f\u0438\u0442" in haystack or "smoothie" in haystack or "\u0441\u043c\u0443\u0437\u0438" in haystack:
            return kcal <= 260
        if "\u0444\u0440\u0443\u043a\u0442" in haystack or "\u044f\u0431\u043b\u043e\u043a" in haystack or "\u0433\u0440\u0443\u0448" in haystack or "\u044f\u0433\u043e\u0434" in haystack or "\u0431\u0430\u043d\u0430\u043d" in haystack:
            return kcal <= 260
        if "\u0441\u0430\u043b\u0430\u0442" in haystack or "salad" in haystack:
            return kcal <= 320
        if "\u0434\u0435\u0441\u0435\u0440\u0442" in haystack or "\u043f\u0430\u0440\u0444\u0435" in haystack or "\u0441\u0443\u0444\u043b\u0435" in haystack or "\u043f\u0438\u0440\u043e\u0436" in haystack:
            return kcal <= 420
        if "\u0432\u044b\u043f\u0435\u0447\u043a\u0430" in tags or "\u043c\u0430\u0444\u0444\u0438\u043d" in haystack or "\u043a\u0435\u043a\u0441" in haystack or "\u0433\u0430\u043b\u0435\u0442" in haystack or "\u043a\u043b\u0430\u0444\u0444\u0443\u0442\u0438" in haystack or "\u0442\u0430\u0440\u0442" in haystack:
            return kcal <= 420
        if "\u0437\u0430\u043a\u0443\u0441\u043a\u0430" in haystack or "\u043a\u0440\u043e\u043a\u0435\u0442" in haystack or "\u0430\u0434\u0436\u0438\u043a" in haystack:
            return kcal <= 280
        if kcal > 360:
            return False
        return True

    def _compose_day_meals(
        self,
        meal_schedule: list[dict],
        targets: NutriTarget,
        profile: Profile,
        used_week_names: dict[str, int],
        exclude_names: set[str] | None = None,
        diversity_boost: bool = False,
    ) -> list[tuple[dict, dict]]:
        if not meal_schedule:
            return []

        slots: list[tuple[dict, list[dict]]] = []
        meal_count = max(len(meal_schedule), 1)
        excluded = exclude_names or set()
        for scheduled_meal in meal_schedule:
            recipe_type = self._recipe_type_for_meal(scheduled_meal)
            candidates = self._filtered_recipes(profile, recipe_type)
            if excluded:
                filtered_candidates = [recipe for recipe in candidates if recipe["name"].casefold() not in excluded]
                if filtered_candidates:
                    candidates = filtered_candidates
            if not candidates:
                candidates = [recipe for recipe in _load_recipes() if _valid_recipe(recipe) and recipe["name"].casefold() not in excluded]
            meal_target_kcal = targets.kcal / meal_count
            candidates = self._diversified_candidates(candidates, meal_target_kcal, diversity_boost=diversity_boost)
            slots.append((scheduled_meal, candidates))

        beams: list[tuple[list[tuple[dict, dict]], dict, set[str], float]] = [
            ([], {"kcal": 0, "protein": 0, "fat": 0, "carbs": 0}, set(), 0.0)
        ]
        beam_width = 180

        for slot_index, (scheduled_meal, candidates) in enumerate(slots, start=1):
            next_beams: list[tuple[list[tuple[dict, dict]], dict, set[str], float]] = []
            partial_target = self._scaled_targets(targets, slot_index / meal_count)
            for selected, totals, names, _score in beams:
                for recipe in candidates:
                    name = recipe["name"]
                    kbzhu = recipe["kbzhu_per_serving"]
                    next_totals = self._add_kbzhu(totals, kbzhu)
                    next_names = {*names, name}
                    duplicate_penalty = 0.22 if name in names else 0
                    week_penalty = min(0.12 * used_week_names.get(name, 0), 0.48)
                    score = self._score_totals(next_totals, partial_target) + duplicate_penalty + week_penalty + _random_tiebreak()
                    next_beams.append((
                        [*selected, (scheduled_meal, self._recipe_payload(recipe))],
                        next_totals,
                        next_names,
                        score,
                    ))
            ranked_beams = sorted(next_beams, key=lambda item: item[3])
            head = ranked_beams[: min(48, len(ranked_beams))]
            tail = ranked_beams[min(48, len(ranked_beams)): min(260, len(ranked_beams))]
            tail_sample_size = min(len(tail), beam_width - len(head))
            sampled_tail = random.sample(tail, k=tail_sample_size) if tail_sample_size > 0 else []
            beams = [*head, *sampled_tail]

        if not beams:
            return []

        final_target = self._scaled_targets(targets, 1)
        finalists = sorted(
            beams,
            key=lambda item: self._score_totals(item[1], final_target) + item[3] * 0.05 + _random_tiebreak(),
        )[: min(12, len(beams))]
        best = random.choice(finalists[: max(3, min(8, len(finalists)))])
        for _scheduled_meal, recipe in best[0]:
            used_week_names[recipe["name"]] = used_week_names.get(recipe["name"], 0) + 1
        return best[0]

    def _pick_replacement_recipe(
        self,
        meal: Meal,
        candidates: list[dict],
        targets: NutriTarget,
    ) -> dict | None:
        candidates = [recipe for recipe in candidates if _valid_recipe(recipe)]
        if not candidates:
            return None

        day_totals_without = {"kcal": 0, "protein": 0, "fat": 0, "carbs": 0}
        for day_meal in meal.day.meals:
            if day_meal.id == meal.id:
                continue
            day_totals_without = self._add_kbzhu(day_totals_without, day_meal.kbzhu_actual or {})

        current_kbzhu = meal.kbzhu_actual or {}
        meal_count = max(len(meal.day.meals), 1)
        meal_target = self._scaled_targets(targets, 1 / meal_count)
        current_reference = current_kbzhu if all(current_kbzhu.get(key, 0) > 0 for key in ("kcal", "protein", "fat", "carbs")) else meal_target

        ranked = sorted(
            candidates,
            key=lambda recipe: (
                self._score_totals(
                    self._add_kbzhu(day_totals_without, recipe["kbzhu_per_serving"]),
                    self._scaled_targets(targets, 1),
                ),
                self._score_totals(recipe["kbzhu_per_serving"], current_reference),
                abs(recipe["kbzhu_per_serving"].get("kcal", 0) - current_reference.get("kcal", 0)),
                recipe["id"],
            ),
        )
        pool = ranked[: min(10, len(ranked))]
        return random.choice(pool)

    @staticmethod
    def _diversified_candidates(candidates: list[dict], meal_target_kcal: float, diversity_boost: bool = False) -> list[dict]:
        ranked = sorted(
            candidates,
            key=lambda recipe: (
                abs(recipe["kbzhu_per_serving"].get("kcal", 0) - meal_target_kcal),
                -recipe["kbzhu_per_serving"].get("protein", 0),
                recipe["id"],
            ),
        )[:140]
        if len(ranked) <= 24:
            random.shuffle(ranked)
            return ranked

        core_size = 12 if diversity_boost else 20
        sample_target = 48 if diversity_boost else 36
        core = ranked[:core_size]
        tail = ranked[core_size:]
        if diversity_boost and len(core) > 6:
            drop_count = min(6, len(core) // 2)
            core = core[drop_count:]
        sample_size = min(len(tail), sample_target)
        sampled_tail = random.sample(tail, k=sample_size) if sample_size else []
        mixed = [*core, *sampled_tail]
        random.shuffle(mixed)
        return mixed

    @staticmethod
    def _scaled_targets(targets: NutriTarget, share: float) -> dict:
        return {
            "kcal": targets.kcal * share,
            "protein": targets.protein * share,
            "fat": targets.fat * share,
            "carbs": targets.carbs * share,
        }

    @staticmethod
    def _add_kbzhu(left: dict, right: dict) -> dict:
        return {
            "kcal": left.get("kcal", 0) + right.get("kcal", 0),
            "protein": left.get("protein", 0) + right.get("protein", 0),
            "fat": left.get("fat", 0) + right.get("fat", 0),
            "carbs": left.get("carbs", 0) + right.get("carbs", 0),
        }

    @staticmethod
    def _score_totals(totals: dict, target: dict) -> float:
        weights = {"kcal": 2.2, "protein": 1.2, "fat": 1.0, "carbs": 1.0}
        return sum(
            weights[key] * abs(totals.get(key, 0) - target.get(key, 0)) / max(target.get(key, 0), 1)
            for key in weights
        )

    @staticmethod
    def _recipe_payload(recipe: dict) -> dict:
        return {
            "name": recipe["name"],
            "kbzhu_per_serving": recipe["kbzhu_per_serving"],
            "heating_instructions": recipe.get("heating_instructions"),
            "ingredients": recipe.get("ingredients", []),
            "tags": recipe.get("tags", []),
            "serving_grams": recipe.get("serving_grams"),
        }

    def _compose_meal(
        self,
        meal_type: str,
        targets: NutriTarget,
        profile: Profile | None = None,
        share: float | None = None,
        exclude_names: list[str | None] | None = None,
    ) -> dict | None:
        candidates = self._filtered_recipes(profile, meal_type) if profile else _recipes_for_meal(meal_type)
        excluded = {name.casefold() for name in (exclude_names or []) if name}
        if excluded:
            filtered = [recipe for recipe in candidates if recipe["name"].casefold() not in excluded]
            if filtered:
                candidates = filtered
        if not candidates:
            # Fallback: use any recipe from the database
            candidates = _load_recipes()
        if not candidates:
            return None

        share = share or {"breakfast": 0.25, "main": 0.30, "snack": 0.15}.get(meal_type, 0.25)
        target_kcal = targets.kcal * share
        selected = self._pick_recipe(candidates, target_kcal)
        return {
            "name": selected["name"],
            "kbzhu_per_serving": selected["kbzhu_per_serving"],
            "heating_instructions": selected.get("heating_instructions"),
            "ingredients": selected.get("ingredients", []),
            "tags": selected.get("tags", []),
            "serving_grams": selected.get("serving_grams"),
        }

    @staticmethod
    def _pick_recipe(candidates: list[dict], target_kcal: float) -> dict:
        sorted_candidates = sorted(
            candidates,
            key=lambda recipe: (
                abs(recipe["kbzhu_per_serving"].get("kcal", 0) - target_kcal),
                -recipe["kbzhu_per_serving"].get("protein", 0),
                recipe["id"],
            ),
        )
        pool = sorted_candidates[: min(8, len(sorted_candidates))]
        return random.choice(pool)

    @staticmethod
    def _solve_scales(combo: list[dict], meal_targets: dict) -> list[float]:
        """
        Find per-component scale factors so the combined macros
        match meal_targets.

        For 1 component: scale by kcal.
        For 2+ components:
          - Scale protein source to hit protein target
          - Scale carb source to hit carbs target
          - Don't normalize by kcal (macros > exact kcal)
        """
        n = len(combo)
        if n == 0:
            return []

        target_kcal = meal_targets["kcal"]

        if n == 1:
            base = combo[0]["kbzhu_per_serving"]["kcal"]
            return [target_kcal / base] if base > 0 else [1.0]

        # Classify components
        protein_idxs = []
        carb_idxs = []
        other_idxs = []
        for i, r in enumerate(combo):
            k = r["kbzhu_per_serving"]
            if k.get("kcal", 0) <= 0:
                other_idxs.append(i)
                continue
            p_pct = (k.get("protein", 0) * 4) / k["kcal"]
            c_pct = (k.get("carbs", 0) * 4) / k["kcal"]
            if p_pct > 0.3:
                protein_idxs.append(i)
            elif c_pct > 0.5:
                carb_idxs.append(i)
            else:
                other_idxs.append(i)

        # Start with uniform kcal scaling
        total_base_kcal = sum(r["kbzhu_per_serving"]["kcal"] for r in combo)
        if total_base_kcal <= 0:
            return [1.0] * n
        scales = [target_kcal / total_base_kcal] * n

        # Scale protein sources to hit protein target
        if protein_idxs:
            p_from_others = sum(
                combo[i]["kbzhu_per_serving"]["protein"] * scales[i]
                for i in carb_idxs + other_idxs
            )
            base_p = sum(combo[i]["kbzhu_per_serving"]["protein"] for i in protein_idxs)
            needed_p = meal_targets["protein"] - p_from_others
            if base_p > 0 and needed_p > 0:
                for i in protein_idxs:
                    scales[i] = needed_p / base_p

        # Scale carb sources to hit carbs target
        if carb_idxs:
            c_from_others = sum(
                combo[i]["kbzhu_per_serving"]["carbs"] * scales[i]
                for i in protein_idxs + other_idxs
            )
            base_c = sum(combo[i]["kbzhu_per_serving"]["carbs"] for i in carb_idxs)
            needed_c = meal_targets["carbs"] - c_from_others
            if base_c > 0 and needed_c > 0:
                for i in carb_idxs:
                    scales[i] = needed_c / base_c

        # Scale "other" (vegs, etc.) by remaining kcal
        kcal_used = sum(
            combo[i]["kbzhu_per_serving"]["kcal"] * scales[i]
            for i in protein_idxs + carb_idxs
        )
        remaining_kcal = max(target_kcal - kcal_used, 0)
        other_base_kcal = sum(combo[i]["kbzhu_per_serving"]["kcal"] for i in other_idxs)
        if other_idxs and other_base_kcal > 0:
            for i in other_idxs:
                scales[i] = remaining_kcal / other_base_kcal

        # Clamp to reasonable portion range (0.5x - 4x)
        scales = [max(0.5, min(s, 4.0)) for s in scales]
        return scales

    @staticmethod
    def _normalize_unit(unit: str | None) -> str:
        raw = re.sub(r"\s+", " ", (unit or "шт").strip().casefold())
        aliases = {
            "г": "г",
            "гр": "г",
            "грамм": "г",
            "грамма": "г",
            "граммов": "г",
            "кг": "г",
            "килограмм": "г",
            "килограмма": "г",
            "мл": "мл",
            "миллилитр": "мл",
            "миллилитра": "мл",
            "л": "мл",
            "литр": "мл",
            "литра": "мл",
            "стакан": "мл",
            "стакана": "мл",
            "стаканов": "мл",
            "ст. л.": "мл",
            "ст.л.": "мл",
            "ст л": "мл",
            "столовая ложка": "мл",
            "столовые ложки": "мл",
            "ч. л.": "мл",
            "ч.л.": "мл",
            "ч л": "мл",
            "чайная ложка": "мл",
            "чайные ложки": "мл",
            "упак": "шт",
            "упаковка": "шт",
            "упаковки": "шт",
            "пачка": "шт",
            "пачки": "шт",
            "банка": "шт",
            "банки": "шт",
            "бутылка": "шт",
            "бутылки": "шт",
            "шт": "шт",
            "штука": "шт",
            "штуки": "шт",
            "штук": "шт",
            "зубчик": "шт",
            "зубчика": "шт",
            "зубчиков": "шт",
            "пучок": "пучок",
            "пучка": "пучок",
            "пучков": "пучок",
        }
        if raw.startswith("головк"):
            return "шт"
        return aliases.get(raw, raw or "шт")

    @staticmethod
    def _normalize_ingredient_name(name: str) -> str:
        clean = name.strip().casefold().replace("«", '"').replace("»", '"')
        clean = clean.replace("ё", "е")
        clean = re.sub(r"[\(\)\[\]\{\}]+", " ", clean)
        clean = re.sub(r"[\"'`]", "", clean)
        clean = re.sub(r"^[\-\–\—\+\*]+\s*", "", clean)
        clean = re.sub(r"\s+", " ", clean).strip(" ,;:-")
        clean = re.sub(r"\bс[012]\b", "", clean)
        clean = re.sub(r"\bкатегори[яи]\s*[cс]?[012]\b", "", clean)
        clean = re.sub(r"\bдля\s+(?:жарки|смазывания|подачи|декора|украшения)\b", "", clean)
        clean = re.sub(r"\b(?:по вкусу|по желанию|при желании|для подачи|для украшения|для декора)\b", "", clean)
        clean = re.sub(r"\bдобав[а-я]*\s+по\b.*$", "", clean)
        clean = re.sub(r"\b(?:примерно|около|градусов|понадобится|желательно|опционально)\b", "", clean)
        clean = re.sub(r"\b(?:любой|любая|любое|любые|любого|любую)\b", "", clean)
        clean = re.sub(r"\b(?:измельченн(?:ая|ый|ое|ые)|нарезанн(?:ая|ый|ое|ые)|сушен(?:ая|ый|ое|ые)|свеж(?:ая|ий|ее|ие)|быстродействующ(?:ие|ий|ая)|цельнозернов(?:ая|ой|ые)|газированн(?:ая|ый|ое|ые)|несладк(?:ая|ий|ое|ие))\b", "", clean)
        clean = re.sub(r"\b\d+(?:[.,/]\d+)?(?:\s*-\s*\d+(?:[.,/]\d+)?)?\s*(?:шт|г|гр|кг|мл|л|ст\.?\s*л\.?|ч\.?\s*л\.?|пучк[а-я]*)\b.*$", "", clean)
        clean = re.sub(r"\b\d+\b", "", clean)
        clean = re.sub(r"\s*[,;/]\s*", " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip(" ,;:-")
        return clean

    @staticmethod
    def _extract_percent(name: str) -> str | None:
        match = re.search(r"(\d+[.,]?\d*)\s*%", name)
        if not match:
            return None
        return match.group(1).replace(',', '.').rstrip('0').rstrip('.')

    def _canonical_ingredient_name(self, raw_name: str) -> str:
        clean = self._normalize_ingredient_name(raw_name)
        if not clean:
            return ""

        if any(
            phrase in clean
            for phrase in (
                "по вкусу",
                "по желанию",
                "при желании",
                "для подачи",
                "для украшения",
                "для декора",
                "несколько листиков",
                "несколько веточек",
                "щепотка",
                "щепотки",
                "любимые",
                "желанию",
            )
        ):
            return ""
        if "вода" in clean:
            return ""
        if clean in {
            "растительное",
            "быстродействующие",
            "половина",
            "молотый",
            "молотая",
            "молотые",
            "цельнозерновая",
            "цельнозерновой",
            "т.п.",
            "для фритюра",
        }:
            return ""
        if re.fullmatch(r"[-\d\s.,/]+", clean):
            return ""
        if "градусов примерно" in clean or "понадобится" in clean:
            return ""
        if clean.startswith("для "):
            return ""

        percent = self._extract_percent(raw_name)

        if "яйц" in clean:
            if "перепел" in clean:
                return "Яйца перепелиные"
            return "Яйца куриные"

        if "лук зелен" in clean or "зеленый лук" in clean:
            return "Лук зеленый"
        if "лук красн" in clean:
            return "Лук красный"
        if clean == "лук" or "лук репчат" in clean:
            return "Лук репчатый"
        if "чеснок" in clean:
            return "Чеснок"
        if "морков" in clean:
            return "Морковь"
        if "огур" in clean:
            return "Огурцы"
        if "кабач" in clean:
            return "Кабачок"
        if "баклаж" in clean:
            return "Баклажан"
        if "картоф" in clean:
            return "Картофель"
        if "шпинат" in clean:
            return "Шпинат"
        if "салатн" in clean and "лист" in clean:
            return "Салатные листья"
        if "петруш" in clean:
            return "Петрушка"
        if "базилик" in clean:
            return "Базилик"
        if "кинз" in clean:
            return "Кинза"
        if "имбир" in clean:
            return "Имбирь"
        if "шампинь" in clean:
            return "Шампиньоны"
        if "редис" in clean:
            return "Редис"
        if "перец болгар" in clean or "болгарск" in clean:
            return "Перец болгарский"
        if "перец чили" in clean:
            return ""

        if "томатн паст" in clean:
            return "Томатная паста"
        if "протерт" in clean and "томат" in clean:
            return "Томаты протертые"
        if "вялен" in clean and "томат" in clean:
            return "Томаты вяленые"
        if "черри" in clean and ("томат" in clean or "помидор" in clean):
            return "Томаты черри"
        if "томат" in clean or "помидор" in clean:
            return "Помидоры"

        if "сок лимона" in clean or "лимонный сок" in clean:
            return "Лимонный сок"
        if "сок лайма" in clean or "лаймовый сок" in clean:
            return "Лаймовый сок"
        if "лимон" in clean:
            return "Лимон"
        if "лайм" in clean:
            return "Лайм"
        if "арбуз" in clean:
            return "Арбуз"
        if "апельсин" in clean:
            return "Апельсин"
        if "банан" in clean:
            return "Банан"
        if "клубник" in clean:
            return "Клубника"
        if "вишн" in clean:
            return "Вишня"
        if "малин" in clean:
            return "Малина"
        if "голубик" in clean:
            return "Голубика"
        if "клюкв" in clean:
            return "Клюква"
        if "ананас" in clean:
            return "Ананас"
        if "смородин" in clean:
            return "Смородина"
        if "изюм" in clean:
            return "Изюм"
        if "зерна граната" in clean or "зерна гранат" in clean:
            return "Гранат"
        if "гранатовый сок" in clean:
            return "Гранатовый сок"

        if "оливков" in clean and "масл" in clean:
            return "Масло оливковое"
        if "сливоч" in clean and "масл" in clean:
            return "Масло сливочное"
        if "кунжутн" in clean and "масл" in clean:
            return "Масло кунжутное"
        if "кокосов" in clean and "масл" in clean:
            return "Масло кокосовое"
        if "растительн" in clean and "масл" in clean:
            return "Масло растительное"
        if "масл" in clean:
            return "Масло растительное"

        if "соль" in clean and "перец" in clean:
            return ""
        if clean == "соль":
            return "Соль"
        if "сахар" in clean:
            return "Сахар"
        if re.fullmatch(r"мед|мёд", clean):
            return "Мед"
        if "ванил" in clean:
            return "Ваниль"
        if "паприк" in clean:
            return "Паприка"
        if "куркум" in clean:
            return "Куркума"
        if "уксус" in clean:
            return "Уксус"
        if "перец черн" in clean:
            return "Перец черный"
        if "перец молот" in clean:
            return "Перец черный"
        if "горчиц" in clean:
            return "Горчица"
        if "специи для плова" in clean:
            return "Специи для плова"
        if "орегано" in clean:
            return "Орегано"
        if "смесь сушеных трав" in clean or "микс сушеных трав" in clean:
            return "Смесь сушеных трав"

        if "вино" in clean:
            if "игрист" in clean:
                return "Вино игристое"
            if "сух" in clean and "бел" in clean:
                return "Вино белое сухое"
            if "сух" in clean and "красн" in clean:
                return "Вино красное сухое"
            return "Вино"

        if "соус" in clean:
            return clean[:1].upper() + clean[1:]
        if "бульон" in clean:
            if "курин" in clean:
                return "Бульон куриный"
            if "рыбн" in clean:
                return "Бульон рыбный"
            if "овощ" in clean:
                return "Бульон овощной"
            return "Бульон"

        if "кефир" in clean:
            return "Кефир"
        if "йогурт" in clean:
            return "Йогурт"
        if "молоко кокос" in clean:
            return "Молоко кокосовое"
        if "молоко" in clean:
            return "Молоко"
        if "сливк" in clean:
            level = float((percent or "10").replace(",", ".")) if percent else 10.0
            if level <= 15:
                normalized_percent = "10"
            elif level <= 26:
                normalized_percent = "20"
            else:
                normalized_percent = "33"
            return f"Сливки {normalized_percent}%"
        if "сметан" in clean:
            return "Сметана"
        if "творог" in clean:
            return "Творог"
        if "моцарелл" in clean:
            return "Моцарелла"
        if "пармезан" in clean:
            return "Пармезан"
        if "рикотт" in clean:
            return "Рикотта"
        if "брынз" in clean:
            return "Брынза"
        if clean in {"твердый", "полутвердый"}:
            return "Сыр твердый/полутвердый"
        if "сыр" in clean:
            if "творож" in clean:
                return "Сыр творожный"
            if "полутверд" in clean or "тверд" in clean:
                return "Сыр твердый/полутвердый"
            return "Сыр"

        if "мука пшенич" in clean:
            return "Мука пшеничная"
        if clean == "мука":
            return "Мука"
        if "овсян" in clean and "хлоп" in clean:
            return "Овсяные хлопья"
        if "греч" in clean and "лапш" in clean:
            return "Лапша гречневая"
        if "рисов" in clean and "лапш" in clean:
            return "Лапша рисовая"
        if "манн" in clean:
            return "Манная крупа"
        if clean == "жасмин":
            return "Рис жасмин"
        if "пшен" in clean:
            return "Пшено"
        if "греч" in clean:
            return "Гречка"
        if "жасмин" in clean and "рис" in clean:
            return "Рис жасмин"
        if "басмати" in clean and "рис" in clean:
            return "Рис басмати"
        if clean == "рис":
            return "Рис"
        if "кус-кус" in clean or "кускус" in clean:
            return "Кус-кус"
        if "паста" in clean or "каннеллони" in clean:
            return "Паста"
        if "багет" in clean:
            return "Багет"
        if "чечевиц" in clean:
            return "Чечевица"
        if "нут" in clean:
            return "Нут"
        if "крахмал" in clean and "кукуруз" in clean:
            return "Кукурузный крахмал"
        if "сухар" in clean:
            return "Панировочные сухари"
        if "разрыхлит" in clean:
            return "Разрыхлитель"
        if "дрожж" in clean:
            return "Дрожжи"
        if "желатин" in clean:
            return "Желатин"
        if "укроп" in clean:
            return "Укроп"
        if "щавел" in clean:
            return "Щавель"
        if "брокколи" in clean:
            return "Брокколи"
        if "цукини" in clean:
            return "Кабачок"
        if "зелен" in clean and clean in {"зелень", "небольшой пучок"}:
            return ""
        if "мята" in clean:
            return "Мята"
        if "розмарин" in clean:
            return "Розмарин"
        if "капуста пекин" in clean:
            return "Капуста пекинская"
        if "арбуз" in clean:
            return "Арбуз"
        if "горошек" in clean:
            return "Горошек зеленый"
        if clean.startswith("зелень"):
            return ""
        if "перловк" in clean:
            return "Перловка"
        if "фундук" in clean:
            return "Фундук"
        if "кешью" in clean:
            return "Кешью"
        if "грецк" in clean and "орех" in clean:
            return "Орех грецкий"
        if "тун" in clean:
            return "Тунец"
        if "каперс" in clean:
            return "Каперсы"
        if "кунжут" in clean:
            return "Кунжут"
        if "семеч" in clean:
            return "Семечки"
        if "микс семеч" in clean:
            return "Семечки"
        if "какао" in clean:
            return "Какао"
        if "в собственном соку" in clean:
            return ""
        if re.fullmatch(r"\d+\s+колечк[а-я]*", clean):
            return ""
        if "чайной ложки" in clean:
            return ""
        if "каждая специя" in clean:
            return ""
        if clean in {"зелень", "небольшой пучок", "молотый", "долгой варки"}:
            return ""
        if re.fullmatch(r"сода", clean):
            return "Сода"
        if "шоколад" in clean:
            return "Шоколад"

        if any(word in clean for word in ("курин", "индейк", "говядин", "свинин", "печен", "фарш")):
            return clean[:1].upper() + clean[1:]
        if "сайр" in clean:
            return "Сайра"
        if "горбуш" in clean:
            return "Горбуша"
        if any(word in clean for word in ("кревет", "рыб", "треск", "мид", "семг", "лосос")):
            clean = re.sub(r"\s*\b(?:или|либо)\b.*$", "", clean).strip(" ,;:-")
            return clean[:1].upper() + clean[1:]

        clean = re.sub(r"\s*\b(?:или|либо)\b.*$", "", clean).strip(" ,;:-")
        if re.fullmatch(r"[а-я-]+(?:ая|яя|ое|ее|ый|ий|ой|ые|ие|ого|ему|ыми|ими|ых)", clean):
            return ""
        return clean[:1].upper() + clean[1:]

    @staticmethod
    def _normalize_quantity(name: str, quantity: float, unit: str | None) -> tuple[float, str]:
        normalized_unit = MealPlannerService._normalize_unit(unit)
        raw = (unit or "").strip().casefold()
        factor = 1.0
        if raw in {"кг", "килограмм", "килограмма"}:
            factor = 1000.0
        elif raw in {"л", "литр", "литра"}:
            factor = 1000.0
        elif raw in {"стакан", "стакана", "стаканов"}:
            factor = 250.0
        elif raw in {"ст. л.", "ст.л.", "ст л", "столовая ложка", "столовые ложки"}:
            factor = 15.0
        elif raw in {"ч. л.", "ч.л.", "ч л", "чайная ложка", "чайные ложки"}:
            factor = 5.0
        quantity *= factor

        piece_to_grams = {
            "Лук репчатый": 100.0,
            "Лук красный": 100.0,
            "Морковь": 80.0,
            "Чеснок": 5.0,
            "Помидоры": 120.0,
            "Томаты черри": 15.0,
            "Огурцы": 120.0,
            "Перец болгарский": 150.0,
            "Картофель": 150.0,
            "Кабачок": 250.0,
            "Баклажан": 250.0,
            "Апельсин": 180.0,
            "Банан": 120.0,
            "Лимон": 120.0,
            "Редис": 20.0,
            "Горбуша": 250.0,
        }

        if name == "Яйца куриные" and normalized_unit == "г":
            return quantity / 50.0, "шт"
        if name == "Яйца перепелиные" and normalized_unit == "г":
            return quantity / 12.0, "шт"
        if normalized_unit == "шт" and name in piece_to_grams:
            return quantity * piece_to_grams[name], "г"
        if name in {"Молоко", "Кефир"} and normalized_unit == "г":
            return quantity, "мл"
        if name == "Лимонный сок" and normalized_unit == "г":
            return quantity, "мл"
        if name.startswith("Сливки ") and normalized_unit == "г":
            return quantity, "мл"
        if name.startswith("Масло ") and name != "Масло сливочное" and normalized_unit == "г":
            return quantity, "мл"
        if name.startswith("Масло ") and normalized_unit == "шт":
            return quantity * 15.0, "мл"
        if name == "Овсяные хлопья" and normalized_unit == "шт":
            return quantity * 40.0, "г"
        if name == "Сыр твердый/полутвердый" and normalized_unit == "шт":
            return quantity * 200.0, "г"
        if name.startswith("Бульон ") and normalized_unit == "шт":
            return 0.0, "шт"
        if name in {"Лук зеленый", "Петрушка", "Базилик", "Кинза", "Мята"} and normalized_unit == "шт":
            return quantity, "пучок"
        if name in {"Соль", "Перец черный", "Паприка", "Куркума"} and normalized_unit == "шт":
            return 0.0, "шт"
        return quantity, normalized_unit

    @staticmethod
    def _format_quantity(quantity: float, unit: str) -> str:
        if unit in {"г", "мл"} and quantity >= 1000:
            converted_unit = "кг" if unit == "г" else "л"
            value = round(quantity / 1000, 2)
            if isinstance(value, float) and value.is_integer():
                value = int(value)
            return f"{value} {converted_unit}"
        if unit in {"г", "мл"}:
            value = round(quantity)
        else:
            value = round(quantity, 1)
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return f"{value} {unit}"

    @staticmethod
    def _ingredient_category(name: str) -> str:
        lower = name.casefold()
        if "яйц" in lower:
            return "Яйца"
        if any(word in lower for word in ("соус", "томатная паста", "томаты протертые", "бульон", "вино", "пиво", "разрыхлитель", "сироп", "каперс", "горчиц", "желатин", "дрожж")):
            return "Соусы и добавки"
        if any(word in lower for word in ("масло", "соль", "сахар", "мед", "паприка", "куркума", "уксус", "перец черный", "розмарин", "кориандр", "кунжут", "орегано", "специи для плова", "сода", "ваниль", "смесь сушеных трав")):
            return "Специи и масла"
        if any(word in lower for word in ("курин", "индейк", "говядин", "свинин", "печен", "бекон")):
            return "Мясо и птица"
        if any(word in lower for word in ("рыб", "кревет", "мид", "лосос", "треск", "семг", "горбуш", "тун", "сайр")):
            return "Рыба и морепродукты"
        if any(word in lower for word in ("кефир", "молоко", "йогурт", "сливки", "сметана", "творог", "моцарелла", "пармезан", "рикотта", "сыр", "брынз")):
            return "Молочные продукты"
        if any(word in lower for word in ("греч", "рис", "лапша", "мука", "крупа", "пшено", "крахмал", "чечевица", "нут", "кус-кус", "сухари", "перловк", "овсян", "багет", "паста", "каннеллони")):
            return "Крупы и хлеб"
        if any(word in lower for word in ("гранатовый сок", "апельсин", "банан", "клубник", "лимон", "лайм", "арбуз", "вишн", "малин", "голубик", "клюкв", "ананас", "изюм", "смородин", "гранат")):
            return "Фрукты и ягоды"
        if any(word in lower for word in ("лук", "чеснок", "морковь", "огур", "кабач", "баклаж", "картоф", "шпинат", "салатн", "петруш", "базилик", "кинза", "имбир", "шампин", "редис", "перец болгар", "томат", "помидор", "укроп", "щавел", "брокколи", "мята", "цук", "горошек", "капуста пекин")):
            return "Овощи и зелень"
        if any(word in lower for word in ("семечки", "орех", "фундук", "кешью", "кунжут")):
            return "Орехи и семечки"
        if any(word in lower for word in ("сок", "кофе", "чай")):
            return "Напитки"
        return "Прочее"

    def _agg_shopping(self, agg: dict, recipe: dict, portions: float = 1.0) -> None:
        recipe_servings = max(float(recipe.get("servings") or 1), 1.0)
        multiplier = max(float(portions or 1.0), 0.0) / recipe_servings
        for ing in recipe.get("ingredients", []):
            normalized_name = self._canonical_ingredient_name(ing.get("name", ""))
            if not normalized_name:
                continue
            quantity, unit = self._normalize_quantity(normalized_name, float(ing.get("quantity", 0) or 0), ing.get("unit"))
            if quantity <= 0:
                continue
            key = f"{normalized_name}|{unit}"
            if key not in agg:
                agg[key] = {
                    "name": normalized_name,
                    "quantity": 0.0,
                    "unit": unit,
                    "category": self._ingredient_category(normalized_name),
                }
            agg[key]["quantity"] += quantity * multiplier

    async def _sync_shopping_list(self, plan_id: int, user_id: int, week_start: date) -> ShoppingList:
        result = await self.session.execute(
            select(MealPlan)
            .where(MealPlan.id == plan_id)
            .where(MealPlan.user_id == user_id)
            .options(selectinload(MealPlan.days).selectinload(DayPlan.meals).selectinload(Meal.container))
        )
        plan = result.scalar_one()

        existing_result = await self.session.execute(
            select(ShoppingList)
            .where(ShoppingList.plan_id == plan_id)
            .options(selectinload(ShoppingList.items))
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            await self.session.delete(existing)
            await self.session.flush()

        shopping_agg: dict[str, dict] = {}
        for day in plan.days:
            for meal in day.meals:
                recipe_name = meal.container.contents_description if meal.container else None
                recipe = _recipe_by_name(recipe_name)
                if recipe is None:
                    continue
                self._agg_shopping(shopping_agg, recipe, meal.portions or 1.0)

        return await self._create_shopping_list(user_id, plan_id, week_start, shopping_agg)

    async def _create_shopping_list(
        self,
        user_id: int,
        plan_id: int,
        week_start: date,
        agg: dict,
    ) -> ShoppingList:
        sl = ShoppingList(user_id=user_id, plan_id=plan_id, week_start=week_start)
        self.session.add(sl)
        await self.session.flush()

        category_priority = {
            "Овощи и зелень": 1,
            "Фрукты и ягоды": 2,
            "Мясо и птица": 3,
            "Рыба и морепродукты": 4,
            "Молочные продукты": 5,
            "Яйца": 6,
            "Крупы и хлеб": 7,
            "Орехи и семечки": 8,
            "Специи и масла": 9,
            "Соусы и добавки": 10,
            "Напитки": 11,
            "Прочее": 12,
        }
        for info in sorted(agg.values(), key=lambda item: (category_priority.get(item["category"], 99), item["name"])):
            self.session.add(
                ShoppingItem(
                    shopping_list_id=sl.id,
                    name=info["name"],
                    quantity=self._format_quantity(info["quantity"], info["unit"]),
                    unit=info["unit"],
                    category=info["category"],
                    priority=category_priority.get(info["category"], 10),
                )
            )

        return sl
