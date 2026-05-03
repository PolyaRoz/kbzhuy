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
import copy
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.models.plan import MealPlan, DayPlan, Meal
from app.models.container import Container
from app.models.cooking import CookingPlan
from app.models.shopping import ShoppingList, ShoppingItem
from app.models.profile import Profile
from app.models.post import PlanRecipeRequest
from app.models.storage import InventoryItem
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

CYRILLIC = "а-яё"

PREFERENCE_GROUPS: dict[str, tuple[str, ...]] = {
    "alcohol": (
        "алкогол", "вино", "вина", "вином", "вине",
        "игрист", "шампан", "пиво", "пивн", "сидр", "водка", "ром", "коньяк", "бренди",
        "виски", "ликер", "ликёр", "марсала", "саке", "текила", "джин",
    ),
    "pork": (
        "свинина", "свинину", "свинин", "свиная", "свиной", "свиные", "свино",
        "бекон", "ветчина", "хамон", "грудинка", "корейка", "окорок",
    ),
    "beef": ("говядина", "говяж", "телятина", "теляч"),
    "fish": (
        "рыба", "рыбу", "рыбн", "треска", "судак", "лосось", "семга", "сёмга", "форель",
        "горбуша", "тунец", "скумбрия", "сайра", "хек", "минтай", "дорадо", "сибас",
    ),
    "seafood": (
        "морепродукт", "кревет", "мидии", "мидия", "кальмар", "осьминог", "краб",
        "гребеш", "устриц",
    ),
    "dairy": (
        "лактоз", "молоко", "молоч", "сливки", "сливоч", "сметана", "йогурт", "кефир",
        "творог", "сыр", "моцарелла", "пармезан", "рикотта", "брынза", "маскарпоне",
    ),
    "eggs": ("яйцо", "яйца", "яичный", "желток", "белок"),
    "nuts": (
        "орех", "орехи", "миндаль", "фундук", "кешью", "арахис", "грецк", "фисташ",
        "пекан", "макадам",
    ),
    "gluten": (
        "глютен", "пшениц", "пшенич", "мука", "манка", "булгур", "кус-кус", "кускус",
        "хлеб", "лаваш", "паста", "лапша", "спагетти", "макарон",
    ),
    "mushrooms": ("гриб", "грибы", "шампиньон", "лисичк", "вешенк"),
    "chicken": ("курица", "курин", "цыплен", "индейк", "птица"),
    "apple": ("яблок", "яблоч"),
    "pear": ("груш",),
}

PREFERENCE_GROUP_ALIASES: dict[str, tuple[str, ...]] = {
    "alcohol": ("алкогол", "вино", "шампан", "пиво"),
    "pork": ("свинин", "свинину", "свиная", "свиной", "бекон", "ветчина"),
    "beef": ("говядин", "говяж", "телятина"),
    "fish": ("рыба", "рыбу", "рыбн"),
    "seafood": ("морепродукт", "кревет", "мидии", "кальмар"),
    "dairy": ("лактоз", "молоч", "молоко", "сыр", "сливки", "творог"),
    "eggs": ("яйц", "яичн", "желток", "белок"),
    "nuts": ("орех", "миндаль", "арахис", "фундук", "кешью"),
    "gluten": ("глютен", "пшениц", "мука", "хлеб", "паста", "лапша"),
    "mushrooms": ("гриб", "шампиньон"),
    "chicken": ("куриц", "курин", "птица", "индейк"),
    "apple": ("яблок", "яблоч"),
    "pear": ("груш",),
}


def _load_recipes() -> list[dict]:
    global _RECIPES
    if _RECIPES is None:
        markdown_path = next((path for path in MARKDOWN_RECIPE_PATHS if path.exists()), None)
        if markdown_path:
            _RECIPES = _with_safe_substitution_variants(_load_markdown_recipes(markdown_path))
            if _RECIPES:
                return _RECIPES

        json_path = next((path for path in JSON_RECIPES_PATHS if path.exists()), None)
        if not json_path:
            raise FileNotFoundError("Recipe database not found")
        _RECIPES = _with_safe_substitution_variants(json.loads(json_path.read_text(encoding="utf-8")))
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


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def _preference_group_ids(raw_terms: list[str]) -> set[str]:
    group_ids: set[str] = set()
    for raw in raw_terms:
        term = str(raw or "").casefold()
        if not term:
            continue
        for group_id, aliases in PREFERENCE_GROUP_ALIASES.items():
            if any(alias in term for alias in aliases):
                group_ids.add(group_id)
    return group_ids


