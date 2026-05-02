"""
Rule-based cooking planner.

The planner turns the active weekly menu into prep sessions. It follows the
local culinary principles: cook modules, repeat useful dishes, keep fresh
elements fresh, freeze only what handles freezing, and reduce daily cooking.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from math import ceil
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cooking import CookingPlan, CookingStep
from app.models.plan import DayPlan, Meal, MealPlan
from app.models.profile import Profile
from app.services.meal_planner_service import MealPlannerService, _recipe_by_name


COOKING_PLAN_VERSION = 27

WEEKDAY_NAMES = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье",
}

SHORT_WEEKDAY_NAMES = {
    0: "пн",
    1: "вт",
    2: "ср",
    3: "чт",
    4: "пт",
    5: "сб",
    6: "вс",
}

CONTAINER_WEEKDAY_CODES = {
    0: "ПН",
    1: "ВТ",
    2: "СР",
    3: "ЧТ",
    4: "ПТ",
    5: "СБ",
    6: "ВС",
}

MEAL_ORDER = {
    "breakfast": 0,
    "lunch": 1,
    "snack": 2,
    "dinner": 3,
}

BATCH_FRIENDLY_WORDS = (
    "котлет",
    "фрикадель",
    "запеканк",
    "сырник",
    "вафл",
    "суп",
    "бульон",
    "рагу",
    "болоньез",
    "пирог",
    "паштет",
    "риет",
    "хумус",
    "соус",
    "песто",
    "круп",
    "рис",
    "булгур",
    "греч",
    "перлов",
    "пшено",
    "запеч",
    "тушен",
    "марин",
)

STRONG_BATCH_MODULE_WORDS = (
    "котлет",
    "фрикадель",
    "сырник",
    "вафл",
    "запеканк",
    "суп",
    "бульон",
    "соус",
    "песто",
    "рагу",
    "болоньез",
    "паштет",
    "риет",
    "хумус",
)

FRESH_FINISH_WORDS = (
    "салат",
    "огурец",
    "огурцы",
    "зелень",
    "руккол",
    "лист",
    "свеж",
    "брускетт",
)

FREEZER_FRIENDLY_WORDS = (
    "котлет",
    "фрикадель",
    "сырник",
    "вафл",
    "запеканк",
    "бульон",
    "соус",
    "рагу",
    "болоньез",
    "пирог",
    "тесто",
    "паштет",
    "риет",
)

FREEZER_RISK_WORDS = (
    "салат",
    "огурец",
    "зелень",
    "сметан",
    "сливки",
    "майонез",
    "рыба",
    "кревет",
    "мидии",
    "кальмар",
    "морепродукт",
)

PROTEIN_WORDS = (
    "куриц",
    "индей",
    "говяд",
    "свинин",
    "рыб",
    "лосос",
    "треск",
    "тунец",
    "кревет",
    "фарш",
    "котлет",
    "фрикадель",
    "яйц",
    "творог",
    "сырник",
    "бобов",
    "нут",
    "чечев",
    "фасол",
)

GRAIN_WORDS = (
    "рис",
    "греч",
    "булгур",
    "пшено",
    "перлов",
    "паста",
    "лапша",
    "картоф",
    "круп",
    "кус-кус",
    "кускус",
)

VEGETABLE_WORDS = (
    "овощ",
    "морков",
    "кабач",
    "баклаж",
    "томат",
    "помид",
    "лук",
    "чеснок",
    "перец",
    "зелень",
    "шпинат",
    "брокколи",
    "салат",
    "огур",
    "гриб",
)

SAUCE_WORDS = (
    "соус",
    "песто",
    "заправк",
    "йогурт",
    "сливоч",
    "томат",
    "горчиц",
    "масло",
    "лимон",
)


@dataclass(slots=True)
class PlannedMeal:
    meal_id: int
    day_id: int
    day_date: date
    meal_type: str
    meal_name: str
    meal_order: int
    meal_time: str | None
    recipe_name: str
    kbzhu: dict
    recipe: dict | None
    container_label: str | None
    portion_grams: int | None


@dataclass(slots=True)
class CookingAction:
    session_index: int
    recipe_name: str
    title: str
    description: str
    duration_minutes: int
    is_parallel: bool
    category: str
    recipe_order: int
    ingredient_names: tuple[str, ...] = ()


class CookingPlannerService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def build_for_plan(
        self,
        user_id: int,
        meal_plan_id: int,
        scheduled_date: date,
    ) -> CookingPlan:
        result = await self.session.execute(
            select(MealPlan)
            .where(MealPlan.id == meal_plan_id)
            .where(MealPlan.user_id == user_id)
            .options(
                selectinload(MealPlan.days)
                .selectinload(DayPlan.meals)
                .selectinload(Meal.container)
            )
        )
        meal_plan = result.scalar_one_or_none()
        if meal_plan is None:
            raise ValueError("Meal plan not found")

        profile_result = await self.session.execute(select(Profile).where(Profile.user_id == user_id))
        profile = profile_result.scalar_one_or_none()
        if profile is None:
            raise ValueError("Profile not found")

        existing_result = await self.session.execute(
            select(CookingPlan)
            .where(CookingPlan.user_id == user_id)
            .where(CookingPlan.plan_id == meal_plan_id)
            .options(selectinload(CookingPlan.steps))
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            await self.session.delete(existing)
            await self.session.flush()

        planned_meals = self._collect_meals(meal_plan, profile, from_date=meal_plan.period_start)
        sessions = self._build_session_shells(meal_plan, profile, scheduled_date)
        steps_data, meta = self._build_steps_and_meta(planned_meals, sessions, profile, period_end=meal_plan.period_end)

        for step_number, step_data in enumerate(steps_data, start=1):
            step_data["step_number"] = step_number
        self._attach_step_numbers(meta, steps_data)

        estimated_time = sum(session["estimated_time_min"] for session in meta["sessions"])
        active_time = sum(session["active_time_min"] for session in meta["sessions"])
        cooking_plan = CookingPlan(
            user_id=user_id,
            plan_id=meal_plan_id,
            scheduled_date=scheduled_date,
            estimated_time_min=estimated_time,
            active_time_min=active_time,
            parallel_groups=[session["index"] for session in meta["sessions"]],
            container_distribution=meta,
        )
        self.session.add(cooking_plan)
        await self.session.flush()

        for step_data in steps_data:
            step = CookingStep(
                cooking_plan_id=cooking_plan.id,
                step_number=step_data["step_number"],
                title=step_data["title"],
                description=step_data["description"],
                duration_minutes=step_data["duration_minutes"],
                is_parallel=step_data["is_parallel"],
                parallel_group=step_data["parallel_group"],
            )
            self.session.add(step)

        await self.session.commit()
        await self.session.refresh(cooking_plan)
        return cooking_plan

    def _collect_meals(self, meal_plan: MealPlan, profile: Profile, from_date: date) -> list[PlannedMeal]:
        meal_meta = self._profile_meal_meta(profile)
        first_date = max(meal_plan.period_start, min(from_date, meal_plan.period_end))
        meals: list[PlannedMeal] = []
        for day in sorted(meal_plan.days, key=lambda item: item.date):
            if day.date < first_date:
                continue
            for meal in sorted(day.meals, key=lambda item: meal_meta.get(item.meal_type, {}).get("order", 99)):
                recipe_name = meal.container.contents_description if meal.container else None
                if not recipe_name:
                    continue
                meta = meal_meta.get(meal.meal_type, {})
                meals.append(
                    PlannedMeal(
                        meal_id=meal.id,
                        day_id=day.id,
                        day_date=day.date,
                        meal_type=meal.meal_type,
                        meal_name=str(meta.get("name") or self._fallback_meal_name(meal.meal_type)),
                        meal_order=int(meta.get("order") or 0) + 1,
                        meal_time=meta.get("time"),
                        recipe_name=recipe_name,
                        kbzhu=meal.kbzhu_actual or (meal.container.kbzhu if meal.container else {}) or {},
                        recipe=_recipe_by_name(recipe_name),
                        container_label=meal.container.label if meal.container else None,
                        portion_grams=int(round(((_recipe_by_name(recipe_name) or {}).get("serving_grams") or 0) * (meal.portions or 1.0))) or None,
                    )
                )
        return meals

    def _build_session_shells(
        self,
        meal_plan: MealPlan,
        profile: Profile,
        scheduled_date: date,
    ) -> list[dict]:
        frequency = str(profile.cooking_frequency or "twice_a_week").casefold()
        start = meal_plan.period_start  # e.g. Monday
        end = meal_plan.period_end      # e.g. Sunday

        # Sessions are scheduled BEFORE the food is eaten:
        # you cook on day D, the food is consumed starting day D+1.
        if any(token in frequency for token in ("every", "daily", "кажд")):
            # Cook every evening for the next day.
            # Sessions: [start-1, start, start+1, ..., start+(n-2)]  (n sessions for n days)
            n = (end - start).days + 1
            dates = [start - timedelta(days=1) + timedelta(days=i) for i in range(n)]
        elif any(token in frequency for token in ("once", "1", "один")):
            # One big prep the day before the week starts (e.g. Sunday for Mon–Sun).
            dates = [start - timedelta(days=1)]
        else:
            # Twice a week: first session day before start, second session at midpoint.
            # e.g. Sunday (covers Mon–Thu) + Thursday (covers Fri–Sun).
            half = (end - start).days // 2          # = 3 for a 7-day week
            session1 = start - timedelta(days=1)    # Sunday
            session2 = start + timedelta(days=half) # Thursday
            dates = [session1, session2] if session2 < end else [session1]

        sessions = []
        for index, session_date in enumerate(dates, start=1):
            if len(dates) == 1:
                title = "Большая заготовка недели"
            elif len(dates) == 2:
                title = "Основная заготовка" if index == 1 else "Вторая заготовка"
            else:
                next_day = session_date + timedelta(days=1)
                title = f"Заготовка на {self._date_label(next_day)}"
            sessions.append(
                {
                    "index": index,
                    "date": session_date,
                    "title": title,
                    "estimated_time_min": 0,
                    "active_time_min": 0,
                    "meals_covered": 0,
                    "modules": [],
                    "step_numbers": [],
                }
            )
        return sessions

    def _build_steps_and_meta(
        self,
        planned_meals: list[PlannedMeal],
        sessions: list[dict],
        profile: Profile,
        period_end: date | None = None,
    ) -> tuple[list[dict], dict]:
        if period_end is None:
            period_end = max((m.day_date for m in planned_meals), default=sessions[-1]["date"])

        # Universal coverage formula (works for all frequencies):
        #   session on day D  →  covers meals on days [D+1 … next_session.date] (inclusive)
        #   last session      →  covers meals on days [D+1 … period_end]
        # This matches the product rule: "cook today, eat from tomorrow".

        steps: list[dict] = []
        modules: list[dict] = []

        for i, session in enumerate(sessions):
            cov_start = session["date"] + timedelta(days=1)
            cov_end = sessions[i + 1]["date"] if i + 1 < len(sessions) else period_end

            # Collect meals whose consumption date falls within this session's coverage
            session_meals = [m for m in planned_meals if cov_start <= m.day_date <= cov_end]

            # Group by recipe within this session
            grouped_here: dict[str, list[PlannedMeal]] = {}
            for meal in session_meals:
                grouped_here.setdefault(meal.recipe_name, []).append(meal)

            session_actions: list[CookingAction] = []
            for recipe_name, meals in sorted(grouped_here.items(), key=lambda item: (item[1][0].day_date, item[0])):
                recipe = meals[0].recipe
                fresh_finish = self._needs_fresh_finish(recipe_name, recipe)
                module = self._module_payload(recipe_name, meals, session["date"], recipe, fresh_finish)
                modules.append(module)
                session["modules"].append(module)
                session["meals_covered"] += len(meals)
                session_actions.extend(self._recipe_actions(recipe_name, recipe, module, session["index"]))

            session_steps = self._session_setup_steps(session, session_actions, session["modules"])
            action_steps = self._action_steps(session_actions)
            action_steps.extend(self._module_packing_steps(session, session["modules"], action_steps))
            session_steps.extend(action_steps)
            session["estimated_time_min"], session["active_time_min"] = self._session_time_estimate(session_steps)
            steps.extend(session_steps)

        ordered_steps = sorted(steps, key=lambda item: (item["session_index"], item.get("_order", 500)))
        for step in ordered_steps:
            step.pop("_order", None)
            step.pop("_category", None)
            step.pop("_recipe_name", None)
        meta = {
            "version": COOKING_PLAN_VERSION,
            "summary": {
                "strategy": self._strategy_label(profile),
                "sessions_count": len(sessions),
                "meals_count": len(planned_meals),
                "batch_modules_count": len(modules),
            },
            "sessions": [
                {
                    **session,
                    "date": session["date"].isoformat(),
                    "date_label": self._date_label(session["date"]),
                    "modules": session["modules"],
                }
                for session in sessions
            ],
            "modules": modules,
            "principles": [],
        }
        return ordered_steps, meta

    def _recipe_actions(
        self,
        recipe_name: str,
        recipe: dict | None,
        module: dict,
        session_index: int,
    ) -> list[CookingAction]:
        instructions = self._recipe_instructions(recipe)
        if not instructions:
            instructions = [f"Приготовить {recipe_name} по рецепту."]

        actions: list[CookingAction] = []
        scaled_ingredients = self._scaled_ingredients(recipe, module["portions"])
        for order, instruction in enumerate(instructions, start=1):
            for phase_index, phase in enumerate(self._instruction_phases(recipe_name, instruction), start=1):
                category = self._classify_instruction(phase)
                matched_ingredients = self._ingredients_for_instruction(phase, scaled_ingredients)
                duration = self._instruction_duration(phase, category)
                description = self._action_description(module, phase, matched_ingredients)
                if "Действие:" not in description:
                    continue
                actions.append(
                    CookingAction(
                        session_index=session_index,
                        recipe_name=recipe_name,
                        title=self._instruction_title(recipe_name, phase, category),
                        description=description,
                        duration_minutes=duration,
                        is_parallel=category in {"bake", "boil", "simmer", "rest"},
                        category=category,
                        recipe_order=order * 10 + phase_index,
                        ingredient_names=tuple(item["name"] for item in matched_ingredients),
                    )
                )
        return sorted(actions, key=lambda action: self._recipe_action_order(recipe_name, action))

    @staticmethod
    def _instruction_phases(recipe_name: str, instruction: str) -> list[str]:
        recipe_lower = recipe_name.casefold()
        text = instruction.strip()
        lowered = text.casefold()
        if "томатный рыбный суп" in recipe_lower and lowered.startswith("сварить бульон"):
            return [
                "Мелко нарезать морковь, лук и половину петрушки для рыбного бульона; в кастрюлю добавить рыбный набор и нарезанные овощи.",
            ]
        if "куриные бедра с апельсинами" in recipe_lower and "мариноваться минимум на час" in lowered:
            return [
                "Куриные бедрышки хорошо смешать с маринадом.",
                "Оставить куриные бедрышки мариноваться минимум на 60 минут при комнатной температуре.",
            ]
        if "самый вкусный говяжий гуляш" in recipe_lower and "тушить на медленном огне под крышкой 40 минут" in lowered:
            return [
                "Добавить к гуляшу мелко нарезанные помидоры, воду и специи.",
                "Тушить гуляш на медленном огне под крышкой 40 минут.",
            ]
        if "самый вкусный говяжий гуляш" in recipe_lower and lowered.startswith("убрать крышку"):
            return [
                "Снять крышку с гуляша.",
                "Тушить гуляш без крышки 20-30 минут, периодически помешивая, чтобы соус загустел.",
            ]
        if "обжарить лук до мягкости" in lowered and "тушить 5 минут" in lowered:
            return [
                re.sub(r"\s+и\s+тушить\s+5\s+минут.*", ".", text, flags=re.I),
                "Тушить томатную заправку под крышкой 5 минут.",
            ]
        if "бульон довести до кипения" in lowered and "варить 15 минут" in lowered and ("еще 5 минут" in lowered or "ещё 5 минут" in lowered):
            return [
                "Бульон довести до кипения, добавить промытый рис жасмин и кусочки филе.",
                "Варить суп с рисом и рыбой 15 минут.",
                "Добавить томатный соус и варить еще 5 минут.",
            ]
        marinade_wait = re.search(r"\b(оставить\s+промариноваться\s+на\s+\d+(?:[-–]\d+)?\s+минут[а-я]*)", text, flags=re.I)
        if marinade_wait:
            before = re.sub(r"\s+\u0438$", "", text[: marinade_wait.start()].strip(" ,.;"), flags=re.I)
            phases = []
            if before:
                phases.append(before + ".")
            phases.append(marinade_wait.group(1).strip().rstrip(".") + ".")
            return phases
        return [text]

    @staticmethod
    def _recipe_action_order(recipe_name: str, action: CookingAction) -> tuple[float, int]:
        recipe_lower = recipe_name.casefold()
        text = action.description.casefold()
        order = float(action.recipe_order)
        if "горбуш" in recipe_lower:
            if "морковь нарезать" in text:
                order = 1.0
            elif "смешать морковь" in text:
                order = 2.0
            elif "горбушу нарезать" in text:
                order = 3.0
            elif "подготовить 4 квадрата" in text:
                order = 4.0
            elif "на морковь выложить" in text:
                order = 5.0
            elif action.category == "bake" and "духовк" in text:
                order = 6.0
        return (order, action.recipe_order)

    def _scaled_ingredients(self, recipe: dict | None, portions: int | float) -> list[dict]:
        if not recipe:
            return []
        servings = max(float(recipe.get("servings") or 1), 1.0)
        multiplier = max(float(portions or 1), 0.0) / servings
        normalizer = MealPlannerService(self.session)
        ingredients = []
        for ingredient in recipe.get("ingredients", []):
            raw_name = str(ingredient.get("name") or "").strip()
            if not raw_name:
                continue
            if any(token in raw_name.casefold() for token in ("по вкусу", "по желанию")):
                continue
            canonical = normalizer._canonical_ingredient_name(raw_name)
            if not canonical:
                continue
            quantity, unit = normalizer._normalize_quantity(
                canonical,
                float(ingredient.get("quantity", 0) or 0),
                ingredient.get("unit"),
            )
            quantity *= multiplier
            if not MealPlannerService._is_meaningful_shopping_quantity(quantity, unit):
                continue
            ingredients.append({
                "name": canonical,
                "raw_name": raw_name,
                "quantity": quantity,
                "unit": unit,
            })
        return ingredients

    @staticmethod
    def _ingredients_for_instruction(instruction: str, ingredients: list[dict]) -> list[dict]:
        lowered = instruction.casefold()
        matched: dict[tuple[str, str], dict] = {}
        for ingredient in ingredients:
            name = str(ingredient.get("name") or "")
            raw_name = str(ingredient.get("raw_name") or "")
            if "набор для бульона" in name.casefold() and "рыбный набор" not in lowered:
                continue
            words = [
                word
                for word in re.findall(r"[а-яёa-z]{3,}", f"{name} {raw_name}".casefold())
                if word not in {"для", "или", "без"}
            ]
            stems = {word[:5] for word in words if len(word) >= 5} | set(words)
            if any(stem and stem in lowered for stem in stems):
                display_name = name
                key = (display_name.casefold(), str(ingredient.get("unit") or "").casefold())
                if key in matched:
                    matched[key]["quantity"] = float(matched[key].get("quantity") or 0) + float(ingredient.get("quantity") or 0)
                else:
                    matched[key] = {**ingredient, "name": display_name}
        return list(matched.values())[:8]

    @staticmethod
    def _recipe_instructions(recipe: dict | None) -> list[str]:
        if not recipe:
            return []
        instructions: list[str] = []
        for step in recipe.get("steps", []):
            if not isinstance(step, dict):
                continue
            raw_text = str(step.get("text") or "").strip()
            if not raw_text:
                continue
            raw_text = CookingPlannerService._normalize_recipe_step_text(raw_text)
            chunks = re.split(r"(?=\b\d+\s*\.\s*)", raw_text)
            step_added = False
            for chunk in chunks:
                chunk = re.sub(r"^\d+\s*\.\s*", "", chunk).strip()
                if not chunk:
                    continue
                parts = re.split(r"(?<=[.!?])\s+", chunk)
                for part in parts:
                    clean = CookingPlannerService._clean_instruction(part)
                    if clean and CookingPlannerService._looks_like_instruction(clean):
                        instructions.append(clean)
                        step_added = True
            if not step_added:
                clean = CookingPlannerService._clean_instruction(raw_text)
                if clean and CookingPlannerService._looks_like_instruction(clean):
                    instructions.append(clean)
        return instructions

    @staticmethod
    def _normalize_recipe_step_text(value: str) -> str:
        clean = re.sub(r"\s+", " ", value).strip()
        clean = re.sub(r"\bприготовления\s+\d+\s*минут[а-я]*", "", clean, flags=re.I)
        clean = re.sub(r"\bвыход\s*:?\s*~?\s*\d+(?:[,.]\d+)?\s*(?:г|мл)\b", "", clean, flags=re.I)
        clean = re.sub(r"\bкбжу\s+на\s+100\s*г\s*:?.*?(?=(?:\d+\.\s*)|$)", "", clean, flags=re.I)
        clean = re.sub(r"\bна\s+\d+(?:-\d+)?\s+порци[а-я]*\b[:.\s-]*", "", clean, flags=re.I)
        return re.sub(r"\s+", " ", clean).strip(" -–—.;")

    @staticmethod
    def _clean_instruction(value: str) -> str:
        clean = value.strip(" -–—.;")
        clean = re.sub(r"^\d+\s*\.\s*", "", clean)
        clean = re.sub(r"\s+", " ", clean)
        clean = re.sub(r"\bна\s+\d+(?:-\d+)?\s+порци[а-я]*\b", "", clean, flags=re.I)
        clean = re.sub(r"\s+", " ", clean).strip(" -–—.;")
        return clean

    @staticmethod
    def _looks_like_instruction(value: str) -> bool:
        lowered = value.casefold()
        if len(lowered) < 8:
            return False
        reject_words = ("когда хочется", "прекрасное", "замены:", "можно заменить", "подавать можно", "бабушка всегда говорила")
        if any(word in lowered for word in reject_words):
            return False
        if lowered.startswith(("заправкой ", "приготовления ", "сначала —", "сначала -")):
            return False
        if lowered in {"перемешать", "хорошо перемешать", "подавать", "готово"}:
            return False
        if lowered.startswith("готов") and "подав" in lowered:
            return False
        action_words = (
            "нарез", "натер", "измельч", "очист", "промы", "раздел", "снять",
            "смеш", "перемеш", "взб", "залить", "добав", "всып", "полить",
            "отвар", "варить", "повар", "кип", "довести", "туш", "запеч",
            "отправ", "разогр", "обжар", "жар", "сковород", "вылож", "перелож", "полож", "влож",
            "подготов", "заверн", "сформ", "скрут", "остав", "разлож",
            "прогреть", "процед", "марин", "готовить", "вымеш", "накрыть",
        )
        return any(word in lowered for word in action_words)

    @staticmethod
    def _classify_instruction(value: str) -> str:
        lowered = value.casefold()
        if lowered.startswith(("мариновать", "оставить промариноваться")):
            return "rest"
        if lowered.startswith(("мелко нарезать", "нарезать", "снять крышку")):
            return "prep"
        if lowered.startswith("подготовить") and "фольг" in lowered:
            return "prep"
        if "снять фольгу" in lowered or "выпекать" in lowered:
            return "bake"
        if "форму для запекания" in lowered or "фольгой" in lowered:
            return "bake"
        if "отправить" in lowered and ("духовк" in lowered or "градус" in lowered):
            return "bake"
        if "тесто" in lowered and any(word in lowered for word in ("вымеш", "мучной", "форму для хлеба", "обмять", "подходить")):
            return "prep" if "оставить" not in lowered else "rest"
        if "фарш" in lowered or "панировочн" in lowered or "сформировать" in lowered:
            return "prep"
        if "промарин" in lowered or "маринад" in lowered or "замарин" in lowered or ("соев" in lowered and ("мед" in lowered or "мёд" in lowered) and "масл" in lowered):
            return "prep"
        if lowered.startswith("выложить") and any(word in lowered for word in ("тарелк", "подав", "посыпать")):
            return "finish"
        if lowered.startswith("в миске соединить"):
            return "assemble"
        if "горячее масло" in lowered:
            return "assemble"
        if "соус терияки" in lowered:
            return "assemble"
        if "бульон довести до кипения" in lowered and "варить" in lowered:
            return "boil"
        if lowered.startswith("варить ") and "томатный соус" in lowered:
            return "boil"
        if lowered.startswith("переложить ингредиенты в сотейник"):
            return "assemble"
        if lowered.startswith("в сотейник к остальным ингредиентам добавить"):
            return "assemble"
        if lowered.startswith("обжарить лук") and "тушить" in lowered:
            return "fry"
        if "жарим на среднем нагреве" in lowered or "до полного схватывания" in lowered:
            return "fry"
        if "добавить курицу" in lowered or "обжаривать смесь" in lowered:
            return "fry"
        if "лапшу отварить" in lowered:
            return "boil"
        if "рис хорошо промыть" in lowered or "выложить промытый рис" in lowered:
            return "simmer"
        if "готовить еще" in lowered or "готовить ещё" in lowered or ("готовить плов" in lowered and ("рис" in lowered or "нут" in lowered)):
            return "simmer"
        if "промаринован" in lowered or "разложить рядом" in lowered:
            return "bake"
        if "духовк" in lowered or "запеч" in lowered or "противень" in lowered:
            return "bake"
        if re.search(r"\bтуш(?:ить|им|ат|ите|ен|еный|еная|ение|итьcя|иться|ится)", lowered) or "под крыш" in lowered:
            return "simmer"
        if lowered.startswith(("сварить", "отварить", "залить холодной водой")):
            return "boil"
        if "бульон" in lowered and any(word in lowered for word in ("вар", "свар")):
            return "boil"
        if any(word in lowered for word in ("сотейник", "кастрюл", "казан")) and any(word in lowered for word in ("залить", "бульон", "вода", "кип", "туш")):
            return "simmer"
        if "жарен" in lowered and not any(word in lowered for word in ("обжар", "жарить", "сковород", "разогрет")):
            return "assemble"
        if any(word in lowered for word in ("обжар", "жарить", "сковород")):
            return "fry"
        if (lowered.startswith(("оставить", "замарин", "дать постоять")) or "отправить мариноваться" in lowered) and any(word in lowered for word in ("час", "минут", "постоять", "упар", "марин")):
            return "rest"
        if any(word in lowered for word in ("вылож", "перелож", "полож", "влож", "залить", "полить", "заверн", "сформ", "скрут", "добав", "всып")):
            return "assemble"
        if any(word in lowered for word in ("нарез", "натер", "измельч", "очист", "промы", "раздел", "снять", "подготов", "смеш", "перемеш", "взб")):
            return "prep"
        if any(word in lowered for word in ("рис", "круп", "греч", "картоф", "бульон", "фасол", "нут", "чечев")) and any(word in lowered for word in ("вар", "отвар", "кип")):
            return "boil"
        if any(word in lowered for word in ("вар", "отвар", "кип", "прогреть", "довести")):
            return "boil"
        return "finish"

    @staticmethod
    def _instruction_duration(value: str, category: str) -> int:
        lowered = value.casefold()
        ranges = re.findall(r"(\d+)\s*[-–]\s*(\d+)\s*мин", lowered)
        if ranges:
            return max(1, int(ranges[0][1]))
        minutes = re.findall(r"(\d+)\s*мин", lowered)
        if minutes:
            return max(1, int(minutes[0]))
        hours = re.findall(r"(\d+)\s*(?:час|часа|часов)\b", lowered)
        if hours:
            return int(hours[0]) * 60 if category == "rest" else min(60, int(hours[0]) * 60)
        if "переложить ингредиенты в сотейник" in lowered or "довести до кипения" in lowered:
            return 5
        defaults = {
            "bake": 25,
            "boil": 15,
            "simmer": 20,
            "rest": 5,
            "fry": 8,
            "prep": 7,
            "assemble": 6,
            "finish": 5,
        }
        return defaults.get(category, 5)

    @staticmethod
    def _instruction_title(recipe_name: str, value: str, category: str) -> str:
        lowered = value.casefold()
        if category == "prep":
            if any(word in lowered for word in ("мяс", "говяд", "куриц", "филе", "рыб", "тунец", "горбуш")):
                return f"Подготовить белок для «{recipe_name}»"
            if any(word in lowered for word in ("овощ", "томат", "перец", "лук", "морков", "картоф", "огур", "капуст")):
                return f"Подготовить овощи для «{recipe_name}»"
            if any(word in lowered for word in ("рис", "круп", "лапш")):
                return f"Подготовить крупу или лапшу для «{recipe_name}»"
            return f"Подготовить ингредиенты для «{recipe_name}»"
        if category == "boil":
            return f"Варить: «{recipe_name}»"
        if category == "bake":
            return f"Поставить в духовку: «{recipe_name}»"
        if category == "fry":
            return f"Обжарить для «{recipe_name}»"
        if category == "simmer":
            return f"Тушить: «{recipe_name}»"
        if category == "rest":
            return f"Оставить/замариновать: «{recipe_name}»"
        if category == "assemble":
            return f"Собрать «{recipe_name}»"
        return f"Завершить «{recipe_name}»"

    @staticmethod
    def _action_description(module: dict, instruction: str, ingredients: list[dict]) -> str:
        lines = []
        if ingredients:
            formatted = [item for item in (CookingPlannerService._format_ingredient(item) for item in ingredients) if item]
            if formatted:
                lines.append("Количество: " + ", ".join(formatted) + ".")
        normalized = CookingPlannerService._humanize_instruction(str(module.get("name") or ""), instruction)
        if normalized:
            lines.append("Действие: " + normalized.rstrip(".") + ".")
        return "\n".join(lines)

    @staticmethod
    def _format_ingredient(ingredient: dict) -> str:
        name = str(ingredient.get("name") or "").strip()
        unit = str(ingredient.get("unit") or "").strip()
        quantity = float(ingredient.get("quantity") or 0)
        lower_name = name.casefold()
        lower_unit = unit.casefold()
        if not name:
            return ""
        if quantity <= 0:
            return name
        if lower_unit in {"шт", "зубчика", "зубчик", "головка", "головки"} and re.search(r"\d+\s*[-–]?\s*\d*\s*шт", lower_name):
            return name
        if lower_unit == "шт" and any(
            word in lower_name
            for word in (
                "масло",
                "соль",
                "перец",
                "паприка",
                "кориандр",
                "зира",
                "специи",
                "кунжут",
                "соус",
                "уксус",
                "тимьян",
            )
        ):
            return name
        if lower_unit == "шт":
            pieces = max(1, ceil(quantity)) if quantity % 1 else int(quantity)
            return f"{name} {pieces} шт"
        return f"{name} {MealPlannerService._format_quantity(quantity, unit)}".strip()

    @staticmethod
    def _display_ingredient_name(name: str) -> str:
        clean = re.sub(r"\s+", " ", name).strip(" .,:;")
        clean = clean.replace("ё", "е")
        clean = re.sub(r"\s*\((?:понадобится|нужно|нужен|нужна)\s*", " ", clean, flags=re.I)
        clean = clean.replace(")", "")
        clean = re.sub(r"\bдля\s+жарки\b", "", clean, flags=re.I)
        clean = re.sub(r"\bдля\s+смазывания\b", "", clean, flags=re.I)
        clean = re.sub(r"\s+", " ", clean).strip(" -–—.,")
        replacements = {
            "Рыбный набор для бульона": "рыбный суповой набор для бульона",
            "Рыбный набор": "рыбный суповой набор для бульона",
            "Паста томатная": "томатная паста",
            "Томаты": "помидоры",
            "Томат": "помидор",
            "Лук репчатый": "лук",
            "Огурцы свежие": "огурцы",
            "Масло подсолнечное": "подсолнечное масло",
        }
        clean = replacements.get(clean, clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        if not clean:
            return ""
        return clean[0].upper() + clean[1:]

    @staticmethod
    def _humanize_instruction(recipe_name: str, instruction: str) -> str:
        recipe_lower = recipe_name.casefold()
        clean = instruction.strip().rstrip(".")
        clean = clean.replace("ё", "е")
        clean = re.sub(r"\s+", " ", clean)
        clean = re.sub(r"\bпоставить\s+таймер\s+на\s+(\d+(?:-\d+)?)\s+минут[а-я]*", r"варить \1 минут", clean, flags=re.I)
        clean = re.sub(r"\bв течении\b", "в течение", clean, flags=re.I)
        clean = re.sub(r"\bрыбный набор\b", "Бульон рыбный", clean, flags=re.I)
        clean = re.sub(r"в кастрюлю выложить Бульон рыбный", "в кастрюлю добавить Бульон рыбный", clean, flags=re.I)
        clean = re.sub(r"^Жасмин залить\b", "Жасминовый чай залить", clean, flags=re.I)
        clean = re.sub(r"^Вложить в горячий бульон\b", "В горячий бульон добавить", clean, flags=re.I)
        clean = re.sub(r"^Затем положить в кастрюлю\b", "В эту же кастрюлю добавить", clean, flags=re.I)
        clean = re.sub(r"^казане\b", "В казане", clean, flags=re.I)
        clean = re.sub(r"^форму\b", "Форму", clean, flags=re.I)
        clean = re.sub(r"^Рис перед варкой хорошо промыть\b", "Промыть рис до прозрачной воды", clean, flags=re.I)
        clean = re.sub(
            r"^Нарезать соломкой томат, редис, капусту, огурец, чеснок, лук, говядину\b",
            "Нарезать соломкой говядину, томат, редис, капусту, огурец, чеснок и лук",
            clean,
            flags=re.I,
        )
        clean = re.sub(
            r"^Говядину замариновать\b",
            "Нарезанную говядину замариновать",
            clean,
            flags=re.I,
        )
        clean = re.sub(
            r"^Горячее масло с луком и чесноком объединить с капустой",
            "После обжарки лука и чеснока сразу перелить горячее масло с луком и чесноком к капусте",
            clean,
            flags=re.I,
        )
        clean = re.sub(
            r"^Взболтать яйцо и вылить на разогретую сковороду с растительным маслом, распределив по всей поверхности сковороды\b",
            "На отдельной сковороде разогреть растительное масло, вылить взболтанное яйцо тонким слоем и жарить 1-2 минуты до схватывания",
            clean,
            flags=re.I,
        )
        clean = re.sub(
            r"^На сковороду добавить растительное масло и обжарить чеснок и лук\b",
            "На свободной сковороде разогреть растительное масло и обжарить чеснок с луком",
            clean,
            flags=re.I,
        )
        clean = re.sub(
            r"^Выложить на тарелку все ингредиенты как бы точками \(горками\).*",
            "",
            clean,
            flags=re.I,
        )
        clean = re.sub(
            r"^Отварить лапшу$",
            "Отварить лапшу в кипящей воде до готовности по инструкции на упаковке и слить воду",
            clean,
            flags=re.I,
        )
        clean = re.sub(
            r"^Выложить на тарелку смесь овощей с айсбергом, сверху разложить обжаренную курицу с морковью\b",
            "Остудить курицу 5 минут и разложить с салатной смесью по контейнерам",
            clean,
            flags=re.I,
        )
        clean = re.sub(
            r"^Выложить удон в тарелку.*",
            "",
            clean,
            flags=re.I,
        )
        clean = re.sub(
            r"^Оставить бульон в холодильнике настаиваться\b",
            "Охладить смешанный бульон кукси в холодильнике",
            clean,
            flags=re.I,
        )
        if "кукси" in recipe_lower and re.match(r"^Залить все ингредиенты бульоном\b", clean, flags=re.I):
            return ""
        if "кукси" in recipe_lower:
            clean = re.sub(
                r"^В миске соединить ледяную воду\b",
                "Смешать бульон кукси: соединить ледяную воду",
                clean,
                flags=re.I,
            )
        if "лагман" in recipe_lower:
            clean = re.sub(
                r"^Обжарить в течение 3 минут на среднем нагреве",
                "Продолжать обжаривать говядину с луком 3 минуты на среднем нагреве",
                clean,
                flags=re.I,
            )
            clean = re.sub(
                r"^Переложить ингредиенты в сотейник",
                "Переложить обжаренную говядину с луком в сотейник",
                clean,
                flags=re.I,
            )
            clean = re.sub(
                r"^Тушить на слабом нагреве\b",
                "Тушить лагман на слабом нагреве",
                clean,
                flags=re.I,
            )
            clean = re.sub(
                r"^В сотейник к остальным ингредиентам добавить\b",
                "В сотейник с лагманом добавить",
                clean,
                flags=re.I,
            )
        if "томатный рыбный суп" in recipe_lower:
            clean = re.sub(
                r"^Сварить бульон: в кастрюлю добавить Бульон рыбный\b",
                "В кастрюлю для рыбного бульона положить рыбный набор",
                clean,
                flags=re.I,
            )
            clean = re.sub(
                r"^Залить холодной водой и варить\b",
                "Залить содержимое кастрюли холодной водой и варить рыбный бульон",
                clean,
                flags=re.I,
            )
            clean = re.sub(
                r"^Процедить бульон, он готов\b",
                "Процедить рыбный бульон",
                clean,
                flags=re.I,
            )
            clean = re.sub(
                r"^Бульон довести до кипения\b",
                "Рыбный бульон довести до кипения",
                clean,
                flags=re.I,
            )
            clean = re.sub(
                r"^Варить 15 минут\b",
                "Варить суп с рисом и рыбой 15 минут",
                clean,
                flags=re.I,
            )
        if "горбуш" in recipe_lower and re.match(r"^Сверху выложить филе горбуши\b", clean, flags=re.I):
            clean = "На морковь выложить филе горбуши, полить каждый кусочек лимонным соком и завернуть края пергамента"
        if "горбуш" in recipe_lower:
            clean = re.sub(r"^Горбушу нарезать\s*,", "Горбушу нарезать на порции,", clean, flags=re.I)
        if "суп с гречневой лапшой" in recipe_lower:
            clean = re.sub(
                r"^Варить на среднем нагреве или при слабом кипении\b",
                "Варить бульон с овощами и грибами на среднем нагреве или при слабом кипении",
                clean,
                flags=re.I,
            )
            clean = re.sub(
                r"^Варить на слабом нагреве\b",
                "Варить суп с рыбой и лапшой на слабом нагреве",
                clean,
                flags=re.I,
            )
        if "самый вкусный говяжий гуляш" in recipe_lower:
            clean = re.sub(
                r"^Затем добавить нарезанные мелко помидоры\b",
                "К говядине добавить мелко нарезанные помидоры",
                clean,
                flags=re.I,
            )
        clean = re.sub(
            r"^Форму для запекания выложить тефтели",
            "В форму для запекания выложить тефтели",
            clean,
            flags=re.I,
        )
        clean = re.sub(r"\bразогрую\b", "разогретую", clean, flags=re.I)
        clean = re.sub(
            r"^Лапшу отварить течение\b",
            "Лапшу отварить в кипящей воде",
            clean,
            flags=re.I,
        )
        clean = re.sub(
            r"^Подошедшее тесто смазать",
            "Подошедшее тесто смазать",
            clean,
            flags=re.I,
        )
        if re.fullmatch(r"Переложить на тарелку рядом\.?", clean, flags=re.I):
            return ""
        clean = re.sub(
            r"^Куриные бедрышки хорошо смешать с маринадом",
            "Когда маринад готов, хорошо смешать с ним куриные бедрышки",
            clean,
            flags=re.I,
        )
        clean = re.sub(
            r"^Затем добавить к нему",
            "Смешать маринад: добавить к апельсиновому соку",
            clean,
            flags=re.I,
        )
        clean = re.sub(
            r"^Смазать его маслом,\s*выложить на противень",
            "Смешать нут с маслом, выложить на противень",
            clean,
            flags=re.I,
        )
        clean = re.sub(r"\s+", " ", clean).strip(" -–—.;")
        return clean

    @staticmethod
    def _action_rank(action: CookingAction) -> int:
        lowered = f"{action.title}\n{action.description}".casefold()
        if action.category == "prep" and any(word in lowered for word in ("промыть", "маринад", "замарин")):
            return 10000 + action.recipe_order
        if action.category in {"boil", "bake"} and action.recipe_order <= 2:
            return (15000 if action.category == "boil" else 16000) + action.recipe_order
        category_rank = {
            "prep": 30,
            "fry": 40,
            "boil": 45,
            "bake": 46,
            "simmer": 50,
            "rest": 52,
            "assemble": 55,
            "finish": 80,
        }
        return category_rank.get(action.category, 80) * 1000 + action.recipe_order

    def _session_setup_steps(self, session: dict, actions: list[CookingAction], modules: list[dict]) -> list[dict]:
        if not actions:
            return []
        recipe_names = ", ".join(module["name"] for module in modules[:12])
        inventory = self._session_inventory(actions)
        steps = [
            {
                "session_index": session["index"],
                "title": "Подготовить продукты и рабочее место",
                "description": "\n".join(
                    line for line in [
                        "Достать продукты из списка покупок для этой заготовки.",
                        f"Готовим сегодня: {recipe_names}." if recipe_names else None,
                        "Точные количества будут указаны в каждом шаге ниже.",
                        f"Инвентарь: {inventory}.",
                        "На маленькой кухне держать одновременно не больше 2 активных конфорок; новое блюдо ставить на плиту, когда предыдущая кастрюля уже спокойно варится или снята.",
                        "Поставить рядом чистые контейнеры и маркер для подписей.",
                    ]
                    if line
                ),
                "duration_minutes": 8,
                "is_parallel": False,
                "parallel_group": session["index"],
                "_order": 0,
            }
        ]
        oven_actions = [action.title for action in actions if action.category == "bake"]
        if oven_actions:
            degrees = self._extract_oven_degrees(" ".join(oven_actions))
            steps.append(
                {
                    "session_index": session["index"],
                    "title": f"Разогреть духовку до {degrees} °C",
                    "description": "Включить духовку сразу, чтобы она грелась параллельно нарезке и сборке блюд.",
                    "duration_minutes": 10,
                    "is_parallel": True,
                    "parallel_group": session["index"],
                    "_order": 1,
                }
            )
        return steps

    @staticmethod
    def _extract_oven_degrees(text: str) -> int:
        match = re.search(r"(\d{3})\s*(?:град|°)", text, flags=re.I)
        if not match:
            return 180
        value = int(match.group(1))
        return value if 120 <= value <= 260 else 180

    @staticmethod
    def _session_inventory(actions: list[CookingAction]) -> str:
        categories = {action.category for action in actions}
        items = ["2 доски (овощи и белок отдельно)", "острый нож", "миски", "контейнеры"]
        if categories & {"boil", "simmer"}:
            items.append("кастрюля/сотейник")
        if "fry" in categories:
            items.append("сковорода")
        if "bake" in categories:
            items.append("противень или форма")
        if any("блендер" in action.title.casefold() or "пробить" in action.description.casefold() for action in actions):
            items.append("блендер")
        return ", ".join(dict.fromkeys(items))

    def _action_to_step(self, action: CookingAction) -> dict:
        return {
            "session_index": action.session_index,
            "title": action.title,
            "description": action.description,
            "duration_minutes": action.duration_minutes,
            "is_parallel": action.is_parallel,
            "parallel_group": action.session_index,
            "_order": 100 + self._action_rank(action),
        }

    @staticmethod
    def _session_time_estimate(steps: list[dict]) -> tuple[int, int]:
        active = 0
        passive_total = 0
        passive_max = 0
        for step in steps:
            duration = int(step.get("duration_minutes") or 0)
            if step.get("is_parallel"):
                passive_total += duration
                passive_max = max(passive_max, duration)
                active += max(1, min(4, ceil(duration * 0.12)))
            else:
                active += duration
        estimated = max(active + min(45, ceil(passive_total * 0.18)), passive_max + ceil(active * 0.55))
        return int(estimated), int(active)

    def _action_steps(self, actions: list[CookingAction]) -> list[dict]:
        by_recipe: dict[str, list[CookingAction]] = {}
        for action in actions:
            by_recipe.setdefault(action.recipe_name, []).append(action)

        queues: list[list[dict]] = []
        for recipe_name, recipe_actions in by_recipe.items():
            recipe_queue = []
            for category, items in self._action_runs(recipe_actions):
                recipe_queue.append(self._grouped_action_step(recipe_name, category, items))
            if recipe_queue:
                queues.append(recipe_queue)

        steps: list[dict] = []
        blockers: dict[int, dict[str, int | str]] = {}

        def blocker_minutes(step: dict) -> int:
            duration = int(step.get("duration_minutes") or 1)
            if not step.get("is_parallel"):
                return 0
            return max(1, duration)

        def tick_blockers(minutes: int) -> None:
            for queue_index, blocker in list(blockers.items()):
                remaining = int(blocker.get("remaining") or 0)
                blocker["remaining"] = max(0, remaining - minutes)
                if blocker["remaining"] <= 0:
                    blockers.pop(queue_index, None)

        def step_resource(step: dict) -> str:
            if not step.get("is_parallel"):
                return ""
            category = str(step.get("_category") or "")
            if category == "bake":
                return "oven"
            if category in {"boil", "simmer"}:
                return "burner"
            return ""

        def step_temperature(step: dict) -> str:
            text = f"{step.get('title') or ''}\n{step.get('description') or ''}".casefold()
            match = re.search(r"(\d{3})\s*(?:°|град)", text)
            if match:
                return match.group(1)
            return "180" if step_resource(step) == "oven" else ""

        def active_burner_count() -> int:
            return sum(
                1
                for blocker in blockers.values()
                if int(blocker.get("remaining") or 0) > 0 and blocker.get("resource") == "burner"
            )

        def active_oven_temperatures() -> set[str]:
            return {
                str(blocker.get("temperature") or "180")
                for blocker in blockers.values()
                if int(blocker.get("remaining") or 0) > 0 and blocker.get("resource") == "oven"
            }

        def oven_is_preheating() -> bool:
            return any(
                int(blocker.get("remaining") or 0) > 0 and blocker.get("resource") == "oven_preheat"
                for blocker in blockers.values()
            )

        def is_blocked(queue_index: int) -> bool:
            blocker = blockers.get(queue_index)
            return bool(blocker and int(blocker.get("remaining") or 0) > 0)

        def resource_is_available(step: dict) -> bool:
            resource = step_resource(step)
            if resource == "burner":
                return active_burner_count() < 2
            if resource == "oven":
                if oven_is_preheating():
                    return False
                temperatures = active_oven_temperatures()
                return not temperatures or step_temperature(step) in temperatures
            return True

        def resource_wait_minutes(step: dict) -> int:
            resource = step_resource(step)
            if resource == "burner":
                values = [
                    int(blocker.get("remaining") or 0)
                    for blocker in blockers.values()
                    if blocker.get("resource") == "burner" and int(blocker.get("remaining") or 0) > 0
                ]
            elif resource == "oven":
                target_temperature = step_temperature(step)
                values = [
                    int(blocker.get("remaining") or 0)
                    for blocker in blockers.values()
                    if blocker.get("resource") in {"oven", "oven_preheat"}
                    and (
                        blocker.get("resource") == "oven_preheat"
                        or str(blocker.get("temperature") or "180") != target_temperature
                    )
                    and int(blocker.get("remaining") or 0) > 0
                ]
            else:
                values = []
            return min(values, default=0)

        def next_passive_duration(queue: list[dict]) -> int:
            for step in queue:
                if step.get("is_parallel"):
                    return int(step.get("duration_minutes") or 0)
            return 0

        def next_passive_step(queue: list[dict]) -> dict | None:
            for step in queue:
                if step.get("is_parallel"):
                    return step
            return None

        def next_passive_resource(queue: list[dict]) -> str:
            step = next_passive_step(queue)
            return step_resource(step) if step else ""

        def active_minutes_to_passive(queue: list[dict]) -> int:
            minutes = 0
            for step in queue:
                if step.get("is_parallel"):
                    break
                minutes += max(1, int(step.get("duration_minutes") or 1))
            return minutes

        def passive_slot_score(step: dict | None) -> int:
            if not step:
                return 0
            resource = step_resource(step)
            if resource == "oven":
                return 3 if not active_oven_temperatures() else 1
            if resource == "burner":
                return max(0, 2 - active_burner_count())
            return 0

        def queue_priority(queue_index: int) -> tuple[int, int, int, int, int, int]:
            queue = queues[queue_index]
            first = queue[0]
            next_passive = next_passive_step(queue)
            passive_duration = next_passive_duration(queue)
            immediate_resource = step_resource(first)
            immediate_passive = 0
            if first.get("is_parallel") and resource_is_available(first):
                immediate_passive = 4 if immediate_resource in {"burner", "oven"} else 1
            slot_score = passive_slot_score(next_passive)
            distance = active_minutes_to_passive(queue)
            next_resource = step_resource(next_passive or {})
            reachable_soon = 1 if next_resource in {"burner", "oven"} and distance <= 15 and resource_is_available(next_passive) else 0
            return (immediate_passive, reachable_soon, slot_score, passive_duration, -distance, -queue_index)

        if any(step_resource(step) == "oven" for queue in queues for step in queue):
            blockers[-1] = {
                "remaining": 10,
                "resource": "oven_preheat",
                "temperature": "180",
            }

        while any(queues):
            ready_indexes = [
                index
                for index, queue in enumerate(queues)
                if queue and not is_blocked(index)
            ]
            if not ready_indexes:
                wait = min(
                    (
                        int(blocker.get("remaining") or 0)
                        for index, blocker in blockers.items()
                        if index >= 0 and queues[index] and int(blocker.get("remaining") or 0) > 0
                    ),
                    default=0,
                )
                if wait <= 0:
                    break
                tick_blockers(wait)
                continue

            constrained_ready = []
            for index in ready_indexes:
                first = queues[index][0]
                next_passive = next_passive_step(queues[index])
                if not resource_is_available(first):
                    continue
                if first.get("is_parallel") or not next_passive or resource_is_available(next_passive):
                    constrained_ready.append(index)
            if constrained_ready:
                ready_indexes = constrained_ready
            else:
                non_resource_ready = [
                    index
                    for index in ready_indexes
                    if not step_resource(queues[index][0])
                    and not step_resource(next_passive_step(queues[index]) or {})
                ]
                if non_resource_ready:
                    ready_indexes = non_resource_ready
                else:
                    waits = [resource_wait_minutes(queues[index][0]) for index in ready_indexes]
                    wait = min((value for value in waits if value > 0), default=0)
                    if wait > 0:
                        tick_blockers(wait)
                        continue

            queue_index = max(ready_indexes, key=queue_priority)
            progressed = False
            while queues[queue_index] and not is_blocked(queue_index):
                step = queues[queue_index][0]
                if not resource_is_available(step):
                    if progressed:
                        break
                    wait = resource_wait_minutes(step)
                    if wait > 0:
                        tick_blockers(wait)
                    break

                step = queues[queue_index].pop(0)
                step["_order"] = 100 + len(steps)
                steps.append(step)
                progressed = True

                if step.get("is_parallel"):
                    minutes = blocker_minutes(step)
                    if minutes > 0:
                        blockers[queue_index] = {
                            "remaining": minutes,
                            "resource": step_resource(step),
                            "temperature": step_temperature(step),
                        }
                    break

                tick_blockers(max(1, int(step.get("duration_minutes") or 1)))

        return steps

    @staticmethod
    def _uses_heat(category: str) -> bool:
        return category in {"boil", "bake", "simmer", "fry"}

    def _action_runs(self, actions: list[CookingAction]) -> list[tuple[str, list[CookingAction]]]:
        runs: list[tuple[str, list[CookingAction]]] = []
        current_category: str | None = None
        current_key: tuple[str, str] | None = None
        current_items: list[CookingAction] = []
        for action in actions:
            category = self._group_category(action)
            key = (category, self._run_subcategory(action, category))
            if current_items and key != current_key:
                runs.append((current_category or "prep", current_items))
                current_items = []
            current_category = category
            current_key = key
            current_items.append(action)
        if current_items:
            runs.append((current_category or "prep", current_items))
        return runs

    @staticmethod
    def _run_subcategory(action: CookingAction, category: str) -> str:
        text = action.description.casefold()
        if category == "fry":
            if "кунжут" in text and not any(word in text for word in ("кур", "говяд", "рыб", "яйц")):
                return "sesame"
            if "яйц" in text or "омлет" in text:
                return "egg"
            if any(word in text for word in ("говяд", "кур", "бедр", "филе", "рыб")):
                return "protein"
            if any(word in text for word in ("лук", "чеснок", "морков", "перец", "овощ")):
                return "vegetables"
        if category in {"boil", "simmer"}:
            if "лапш" in text:
                return "noodles"
            if "бульон" in text:
                return "broth"
        if category == "rest":
            if "бульон" in text:
                return "broth"
        return category

    @staticmethod
    def _group_category(action: CookingAction) -> str:
        category = action.category
        text = f"{action.title}\n{action.description}".casefold()
        recipe_lower = action.recipe_name.casefold()
        if "постный плов" in recipe_lower and category in {"assemble", "finish"} and any(
            word in text for word in ("рис", "нут", "чеснок", "специи", "готовить")
        ):
            return "simmer"
        if category == "prep" and (
            ("рис" in text and any(word in text for word in ("промыть", "варк", "варкой")))
            or ("лапш" in text and "отвар" in text)
        ):
            return "boil"
        if category == "simmer" and "яичные блинчики" in recipe_lower and "рис" in text:
            return "boil"
        if category in {"boil", "bake", "simmer", "rest"}:
            return category
        if category in {"fry"}:
            return "fry"
        if category in {"assemble", "finish"}:
            return "assemble"
        return "prep"

    def _grouped_action_step(self, recipe_name: str, category: str, items: list[CookingAction]) -> dict:
        first = items[0]
        description_lines = self._compact_action_lines(items)
        duration = self._group_duration(items, category)
        title = self._group_title(recipe_name, category, items)
        return {
            "session_index": first.session_index,
            "title": title,
            "description": "\n".join(description_lines),
            "duration_minutes": duration,
            "is_parallel": category in {"boil", "bake", "simmer", "rest"},
            "parallel_group": first.session_index,
            "_category": category,
            "_recipe_name": recipe_name,
        }

    @staticmethod
    def _compact_action_lines(items: list[CookingAction]) -> list[str]:
        instructions = []
        quantities = []
        for action in items:
            instruction = ""
            for line in action.description.splitlines():
                if line.startswith("Количество:"):
                    raw_quantity = line.replace("Количество:", "").strip().rstrip(".")
                    for quantity in re.split(r",\s+(?=[А-ЯЁA-Z])", raw_quantity):
                        quantity = quantity.strip()
                        if quantity and quantity not in quantities:
                            quantities.append(quantity)
                elif line.startswith("Действие:"):
                    instruction = line.replace("Действие:", "").strip()
            clean = instruction.strip().rstrip(".")
            if clean and clean not in instructions:
                instructions.append(clean + ".")
        lines = []
        if quantities:
            lines.append(f"Количество: {', '.join(quantities[:16])}.")
        lines.extend(sorted(instructions, key=CookingPlannerService._instruction_line_rank))
        return lines

    @staticmethod
    def _instruction_line_rank(value: str) -> int:
        lowered = value.casefold()
        if "нарезать соломкой говядину" in lowered:
            return 0
        if "для начала" in lowered or "выдавить сок" in lowered:
            return 0
        if "смешать маринад" in lowered:
            return 1
        if "нарезанную говядину замариновать" in lowered:
            return 1
        if "когда маринад готов" in lowered:
            return 2
        if "промыть рис" in lowered or "рис хорошо промыть" in lowered:
            return 0
        if "рис басмати отварить" in lowered or "отварить рис" in lowered:
            return 1
        if "выложить промытый рис" in lowered or "отварить в воде" in lowered:
            return 1
        if "после того, как вода закипит" in lowered:
            return 2
        if "добавить к овощам нут" in lowered:
            return 0
        if "влить в казан кипяток" in lowered:
            return 2
        if "воткнуть в рис" in lowered:
            return 2
        if "готовить плов" in lowered:
            return 3
        if "обжарить на сухой сковороде кунжут" in lowered:
            return 0
        if "отдельной сковороде" in lowered and "яйц" in lowered:
            return 1
        if "свободной сковороде" in lowered:
            return 2
        if "маринованную говядину" in lowered:
            return 3
        if "горячее масло" in lowered:
            return 4
        if "в миске соединить ледяную воду" in lowered:
            return 5
        if "держать обжаренную говядину" in lowered:
            return 6
        if "подготовить 4 квадрата" in lowered:
            return 0
        if "на морковь выложить филе горбуши" in lowered or "сверху выложить филе горбуши" in lowered:
            return 1
        return 10

    @staticmethod
    def _group_duration(items: list[CookingAction], category: str) -> int:
        raw = sum(max(1, int(item.duration_minutes or 0)) for item in items)
        if category == "prep":
            return max(4, min(12, ceil(raw * 0.32)))
        if category == "fry":
            return max(4, min(12, ceil(raw * 0.5)))
        if category == "assemble":
            return max(3, min(10, ceil(raw * 0.42)))
        return max(item.duration_minutes for item in items)

    def _group_title(self, recipe_name: str, category: str, items: list[CookingAction]) -> str:
        text = " ".join(item.description for item in items).casefold()
        recipe_lower = recipe_name.casefold()
        if category == "prep":
            if "арбузный пунш" in recipe_lower and "сок арбуза" in text:
                return f"«{recipe_name}» · смешать соки для пунша"
            if "томатный рыбный суп" in recipe_lower and "филе трески" in text:
                return f"«{recipe_name}» · нарезать рыбу"
            if "лапш" in text:
                return f"«{recipe_name}» · подготовить лапшу"
            return f"«{recipe_name}» · подготовить"
        if category == "fry":
            if "кунжут" in text and not any(word in text for word in ("кур", "говяд", "рыб", "яйц")):
                return f"«{recipe_name}» · подсушить кунжут"
            if "яйц" in text or "омлет" in text or "блинчик" in text:
                return f"«{recipe_name}» · пожарить яичный блинчик"
            if "кукси" in recipe_lower and "лук" in text and "чеснок" in text:
                return f"«{recipe_name}» · обжарить лук и чеснок"
            if "удон" in recipe_lower and any(word in text for word in ("кур", "бедр")):
                return f"«{recipe_name}» · обжарить курицу с овощами"
            if "лагман" in recipe_lower and "говяд" in text and "специи" in text:
                return f"«{recipe_name}» · обжарить говядину со специями"
            if "лагман" in recipe_lower and "томатн" in text:
                return f"«{recipe_name}» · обжарить с томатной пастой"
            if "говяд" in text:
                return f"«{recipe_name}» · обжарить говядину"
            if any(word in text for word in ("курин", "куриц", "бедр")):
                return f"«{recipe_name}» · обжарить курицу"
            if any(word in text for word in ("рыб", "филе")):
                return f"«{recipe_name}» · обжарить рыбу"
            if "самый вкусный говяжий гуляш" in recipe_lower and any(word in text for word in ("шампинь", "томатн")):
                return f"«{recipe_name}» · обжарить грибы с томатной пастой"
            if "томатный рыбный суп" in recipe_lower and any(word in text for word in ("помид", "паприк", "томатн")):
                return f"«{recipe_name}» · приготовить томатную заправку"
            if any(word in text for word in ("морков", "лук", "перец", "овощ", "чеснок")):
                return f"«{recipe_name}» · обжарить овощи"
            return f"«{recipe_name}» · обжарить"
        if category == "assemble":
            if "арбузный пунш" in recipe_lower and any(word in text for word in ("шарики арбуза", "внешнюю часть", "процеженным")):
                return f"«{recipe_name}» · наполнить арбуз пуншем"
            if "арбузный пунш" in recipe_lower and "жасмин" in text:
                return f"«{recipe_name}» · заварить чай и пробить арбуз"
            if "арбузный пунш" in recipe_lower:
                return f"«{recipe_name}» · смешать пунш"
            if "лагман" in recipe_lower and "сотейник" in text and "бульон" in text:
                return f"«{recipe_name}» · добавить овощи и бульон"
            if "лагман" in recipe_lower and "с лагманом добавить" in text:
                return f"«{recipe_name}» · добавить лапшу и довести до кипения"
            if "кукси" in recipe_lower and any(word in text for word in ("ледяную воду", "уксус", "соевый соус")):
                return f"«{recipe_name}» · смешать бульон кукси"
            if "кукси" in recipe_lower and any(word in text for word in ("омлет", "блинчик")):
                return f"«{recipe_name}» · нарезать яичный блинчик"
            if "кукси" in recipe_lower and any(word in text for word in ("капуст", "горячее масло", "лук", "чеснок")):
                return f"«{recipe_name}» · смешать капусту с луком и чесноком"
            if "томатный рыбный суп" in recipe_lower and "процедить" in text and "бульон" in text:
                return f"«{recipe_name}» · процедить рыбный бульон"
            if "томатный рыбный суп" in recipe_lower and "рис" in text and "филе" in text:
                return f"«{recipe_name}» · добавить рис и рыбу в бульон"
            if "горбуш" in recipe_lower and "пергамент" in text:
                return f"«{recipe_name}» · собрать конверты с горбушей"
            if "суп с гречневой лапшой" in recipe_lower and "горячий бульон" in text:
                return f"«{recipe_name}» · добавить овощи и грибы в бульон"
            if "суп с гречневой лапшой" in recipe_lower and "рыбу" in text and "лапш" in text:
                return f"«{recipe_name}» · добавить рыбу и лапшу"
            if "суп с гречневой лапшой" in recipe_lower and "томатов черри" in text:
                return f"«{recipe_name}» · добавить томаты и зеленый лук"
            if "удон" in recipe_lower and any(word in text for word in ("терияки", "лапш", "кунжутное масло")):
                return f"«{recipe_name}» · соединить удон с курицей и овощами"
            return f"«{recipe_name}» · соединить компоненты"
        if category == "rest":
            if "пунш" in recipe_lower:
                return f"«{recipe_name}» · охладить"
            if "кукси" in recipe_lower and "бульон" in text:
                return f"«{recipe_name}» · охладить бульон кукси"
            return f"«{recipe_name}» · оставить заготовку"
        if category == "bake" and any(word in text for word in ("курин", "бедр")):
            return f"«{recipe_name}» · запечь курицу"
        if category == "bake" and re.search(r"(^|[^а-яё])нут([^а-яё]|$)", text):
            return f"«{recipe_name}» · запечь нут"
        if category == "bake" and any(word in recipe_lower for word in ("хлеб", "лепеш", "маффин")):
            return f"«{recipe_name}» · испечь"
        if category == "bake" and any(word in text for word in ("тефтел", "фрикадел")):
            return f"«{recipe_name}» · запечь тефтели"
        if category == "bake" and any(word in text for word in ("горбуш", "рыб", "филе")):
            return f"«{recipe_name}» · запечь рыбу"
        if category == "bake":
            return f"«{recipe_name}» · поставить в духовку"
        if category == "simmer" and "лагман" in recipe_lower and "переложить обжаренную" in text:
            return f"«{recipe_name}» · добавить овощи и бульон"
        if category == "simmer" and "лагман" in recipe_lower and "тушить лагман" in text:
            return f"«{recipe_name}» · тушить лагман"
        if category == "simmer" and "лагман" in recipe_lower and "с лагманом добавить" in text:
            return f"«{recipe_name}» · добавить лапшу и довести до кипения"
        if category == "simmer" and "лагман" in recipe_lower:
            return f"«{recipe_name}» · тушить до готовности"
        if category == "simmer" and "постный плов" in recipe_lower:
            return f"«{recipe_name}» · довести плов до готовности"
        if category == "simmer" and "самый вкусный говяжий гуляш" in recipe_lower:
            return f"«{recipe_name}» · тушить гуляш до мягкости"
        if category == "simmer" and "томатный рыбный суп" in recipe_lower and "обжарить лук" in text:
            return f"«{recipe_name}» · приготовить томатную заправку"
        if category == "simmer" and "суп" in recipe_lower:
            return f"«{recipe_name}» · довести суп до готовности"
        if category == "simmer" and "рис" in text:
            return f"«{recipe_name}» · довести крупу до готовности"
        if category == "simmer":
            return f"«{recipe_name}» · тушить до готовности"
        if category == "boil" and "кукси" in recipe_lower and "лапш" in text:
            return f"«{recipe_name}» · отварить лапшу"
        if category == "boil" and "томатный рыбный суп" in recipe_lower and "рис" in text and "рыб" in text:
            return f"«{recipe_name}» · сварить суп с рисом и рыбой"
        if category == "boil" and "томатный рыбный суп" in recipe_lower and ("бульон" in text or "рыбный" in text):
            return f"«{recipe_name}» · сварить рыбный бульон"
        if category == "boil" and "суп с гречневой лапшой" in recipe_lower:
            return f"«{recipe_name}» · сварить суп с рыбой и лапшой"
        if category == "boil" and "суп" in recipe_lower and "бульон" in text:
            return f"«{recipe_name}» · варить в бульоне"
        if category == "boil" and "лапш" in text:
            return f"«{recipe_name}» · отварить лапшу"
        if category == "boil" and "рис" in text:
            return f"«{recipe_name}» · сварить рис"
        if category == "boil":
            return f"«{recipe_name}» · сварить до готовности"
        return f"«{recipe_name}» · подготовить этап"

    def _quick_meal_steps(self, session: dict, meals: list[PlannedMeal]) -> list[dict]:
        steps: list[dict] = []
        for offset, meal in enumerate(sorted(meals, key=lambda item: (item.day_date, item.meal_time or "", item.recipe_name))):
            instructions = self._recipe_instructions(meal.recipe)
            if not instructions:
                instructions = [f"Приготовить {meal.recipe_name} по рецепту."]
            lines = [
                clean
                for clean in (self._humanize_instruction(meal.recipe_name, instruction) for instruction in instructions)
                if clean
            ] or [f"Приготовить {meal.recipe_name} по рецепту."]
            duration = int((meal.recipe or {}).get("prep_time_minutes") or 10) + int((meal.recipe or {}).get("cook_time_minutes") or 0)
            duration = max(8, min(45, duration))
            steps.append(
                {
                    "session_index": session["index"],
                    "title": f"{self._meal_label(meal)} - приготовить {meal.recipe_name}",
                    "description": "\n".join(lines),
                    "duration_minutes": duration,
                    "is_parallel": self._has_passive_time(meal.recipe),
                    "parallel_group": session["index"],
                    "_order": 90000 + offset,
                }
            )
        return steps

    @staticmethod
    def _profile_meal_meta(profile: Profile) -> dict[str, dict]:
        raw_meals = (profile.eating_schedule or {}).get("meals")
        if isinstance(raw_meals, list) and raw_meals:
            return {
                str(meal.get("id") or f"meal_{index + 1}"): {
                    "order": index,
                    "name": str(meal.get("name") or f"Прием {index + 1}"),
                    "time": str(meal.get("time") or "12:00"),
                }
                for index, meal in enumerate(raw_meals)
                if isinstance(meal, dict)
            }
        return {
            "breakfast": {"order": 0, "name": "Завтрак", "time": "08:00"},
            "lunch": {"order": 1, "name": "Обед", "time": "13:00"},
            "snack": {"order": 2, "name": "Перекус", "time": "16:00"},
            "dinner": {"order": 3, "name": "Ужин", "time": "19:00"},
        }

    @staticmethod
    def _fallback_meal_name(meal_type: str) -> str:
        return {
            "breakfast": "Завтрак",
            "lunch": "Обед",
            "snack": "Перекус",
            "dinner": "Ужин",
        }.get(meal_type, "Прием пищи")

    @staticmethod
    def _session_for_date(meal_date: date, sessions: list[dict]) -> dict:
        past_sessions = [session for session in sessions if session["date"] <= meal_date]
        if past_sessions:
            return past_sessions[-1]
        return sessions[0]

    @staticmethod
    def _recipe_text(recipe_name: str, recipe: dict | None) -> str:
        parts = [recipe_name]
        if recipe:
            parts.extend(str(tag) for tag in recipe.get("tags", []))
            parts.extend(str(ingredient.get("name", "")) for ingredient in recipe.get("ingredients", []))
            parts.extend(str(step.get("text", "")) for step in recipe.get("steps", []) if isinstance(step, dict))
        return " ".join(parts).casefold()

    def _is_batch_friendly(self, recipe_name: str, recipe: dict | None) -> bool:
        text = self._recipe_text(recipe_name, recipe)
        if self._needs_fresh_finish(recipe_name, recipe) and not any(word in text for word in FREEZER_FRIENDLY_WORDS):
            return False
        return any(word in text for word in BATCH_FRIENDLY_WORDS)

    def _is_strong_batch_module(self, recipe_name: str, recipe: dict | None) -> bool:
        text = self._recipe_text(recipe_name, recipe)
        return any(word in text for word in STRONG_BATCH_MODULE_WORDS)

    def _selected_batch_names(self, grouped: dict[str, list[PlannedMeal]], profile: Profile) -> set[str]:
        frequency = str(profile.cooking_frequency or "twice_a_week").casefold()
        if any(token in frequency for token in ("once", "1", "один")):
            return set(grouped)

        eligible: list[tuple[float, str]] = []
        for recipe_name, meals in grouped.items():
            recipe = meals[0].recipe
            fresh_finish = self._needs_fresh_finish(recipe_name, recipe)
            strong_batch = self._is_strong_batch_module(recipe_name, recipe)
            is_repeated = len(meals) > 1
            if not is_repeated and (not strong_batch or fresh_finish):
                continue
            recipe_time = self._batch_duration(recipe, len(meals), fresh_finish)
            score = len(meals) * 12
            if strong_batch:
                score += 8
            if self._is_freezer_friendly(recipe_name, recipe):
                score += 4
            if fresh_finish:
                score -= 5
            score -= recipe_time / 30
            eligible.append((score, recipe_name))

        eligible.sort(reverse=True)
        limit = self._max_batch_modules(profile)
        return {name for _score, name in eligible[:limit]}

    @staticmethod
    def _max_batch_modules(profile: Profile) -> int:
        budget = profile.cooking_time_budget if isinstance(profile.cooking_time_budget, dict) else {}
        raw_minutes = budget.get("minutes")
        period = str(budget.get("period") or "week").casefold()
        if isinstance(raw_minutes, (int, float)) and raw_minutes > 0:
            weekly_minutes = raw_minutes * 7 if period == "day" else raw_minutes
            return max(2, min(8, int(weekly_minutes // 35) or 2))
        frequency = str(profile.cooking_frequency or "twice_a_week").casefold()
        if any(token in frequency for token in ("once", "1", "один")):
            return 6
        if any(token in frequency for token in ("twice", "2", "два")):
            return 8
        return 4

    def _needs_fresh_finish(self, recipe_name: str, recipe: dict | None) -> bool:
        text = self._recipe_text(recipe_name, recipe)
        if any(word in text for word in FRESH_FINISH_WORDS):
            return True
        if any(word in text for word in ("рыба", "кревет", "мидии", "кальмар", "морепродукт")):
            return True
        return False

    def _is_freezer_friendly(self, recipe_name: str, recipe: dict | None) -> bool:
        text = self._recipe_text(recipe_name, recipe)
        if any(word in text for word in FREEZER_RISK_WORDS):
            return False
        if any(word in text for word in FREEZER_FRIENDLY_WORDS):
            return True
        return False

    @staticmethod
    def _container_storage_location(meal: PlannedMeal, session_date: date, freezer_friendly: bool) -> str:
        days_after = (meal.day_date - session_date).days
        if days_after <= 3:
            return "fridge"
        if freezer_friendly:
            return "freezer"
        return "later"

    def _has_passive_time(self, recipe: dict | None) -> bool:
        if not recipe:
            return False
        text = self._recipe_text(str(recipe.get("name") or ""), recipe)
        cook_time = int(recipe.get("cook_time_minutes") or 0)
        return cook_time >= 20 or any(word in text for word in ("запечь", "запек", "варить", "тушить", "бульон"))

    def _batch_duration(self, recipe: dict | None, meal_count: int, fresh_finish: bool) -> int:
        if not recipe:
            return 25 + min(20, meal_count * 4)
        base = int(recipe.get("prep_time_minutes") or 0) + int(recipe.get("cook_time_minutes") or 0)
        base = max(15, base)
        multiplier_add = min(25, max(0, meal_count - 1) * (4 if fresh_finish else 6))
        return min(110, base + multiplier_add)

    def _active_duration(self, recipe: dict | None, duration: int, meal_count: int) -> int:
        if not recipe or not self._has_passive_time(recipe):
            return max(8, ceil(duration * 0.85))
        prep = int(recipe.get("prep_time_minutes") or 0)
        extra_portions = max(0, meal_count - 1)
        return min(duration, max(8, prep + 8 + extra_portions * 2))

    def _module_payload(
        self,
        recipe_name: str,
        meals: list[PlannedMeal],
        session_date: date,
        recipe: dict | None,
        fresh_finish: bool,
    ) -> dict:
        meal_labels = [self._meal_label(meal) for meal in meals]
        days_after = [(meal.day_date - session_date).days for meal in meals]
        max_days = max(days_after) if days_after else 0
        freezer_friendly = self._is_freezer_friendly(recipe_name, recipe)
        if max_days <= 3:
            storage = "холодильник"
            storage_note = "Хранить в холодильнике до 3 дней, свежие элементы добавить перед подачей."
        elif freezer_friendly:
            storage = "холодильник + морозилка"
            storage_note = "Ближайшие порции оставить в холодильнике, остальные подписать и заморозить."
        else:
            storage = "быстрая сборка"
            storage_note = "Термообработанные компоненты подготовить заранее, свежие элементы добавить при раскладке или перед едой."

        return {
            "name": recipe_name,
            "portions": len(meals),
            "meal_labels": meal_labels,
            "containers": [
                {
                    "label": self._container_code(meal),
                    "meal_label": self._meal_label(meal),
                    "grams": meal.portion_grams,
                    "date": meal.day_date.isoformat(),
                    "meal_name": meal.meal_name,
                    "storage_location": self._container_storage_location(meal, session_date, freezer_friendly),
                }
                for meal in meals
            ],
            "ingredients": [
                self._format_ingredient(ingredient)
                for ingredient in self._scaled_ingredients(recipe, len(meals))
            ],
            "storage": storage,
            "storage_note": storage_note,
            "fresh_finish": fresh_finish,
            "freezer_friendly": freezer_friendly,
            "module_type": self._module_type(recipe_name, recipe),
        }

    def _module_type(self, recipe_name: str, recipe: dict | None) -> str:
        name_and_tags = recipe_name.casefold()
        if recipe:
            name_and_tags = " ".join([name_and_tags, *(str(tag).casefold() for tag in recipe.get("tags", []))])
        full_text = self._recipe_text(recipe_name, recipe)
        if any(word in name_and_tags for word in ("пунш", "напит", "смузи", "компот", "чай", "кофе")):
            return "напиток/перекус"
        if any(word in name_and_tags for word in ("соус", "песто", "заправк")):
            return "соус/акцент"
        if any(word in name_and_tags for word in ("салат", "боул")):
            return "сборка/салат"
        if any(word in full_text for word in PROTEIN_WORDS):
            return "белковый модуль"
        if any(word in full_text for word in GRAIN_WORDS):
            return "гарнир/база"
        if any(word in full_text for word in VEGETABLE_WORDS):
            return "овощной модуль"
        if any(word in full_text for word in SAUCE_WORDS):
            return "соус/акцент"
        return "готовое блюдо"

    @staticmethod
    def _meal_label(meal: PlannedMeal) -> str:
        weekday = SHORT_WEEKDAY_NAMES.get(meal.day_date.weekday(), "")
        time = f"{meal.meal_time} " if meal.meal_time else ""
        return f"{weekday} {meal.day_date.day}: {time}{meal.meal_name}"

    @staticmethod
    def _container_code(meal: PlannedMeal) -> str:
        weekday = CONTAINER_WEEKDAY_CODES.get(meal.day_date.weekday(), "")
        return f"{meal.meal_order} {weekday}".strip()

    @staticmethod
    def _date_label(value: date) -> str:
        return f"{WEEKDAY_NAMES.get(value.weekday(), '')}, {value.day:02d}.{value.month:02d}"

    @staticmethod
    def _batch_step_description(module: dict) -> str:
        labels = "; ".join(module["meal_labels"])
        lines = [
            f"Закрывает приемы: {labels}.",
            module["storage_note"],
        ]
        if module["fresh_finish"]:
            lines.append("Свежесть, зелень, хруст и соус добавлять перед едой, а не заранее в контейнер.")
        if module["freezer_friendly"] and module["storage"] == "холодильник + морозилка":
            lines.append("Порции из морозилки переложить в холодильник за 10-12 часов до еды.")
        return "\n".join(lines)

    @staticmethod
    def _session_insert_index(steps: list[dict], session_index: int) -> int:
        for index, step in enumerate(steps):
            if step["session_index"] == session_index:
                return index
        return len(steps)

    def _session_needs_base_step(self, modules: list[dict]) -> bool:
        if len(modules) >= 2:
            return True
        return any(module["module_type"] in {"гарнир/база", "овощной модуль", "соус/акцент"} for module in modules)

    @staticmethod
    def _base_step_description(modules: list[dict]) -> str:
        module_names = ", ".join(module["name"] for module in modules[:8]) or "блюда недели"
        return "\n".join(
            [
                f"Подготовить общий фон для: {module_names}.",
                "Если есть крупы или картофель - приготовить на 2-3 дня и оживлять бульоном, соусом или зеленью.",
                "Овощи разделить на две группы: часть запечь/бланшировать, часть оставить свежей.",
                "Смешать 1-2 соуса или заправки, чтобы одинаковая база не ощущалась одинаковой едой.",
            ]
        )

    @staticmethod
    def _quick_finish_description(meals: list[PlannedMeal]) -> str:
        lines = []
        for meal in meals:
            lines.append(f"{CookingPlannerService._meal_label(meal)} - {meal.recipe_name}.")
        lines.append("Эти блюда лучше не собирать заранее: приготовить или собрать ближе к приему пищи.")
        return "\n".join(lines)

    @staticmethod
    def _packing_description(modules: list[dict], quick_meals: list[PlannedMeal]) -> str:
        lines = ["Разложить порции по контейнерам и подписать: код, блюдо, дата приема пищи."]
        for module in modules:
            containers = module.get("containers") or []
            for container in containers:
                grams = f", {container['grams']} г" if container.get("grams") else ""
                if "кукси" in str(module.get("name") or "").casefold():
                    lines.append(
                        f"{container['label']}: готовое кукси{grams} — в контейнер положить лапшу, обжаренную говядину, овощи и омлет; залить охлажденным бульоном кукси, посыпать кунжутом и кинзой; {container['meal_label']}."
                    )
                else:
                    lines.append(
                        f"{container['label']}: {module['name']}{grams} — {container['meal_label']}; хранение: {module['storage']}."
                    )
        if quick_meals:
            for meal in quick_meals:
                grams = f", {meal.portion_grams} г" if meal.portion_grams else ""
                label = CookingPlannerService._container_code(meal)
                lines.append(f"{label}: {meal.recipe_name}{grams} — {CookingPlannerService._meal_label(meal)}; собрать ближе к еде.")
        return "\n".join(lines)

    def _packing_steps(self, session: dict, modules: list[dict], quick_meals: list[PlannedMeal]) -> list[dict]:
        lines = self._packing_description(modules, quick_meals).splitlines()
        header = lines[:1]
        items = lines[1:]
        chunks = self._packing_chunks(header, items)
        steps = []
        for index, chunk in enumerate(chunks, start=1):
            suffix = f" ({index}/{len(chunks)})" if len(chunks) > 1 else ""
            steps.append(
                {
                    "session_index": session["index"],
                    "title": f"Разложить готовое по контейнерам{suffix}",
                    "description": "\n".join(header + chunk),
                    "duration_minutes": 5 if len(chunks) > 1 else 10,
                    "is_parallel": False,
                    "parallel_group": session["index"],
                    "_order": 85000 + index,
                }
            )
        return steps

    def _module_packing_steps(self, session: dict, modules: list[dict], action_steps: list[dict]) -> list[dict]:
        steps: list[dict] = []
        orders_by_recipe: dict[str, float] = {}
        for step in action_steps:
            recipe_name = str(step.get("_recipe_name") or "")
            if not recipe_name:
                continue
            orders_by_recipe[recipe_name] = max(
                orders_by_recipe.get(recipe_name, 0.0),
                float(step.get("_order") or 0),
            )

        for module in modules:
            containers = [
                container
                for container in module.get("containers") or []
                if container.get("storage_location") != "later"
            ]
            if not containers:
                continue
            base_order = orders_by_recipe.get(str(module.get("name") or ""), 84000.0)
            steps.append(
                {
                    "session_index": session["index"],
                    "title": f"Разложить порции: {module['name']}",
                    "description": self._module_packing_description(module, containers),
                    "duration_minutes": 5,
                    "is_parallel": False,
                    "parallel_group": session["index"],
                    "_order": base_order + 0.1,
                    "_recipe_name": module["name"],
                }
            )
        return steps

    @staticmethod
    def _module_packing_description(module: dict, containers: list[dict]) -> str:
        location_titles = {
            "fridge": "холодильник",
            "freezer": "морозилку",
            "pantry": "шкаф",
        }
        lines = [
            "Готовое блюдо разложить сразу: подписать код, дату и порцию, затем убрать в хранение.",
        ]
        for container in containers:
            grams = f", {container['grams']} г" if container.get("grams") else ""
            location = location_titles.get(container.get("storage_location"), "холодильник")
            lines.append(
                f"{container['label']}: {module['name']}{grams} - {container['meal_label']}; убрать в {location}."
            )
        return "\n".join(lines)

    @staticmethod
    def _packing_chunks(header: list[str], items: list[str]) -> list[list[str]]:
        chunks: list[list[str]] = []
        current: list[str] = []
        max_description_chars = 920
        max_items = 7
        for item in items:
            candidate = current + [item]
            candidate_text = "\n".join(header + candidate)
            if current and (len(candidate) > max_items or len(candidate_text) > max_description_chars):
                chunks.append(current)
                current = [item]
            else:
                current = candidate
        if current:
            chunks.append(current)
        return chunks or [[]]

    @staticmethod
    def _step_rank(title: str) -> int:
        if "старт" in title:
            return 0
        if "Гарниры" in title:
            return 80
        if "Быстрые" in title:
            return 90
        if "Разложить" in title:
            return 100
        return 50

    @staticmethod
    def _strategy_label(profile: Profile) -> str:
        frequency = str(profile.cooking_frequency or "twice_a_week").casefold()
        if any(token in frequency for token in ("every", "daily", "кажд")):
            return "короткая готовка каждый день"
        if any(token in frequency for token in ("once", "1", "один")):
            return "одна большая заготовка на неделю"
        return "две заготовки в неделю"

    @staticmethod
    def _attach_step_numbers(meta: dict, steps: list[dict]) -> None:
        by_session: dict[int, list[int]] = {}
        for step in steps:
            step_number = step.get("step_number")
            if not step_number:
                continue
            by_session.setdefault(step["session_index"], []).append(step_number)
        for session in meta.get("sessions", []):
            session["step_numbers"] = by_session.get(session["index"], [])