def _compile_preference_patterns(raw_terms: list[str]) -> list[re.Pattern]:
    terms: set[str] = set()
    for raw in raw_terms:
        term = re.sub(r"\s+", " ", str(raw or "").casefold()).strip()
        if len(term) >= 3:
            terms.add(term)

    for group_id in _preference_group_ids(raw_terms):
        terms.update(PREFERENCE_GROUPS.get(group_id, ()))

    patterns = []
    exact_terms = {
        "вино", "вина", "вином", "вине", "пиво", "сидр", "водка", "ром", "коньяк",
        "бренди", "виски", "ликер", "ликёр", "саке", "текила", "джин",
    }
    for term in sorted(terms, key=len, reverse=True):
        escaped = re.escape(term)
        if re.search(r"[а-яё]", term):
            patterns.append(re.compile(rf"(?<![{CYRILLIC}]){escaped}(?![{CYRILLIC}])", re.I))
            if term not in exact_terms:
                patterns.append(re.compile(escaped, re.I))
        else:
            patterns.append(re.compile(escaped, re.I))
    return patterns


def _recipe_search_text(recipe: dict) -> str:
    parts = [
        str(recipe.get("name") or ""),
        " ".join(str(tag) for tag in recipe.get("tags", [])),
        " ".join(str(tag) for tag in recipe.get("meal_types", [])),
    ]
    for ingredient in recipe.get("ingredients", []):
        parts.append(str(ingredient.get("name") or ""))
    return " ".join(parts).casefold()


def _recipe_matches_preference_patterns(recipe: dict, patterns: list[re.Pattern]) -> bool:
    if not patterns:
        return False
    text = _recipe_search_text(recipe)
    return any(pattern.search(text) for pattern in patterns)


def _replace_text_preserving_case(text: str, replacements: tuple[tuple[str, str], ...]) -> str:
    result = text
    for source, target in replacements:
        result = re.sub(source, target, result, flags=re.I)
    return result


APPLE_TO_PEAR_REPLACEMENTS = (
    (r"Яблоки", "Груши"),
    (r"яблоки", "груши"),
    (r"Яблоко", "Груша"),
    (r"яблоко", "груша"),
    (r"яблочный", "грушевый"),
    (r"яблочная", "грушевая"),
    (r"яблочное", "грушевое"),
    (r"яблочного", "грушевого"),
    (r"яблока", "груши"),
    (r"яблок", "груш"),
)

PEAR_TO_APPLE_REPLACEMENTS = (
    (r"Груши", "Яблоки"),
    (r"груши", "яблоки"),
    (r"Груша", "Яблоко"),
    (r"груша", "яблоко"),
    (r"грушевый", "яблочный"),
    (r"грушевая", "яблочная"),
    (r"грушевое", "яблочное"),
    (r"грушевого", "яблочного"),
    (r"груш", "яблок"),
)


def _substituted_recipe(recipe: dict, replacements: tuple[tuple[str, str], ...], new_id: int) -> dict | None:
    text = _recipe_search_text(recipe)
    if not any(re.search(source, text, flags=re.I) for source, _target in replacements):
        return None

    variant = copy.deepcopy(recipe)
    variant["id"] = new_id
    changed = False

    original_name = str(variant.get("name") or "")
    variant["name"] = _replace_text_preserving_case(str(variant.get("name") or ""), replacements)
    changed = changed or variant["name"] != original_name

    variant["tags"] = [
        _replace_text_preserving_case(str(tag), replacements)
        for tag in variant.get("tags", [])
    ]
    for ingredient in variant.get("ingredients", []):
        original_ingredient_name = str(ingredient.get("name") or "")
        ingredient["name"] = _replace_text_preserving_case(str(ingredient.get("name") or ""), replacements)
        changed = changed or ingredient["name"] != original_ingredient_name
    for step in variant.get("steps", []):
        if isinstance(step, dict) and step.get("text"):
            original_step = str(step["text"])
            step["text"] = _replace_text_preserving_case(str(step["text"]), replacements)
            changed = changed or step["text"] != original_step
    if not changed:
        return None
    if variant["name"] == recipe.get("name"):
        marker = "грушей" if replacements is APPLE_TO_PEAR_REPLACEMENTS else "яблоком"
        variant["name"] = f"{variant['name']} с {marker}"
    return variant


def _with_safe_substitution_variants(recipes: list[dict]) -> list[dict]:
    result = list(recipes)
    next_id = max((int(recipe.get("id") or 0) for recipe in result), default=0) + 1
    existing_names = {str(recipe.get("name") or "").casefold() for recipe in result}

    for recipe in recipes:
        for replacements in (APPLE_TO_PEAR_REPLACEMENTS, PEAR_TO_APPLE_REPLACEMENTS):
            variant = _substituted_recipe(recipe, replacements, next_id)
            if not variant:
                continue
            key = variant["name"].casefold()
            if key in existing_names:
                continue
            result.append(variant)
            existing_names.add(key)
            next_id += 1
    return result


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


CONTAINER_WEEKDAY_CODES = {
    0: "ПН",
    1: "ВТ",
    2: "СР",
    3: "ЧТ",
    4: "ПТ",
    5: "СБ",
    6: "ВС",
}


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

        shopping_agg: dict[str, dict] = {}  # name → {qty, unit, category}
        meal_schedule = self._profile_meal_schedule(profile)
        used_week_names: dict[str, int] = {}

        # Load titles the user queued from the Tray feed ("add to plan" button).
        # These get a score boost in the beam search so they appear in the week.
        pending_requests_result = await self.session.execute(
            select(PlanRecipeRequest)
            .where(PlanRecipeRequest.user_id == user_id)
            .where(PlanRecipeRequest.used_in_plan_id.is_(None))
        )
        pending_requests = pending_requests_result.scalars().all()
        preferred_names: set[str] = {req.title.casefold() for req in pending_requests}

        for day_offset in range(7):
            day_date = week_start + timedelta(days=day_offset)
            day_plan = DayPlan(
                plan_id=plan.id,
                date=day_date,
            )
            self.session.add(day_plan)
            await self.session.flush()

            day_meals = self._compose_day_meals(
                meal_schedule, targets, profile, used_week_names, preferred_names=preferred_names
            )
            for scheduled_meal, recipe in day_meals:
                container = Container(
                    user_id=user_id,
                    label=self._container_label(day_date, scheduled_meal, meal_schedule),
                    plan_id=plan.id,
                    status="filled",
                    contents_description=recipe["name"],
                    heating_instructions=recipe.get("heating_instructions"),
                    expiry_date=day_date + timedelta(days=3),
                    kbzhu=recipe["kbzhu_per_serving"],
                )
                self.session.add(container)
                await self.session.flush()

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

        # Mark all pending plan-recipe requests as consumed by this plan
        if pending_requests:
            pending_ids = [req.id for req in pending_requests]
            await self.session.execute(
                update(PlanRecipeRequest)
                .where(PlanRecipeRequest.id.in_(pending_ids))
                .values(used_in_plan_id=plan.id)
            )
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

    async def _delete_cooking_plan(self, plan_id: int) -> None:
        result = await self.session.execute(
            select(CookingPlan).where(CookingPlan.plan_id == plan_id)
        )
        cooking_plan = result.scalar_one_or_none()
        if cooking_plan is not None:
            await self.session.delete(cooking_plan)
            await self.session.flush()

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
            candidates = self._safe_fallback_recipes(profile, excluded)
        recipe = self._pick_replacement_recipe(meal, candidates, targets)
        if recipe is None:
            raise ValueError("Recipe not found")

        container = meal.container
        if container is None:
            container = Container(
                user_id=user_id,
                label=self._container_label(meal.day.date, schedule_meal, schedule),
                plan_id=meal.day.plan_id,
                status="filled",
                expiry_date=meal.day.date + timedelta(days=3),
            )
            self.session.add(container)
            await self.session.flush()
            meal.container_id = container.id

        container.label = self._container_label(meal.day.date, schedule_meal, schedule)
        container.contents_description = recipe["name"]
        container.heating_instructions = recipe.get("heating_instructions")
        container.kbzhu = recipe["kbzhu_per_serving"]
        meal.kbzhu_actual = recipe["kbzhu_per_serving"]
        meal.status = "planned"

        await self.session.flush()
        await self._sync_shopping_list(meal.day.plan_id, user_id, meal.day.plan.period_start)
        await self._delete_cooking_plan(meal.day.plan_id)
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
                    label=self._container_label(day.date, scheduled_meal, meal_schedule),
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
            container.label = self._container_label(day.date, scheduled_meal, meal_schedule)
            container.contents_description = recipe["name"]
            container.heating_instructions = recipe.get("heating_instructions")
            container.kbzhu = recipe["kbzhu_per_serving"]

        for meal in existing_meals[len(day_meals):]:
            if meal.container:
                await self.session.delete(meal.container)
            await self.session.delete(meal)

        await self.session.flush()
        await self._sync_shopping_list(day.plan_id, user_id, day.plan.period_start)
        await self._delete_cooking_plan(day.plan_id)
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
                    "order": index,
                }
                for index, meal in enumerate(raw_meals)
                if isinstance(meal, dict)
            ]
        return [
            {"id": meal_type, "name": self._default_meal_name(meal_type), "time": time, "order": index}
            for index, (meal_type, time) in enumerate(MEAL_SCHEDULE)
        ]

    @staticmethod
    def _container_label(day_date: date, scheduled_meal: dict, meal_schedule: list[dict]) -> str:
        fallback_order = next(
            (index for index, item in enumerate(meal_schedule) if item["id"] == scheduled_meal.get("id")),
            0,
        )
        meal_order = int(scheduled_meal.get("order", fallback_order)) + 1
        weekday = CONTAINER_WEEKDAY_CODES.get(day_date.weekday(), "")
        return f"{meal_order} {weekday}".strip()

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
        avoid_patterns = _compile_preference_patterns(avoid)
        equipment = {str(item).casefold() for item in (profile.kitchen_equipment or [])}
        max_minutes = None
        if isinstance(profile.cooking_time_budget, dict):
            raw_minutes = profile.cooking_time_budget.get("minutes")
            if isinstance(raw_minutes, (int, float)) and raw_minutes > 0:
                period = str(profile.cooking_time_budget.get("period") or "week").casefold()
                frequency = str(profile.cooking_frequency or "twice_a_week").casefold()
                if period == "day":
                    max_minutes = raw_minutes
                elif any(token in frequency for token in ("once", "1", "один")):
                    max_minutes = max(25, min(75, raw_minutes / 2))
                elif any(token in frequency for token in ("twice", "2", "два")):
                    max_minutes = max(25, min(65, raw_minutes / 3))
                else:
                    max_minutes = max(20, min(60, raw_minutes / 5))

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
            if _recipe_matches_preference_patterns(recipe, avoid_patterns):
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

    def _safe_fallback_recipes(
        self,
        profile: Profile,
        excluded: set[str] | None = None,
    ) -> list[dict]:
        avoid = [*(profile.allergies or []), *(profile.disliked_foods or [])]
        avoid_patterns = _compile_preference_patterns(avoid)
        excluded = excluded or set()
        return [
            recipe
            for recipe in _load_recipes()
            if _valid_recipe(recipe)
            and recipe["name"].casefold() not in excluded
            and not _recipe_matches_preference_patterns(recipe, avoid_patterns)
        ]

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

    @staticmethod
    def _is_preferred(name: str, preferred_names: set[str]) -> bool:
        """Loose match: post title ⊆ recipe name or recipe name ⊆ post title."""
        name_lower = name.casefold()
        return any(
            pref in name_lower or name_lower in pref
            for pref in preferred_names
        )

    def _compose_day_meals(
        self,
        meal_schedule: list[dict],
        targets: NutriTarget,
        profile: Profile,
        used_week_names: dict[str, int],
        exclude_names: set[str] | None = None,
        diversity_boost: bool = False,
        preferred_names: set[str] | None = None,
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
                candidates = self._safe_fallback_recipes(profile, excluded)
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
                    duplicate_penalty = 0.9 if name in names else 0
                    week_penalty = self._weekly_repeat_penalty(
                        profile,
                        used_week_names.get(name, 0),
                        diversity_boost=diversity_boost,
                    )
                    # Strong negative bonus for recipes the user explicitly requested
                    # (applies only on first use; subsequent days rely on natural КБЖУ fit)
                    preferred_boost = (
                        -2.0
                        if preferred_names
                        and used_week_names.get(name, 0) == 0
                        and self._is_preferred(name, preferred_names)
                        else 0.0
                    )
                    score = self._score_totals(next_totals, partial_target) + duplicate_penalty + week_penalty + preferred_boost + _random_tiebreak()
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
    def _weekly_repeat_penalty(profile: Profile, previous_count: int, diversity_boost: bool = False) -> float:
        if previous_count <= 0:
            return 0.0
        if diversity_boost:
            return min(0.16 * previous_count, 0.56)

        frequency = str(profile.cooking_frequency or "twice_a_week").casefold()
        if any(token in frequency for token in ("once", "1", "один")):
            if previous_count <= 2:
                return -0.85
            if previous_count == 3:
                return -0.45
            if previous_count == 4:
                return 0.08
            return min(0.30 * (previous_count - 4), 0.90)
        if any(token in frequency for token in ("twice", "2", "два")):
            if previous_count == 1:
                return -0.42
            if previous_count == 2:
                return -0.16
            return min(0.22 * (previous_count - 2), 0.70)
        if any(token in frequency for token in ("every", "daily", "кажд")):
            return min(0.08 * previous_count, 0.30)
        if previous_count == 1:
            return -0.10
        return min(0.14 * (previous_count - 1), 0.45)

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
            candidates = self._safe_fallback_recipes(profile, excluded) if profile else [
                recipe for recipe in _load_recipes()
                if _valid_recipe(recipe) and recipe["name"].casefold() not in excluded
            ]
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
            "ст.л": "мл",
            "ст л": "мл",
            "столовая ложка": "мл",
            "столовые ложки": "мл",
            "ч. л.": "мл",
            "ч.л.": "мл",
            "ч.л": "мл",
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
        clean_lower = clean.casefold()
        if "вода" in clean_lower or "кипят" in clean_lower:
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
        if re.search(r"\bогур", clean):
            return "Огурцы"
        if "кабач" in clean:
            return "Кабачок"
        if "баклаж" in clean:
            return "Баклажан"
        if "картоф" in clean:
            return "Картофель"
        if "шпинат" in clean:
            return "Шпинат"
        if "айсберг" in clean:
            return "Салат айсберг"
        if "фенхел" in clean:
            return "Фенхель"
        if "салатн" in clean and "лист" in clean:
            return "Салатные листья"
        if "салат микс" in clean or "микс салат" in clean:
            return "Салатный микс"
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
        if "сельдер" in clean and "стеб" in clean:
            return "Сельдерей стеблевой"
        if "сельдер" in clean:
            return "Сельдерей"
        if "свекл" in clean:
            return "Свекла"
        if "тыкв" in clean:
            return "Тыква"
        if "цветн" in clean and "капуст" in clean:
            return "Цветная капуста"
        if "белокочан" in clean and "капуст" in clean:
            return "Капуста белокочанная"
        if "лисич" in clean:
            return "Лисички"

        if "томатн паст" in clean:
            return "Томатная паста"
        if "протерт" in clean and "томат" in clean:
            return "Томаты протертые"
        if "вялен" in clean and "томат" in clean:
            return "Томаты вяленые"
        if clean == "черри":
            return "Томаты черри"
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
        if "яблок" in clean:
            return "Яблоки"
        if "груш" in clean:
            return "Груши"
        if "абрикос" in clean:
            return "Абрикосы"
        if "слив" in clean:
            return "Сливы"
        if "виноград" in clean:
            return "Виноград"
        if "инжир" in clean:
            return "Инжир"
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
        if "кориц" in clean:
            return "Корица"
        if "кардамон" in clean:
            return "Кардамон"
        if "гвоздик" in clean:
            return "Гвоздика"
        if re.search(r"\bзира\b", clean):
            return "Зира"

        if re.search(r"\bвино\b", clean):
            if "игрист" in clean:
                return "Вино игристое"
            if "сух" in clean and "бел" in clean:
                return "Вино белое сухое"
            if "сух" in clean and "красн" in clean:
                return "Вино красное сухое"
            return "Вино"

        if "соус" in clean:
            return clean[:1].upper() + clean[1:]
        if "рыбн" in clean and "набор" in clean:
            return "Рыбный набор для бульона"
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
        if "майонез" in clean:
            return "Майонез"
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
        if "мука рис" in clean:
            return "Мука рисовая"
        if "мука кукуруз" in clean:
            return "Мука кукурузная"
        if "мука миндал" in clean:
            return "Мука миндальная"
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
        if "чай" in clean and "жасмин" in clean:
            return "Чай жасминовый"
        if "жасмин" in clean and "рис" in clean:
            return "Рис жасмин"
        if "жасмин" in clean:
            return "Чай жасминовый"
        if "пшен" in clean:
            return "Пшено"
        if "греч" in clean:
            return "Гречка"
        if "басмати" in clean and "рис" in clean:
            return "Рис басмати"
        if clean == "рис":
            return "Рис"
        if "кус-кус" in clean or "кускус" in clean:
            return "Кус-кус"
        if "удон" in clean:
            return "Лапша удон"
        if "паста" in clean or "каннеллони" in clean:
            if "арахис" in clean:
                return "Арахисовая паста"
            if "томат" in clean:
                return "Томатная паста"
            return "Паста"
        if "багет" in clean:
            return "Багет"
        if "лаваш" in clean:
            return "Лаваш"
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
        if "тесто фило" in clean:
            return "Тесто фило"
        if "тесто" in clean:
            return "Тесто"
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
        if "арахис" in clean:
            return "Арахис"
        if "миндал" in clean and "лепест" in clean:
            return "Лепестки миндаля"
        if "миндал" in clean:
            return "Миндаль"
        if re.fullmatch(r"мак", clean):
            return "Мак"
        if "грецк" in clean and "орех" in clean:
            return "Орех грецкий"
        if "пектин" in clean:
            return "Пектин"
        if "крабов" in clean and "палоч" in clean:
            return "Крабовые палочки"
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
        if "прованск" in clean and "трав" in clean:
            return "Прованские травы"
        if "хмели-сунели" in clean or "хмели сунели" in clean:
            return "Хмели-сунели"
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
        if clean == "белок":
            return "Яичный белок"
        if clean == "желток":
            return "Яичный желток"

        if any(word in clean for word in ("курин", "индейк", "говядин", "говяж", "свинин", "свин", "печен", "фарш")):
            if "фарш говяж" in clean:
                return "Фарш говяжий"
            if "фарш свино" in clean:
                return "Фарш свино-говяжий"
            return clean[:1].upper() + clean[1:]
        white_fish_terms = ("судак", "треск", "тиляп", "тилап", "хек", "минта", "пикш", "дорад", "сибас")
        red_fish_terms = ("лосос", "семг", "форел", "горбуш", "кета")
        if "филе" in clean:
            if any(term in clean for term in white_fish_terms) or "белой рыбы" in clean or "белая рыба" in clean:
                return "Филе белой рыбы"
            if any(term in clean for term in red_fish_terms) or "красной рыбы" in clean or "красная рыба" in clean:
                return "Филе красной рыбы"
        if any(term in clean for term in white_fish_terms) or clean in {"рыбы", "рыба", "белой рыбы", "белая рыба"}:
            return "Белая рыба"
        if any(term in clean for term in red_fish_terms) or clean in {"красной рыбы", "красная рыба"}:
            return "Красная рыба"
        if "сайр" in clean:
            return "Сайра"
        if "горбуш" in clean:
            return "Горбуша"
        if any(word in clean for word in ("кревет", "рыб", "треск", "семг", "лосос")) or re.search(r"\bмид", clean):
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
        is_teaspoon = raw in {"ч. л.", "ч.л.", "ч.л", "ч л", "чайная ложка", "чайные ложки"}
        is_tablespoon = raw in {"ст. л.", "ст.л.", "ст.л", "ст л", "столовая ложка", "столовые ложки"}
        is_glass = raw in {"стакан", "стакана", "стаканов"}
        factor = 1.0
        if raw in {"кг", "килограмм", "килограмма"}:
            factor = 1000.0
        elif raw in {"л", "литр", "литра"}:
            factor = 1000.0
        elif is_glass:
            factor = 250.0
        elif is_tablespoon:
            factor = 15.0
        elif is_teaspoon:
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
            "Имбирь": 30.0,
            "Картофель": 150.0,
            "Кабачок": 250.0,
            "Баклажан": 250.0,
            "Апельсин": 180.0,
            "Банан": 120.0,
            "Груши": 160.0,
            "Лимон": 120.0,
            "Лайм": 60.0,
            "Сливы": 35.0,
            "Вишня": 8.0,
            "Гранат": 300.0,
            "Редис": 20.0,
            "Ананас": 900.0,
            "Шпинат": 50.0,
            "Сельдерей стеблевой": 40.0,
            "Горбуша": 250.0,
            "Тунец": 185.0,
            "Куриное филе": 250.0,
            "Куриные бедра": 250.0,
            "Белая рыба": 300.0,
            "Красная рыба": 300.0,
            "Филе белой рыбы": 180.0,
            "Филе красной рыбы": 180.0,
            "Багет": 250.0,
        }
        bunch_to_grams = {
            "Лук зеленый": 50.0,
            "Петрушка": 30.0,
            "Укроп": 30.0,
            "Базилик": 30.0,
            "Кинза": 30.0,
            "Мята": 20.0,
        }
        teaspoon_to_grams = {
            "Имбирь": 2.0,
            "Кориандр": 2.0,
            "Кориандр молотый": 2.0,
            "Паприка": 2.0,
            "Куркума": 2.0,
            "Сода": 5.0,
            "Корица": 3.0,
            "Кардамон": 2.0,
            "Гвоздика": 1.0,
            "Зира": 2.0,
            "Ваниль": 5.0,
            "Специи для плова": 2.0,
            "Хмели-сунели": 2.0,
            "Прованские травы": 2.0,
            "Орегано": 1.0,
            "Перец черный": 2.0,
        }
        pantry_pack_to_grams = {
            "Пшено": 80.0,
            "Паста": 400.0,
            "Панировочные сухари": 100.0,
            "Молоко": 1000.0,
            "Мука пшеничная": 1000.0,
            "Пармезан": 100.0,
            "Сыр": 200.0,
            "Сыр твердый/полутвердый": 200.0,
            "Сметана": 180.0,
            "Дрожжи": 7.0,
            "Ваниль": 5.0,
            "Орегано": 10.0,
            "Кунжут": 30.0,
            "Мед": 250.0,
        }
        fruits_ml_to_g = {
            "Сливы",
            "Абрикосы",
            "Ананас",
            "Виноград",
            "Яблоки",
            "Груши",
            "Апельсин",
            "Банан",
            "Арбуз",
            "Клубника",
            "Вишня",
            "Малина",
            "Голубика",
            "Клюква",
            "Смородина",
            "Изюм",
            "Гранат",
            "Лайм",
            "Лимон",
        }
        liquids_to_ml = {
            "Молоко",
            "Кефир",
            "Сливки 10%",
            "Сливки 20%",
            "Сливки 30%",
            "Сливки 33%",
            "Бульон куриный",
            "Бульон рыбный",
            "Соевый соус",
            "Уксус",
            "Вино белое сухое",
        }

        if name == "Яйца куриные" and normalized_unit == "г":
            return quantity / 50.0, "шт"
        if name == "Яйца перепелиные" and normalized_unit == "г":
            return quantity / 12.0, "шт"
        if is_teaspoon and name in teaspoon_to_grams:
            return (quantity / 5.0) * teaspoon_to_grams[name], "г"
        if normalized_unit == "шт" and name in piece_to_grams:
            return quantity * piece_to_grams[name], "г"
        if normalized_unit == "пучок" and name in bunch_to_grams:
            return quantity * bunch_to_grams[name], "г"
        if normalized_unit == "шт" and name in pantry_pack_to_grams:
            return quantity * pantry_pack_to_grams[name], "г" if name != "Молоко" else "мл"
        if name in liquids_to_ml and normalized_unit == "г":
            return quantity, "мл"
        if name == "Мед" and normalized_unit == "мл":
            return quantity * 1.4, "г"
        if name == "Лимонный сок" and normalized_unit == "г":
            return quantity, "мл"
        if name == "Томаты протертые" and normalized_unit == "мл":
            return quantity, "г"
        if name in fruits_ml_to_g and normalized_unit == "мл":
            return quantity, "г"
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
        if name in bunch_to_grams and normalized_unit == "шт":
            return quantity * bunch_to_grams[name], "г"
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
            value = round(quantity, 1) if 0 < quantity < 1 else round(quantity)
        else:
            value = round(quantity, 1)
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return f"{value} {unit}"

    @staticmethod
    def _is_meaningful_shopping_quantity(quantity: float, unit: str) -> bool:
        if quantity <= 0:
            return False
        if unit in {"г", "мл"}:
            return quantity >= 1.0
        if unit == "шт":
            return quantity >= 0.1
        return quantity > 0.01

    @staticmethod
    def _ingredient_category(name: str) -> str:
        lower = name.casefold()
        if _contains_any(lower, (r"\bяйц", r"\bбелок\b", r"\bжелток\b")):
            return "Яйца"
        if _contains_any(lower, (
            r"\bсоус\b",
            r"томатная паста",
            r"томаты протертые",
            r"\bбульон\b",
            r"\bвино\b",
            r"\bпиво\b",
            r"разрыхлитель",
            r"\bсироп",
            r"каперс",
            r"горчиц",
            r"желатин",
            r"дрожж",
            r"майонез",
            r"пектин",
        )):
            return "Соусы и добавки"
        if _contains_any(lower, (
            r"масло",
            r"\bсоль\b",
            r"\bсахар\b",
            r"\bмед\b",
            r"\bпаприка\b",
            r"\bкуркума\b",
            r"уксус",
            r"перец черный",
            r"розмарин",
            r"кориандр",
            r"\bкунжут\b",
            r"орегано",
            r"специи для плова",
            r"\bсода\b",
            r"ванил",
            r"смесь сушеных трав",
            r"прованские травы",
            r"хмели-сунели|хмели сунели",
            r"\bкорица\b",
            r"\bкардамон\b",
            r"\bгвоздика\b",
            r"\bзира\b",
            r"\bмак\b",
        )):
            return "Специи и масла"
        if _contains_any(lower, (
            r"курин",
            r"индейк",
            r"говядин|говяж",
            r"свинин|свин",
            r"печен",
            r"бекон",
            r"\bфарш\b",
            r"вырезк",
        )):
            return "Мясо и птица"
        if _contains_any(lower, (
            r"\bрыб",
            r"кревет",
            r"\bмид",
            r"лосос",
            r"треск",
            r"семг",
            r"горбуш",
            r"тун",
            r"сайр",
            r"крабов",
        )):
            return "Рыба и морепродукты"
        if _contains_any(lower, (
            r"кефир",
            r"молоко",
            r"йогурт",
            r"сливки",
            r"сметана",
            r"творог",
            r"моцарелл",
            r"пармезан",
            r"рикотт",
            r"\bсыр\b",
            r"брынз",
        )):
            return "Молочные продукты"
        if _contains_any(lower, (
            r"греч",
            r"\bрис\b",
            r"лапш",
            r"\bмука\b",
            r"\bкрупа\b",
            r"\bпшено\b",
            r"крахмал",
            r"чечевиц",
            r"\bнут\b",
            r"кус-кус|кускус",
            r"сухари",
            r"перловк",
            r"овсян",
            r"багет",
            r"\bпаста\b",
            r"каннеллони",
            r"\bтесто\b",
            r"лаваш",
        )):
            return "Крупы и хлеб"
        if _contains_any(lower, (
            r"гранатовый сок",
            r"апельсин",
            r"банан",
            r"клубник",
            r"лимон",
            r"лайм",
            r"арбуз",
            r"вишн",
            r"малин",
            r"голубик",
            r"клюкв",
            r"ананас",
            r"изюм",
            r"смородин",
            r"гранат",
            r"яблок",
            r"груш",
            r"абрикос",
            r"слив",
            r"виноград",
            r"инжир",
        )):
            return "Фрукты и ягоды"
        if _contains_any(lower, (
            r"\bлук\b",
            r"чеснок",
            r"морков",
            r"\bогур",
            r"кабач",
            r"баклаж",
            r"картоф",
            r"шпинат",
            r"салат",
            r"петруш",
            r"базилик",
            r"кинз",
            r"имбир",
            r"шампин",
            r"редис",
            r"перец болгар",
            r"томат",
            r"помидор",
            r"укроп",
            r"щавел",
            r"брокколи",
            r"мята",
            r"цукини",
            r"горошек",
            r"капуста пекин",
            r"капуста белокоч",
            r"цветная капуста",
            r"сельдер",
            r"свекл",
            r"тыкв",
            r"айсберг",
            r"фенхел",
            r"лисич",
        )):
            return "Овощи и зелень"
        if _contains_any(lower, (
            r"семеч",
            r"орех",
            r"фундук",
            r"кешью",
            r"миндал",
            r"арахис",
            r"кунжут",
            r"лепестки миндаля",
        )):
            return "Орехи и семечки"
        if _contains_any(lower, (r"\bсок\b", r"\bкофе\b", r"\bчай\b", r"комбуч")):
            return "Напитки"
        if _contains_any(lower, (r"какао", r"майонез")):
            return "Соусы и добавки"
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
            scaled_quantity = quantity * multiplier
            if not self._is_meaningful_shopping_quantity(scaled_quantity, unit):
                continue
            if key not in agg:
                agg[key] = {
                    "name": normalized_name,
                    "quantity": 0.0,
                    "unit": unit,
                    "category": self._ingredient_category(normalized_name),
                }
            agg[key]["quantity"] += scaled_quantity

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

        # Preserve checked/at_home state so re-syncing doesn't reset user's progress
        checked_state: dict[str, tuple[bool, bool]] = {}
        if existing is not None:
            for item in existing.items:
                key = f"{item.name}|{item.unit}"
                checked_state[key] = (bool(item.checked), bool(item.at_home))
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

        return await self._create_shopping_list(user_id, plan_id, week_start, shopping_agg, checked_state)

    async def _create_shopping_list(
        self,
        user_id: int,
        plan_id: int,
        week_start: date,
        agg: dict,
        checked_state: dict | None = None,
    ) -> ShoppingList:
        # Shopping list is built purely from the meal plan.
        # Inventory levels do NOT affect what appears here — only the user's own
        # checked/at_home choices (preserved via checked_state) determine visibility.
        # This ensures clearing storage never brings items back to the shopping list.
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
            if not self._is_meaningful_shopping_quantity(float(info["quantity"]), info["unit"]):
                continue
            key = f"{info['name']}|{info['unit']}"
            prev_checked, prev_at_home = (checked_state or {}).get(key, (False, False))
            self.session.add(
                ShoppingItem(
                    shopping_list_id=sl.id,
                    name=info["name"],
                    quantity=self._format_quantity(info["quantity"], info["unit"]),
                    unit=info["unit"],
                    category=info["category"],
                    priority=category_priority.get(info["category"], 10),
                    checked=prev_checked,
                    at_home=prev_at_home,
                )
            )

        return sl
