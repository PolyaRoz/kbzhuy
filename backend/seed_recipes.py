"""
Загрузка рецептов и ингредиентов из JSON в БД.

Запуск:
    cd backend
    .venv\Scripts\python.exe seed_recipes.py
"""

import asyncio
import json
from pathlib import Path

from sqlalchemy import select, text

from app.core.database import async_session, engine, Base
from app.models.recipe import Recipe, Ingredient


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RECIPES_FILE = DATA_DIR / "recipes" / "basic_recipes.json"
PRODUCTS_FILE = DATA_DIR / "nutrition" / "products.json"

# Маппинг категорий продуктов по ключевым словам
CATEGORY_MAP = {
    "meat": ["куриная", "куриные", "фарш", "говядина"],
    "fish": ["лосось"],
    "dairy": ["яйца", "творог", "йогурт", "молоко"],
    "grains": ["гречка", "рис", "овсянка"],
    "vegetables": ["картофель", "огурец", "помидор", "брокколи", "шпинат", "лук", "морковь", "чеснок"],
    "oils": ["оливковое масло"],
    "nuts": ["грецкие орехи"],
    "other": ["мёд", "пиво"],
}


def guess_category(name: str) -> str:
    name_lower = name.lower()
    for cat, keywords in CATEGORY_MAP.items():
        for kw in keywords:
            if kw in name_lower:
                return cat
    return "other"


def guess_unit(name: str) -> str:
    name_lower = name.lower()
    if "масло" in name_lower:
        return "мл"
    if "яйца" in name_lower or "яйцо" in name_lower:
        return "шт"
    if "пиво" in name_lower:
        return "мл"
    return "г"


async def seed():
    # Загружаем JSON
    with open(PRODUCTS_FILE, encoding="utf-8") as f:
        products_data = json.load(f)
    with open(RECIPES_FILE, encoding="utf-8") as f:
        recipes_data = json.load(f)

    async with async_session() as session:
        # Проверяем, есть ли уже данные
        existing = (await session.execute(select(Recipe).limit(1))).scalar_one_or_none()
        if existing:
            print(f"БД уже содержит рецепты (первый: {existing.title}). Пропускаю.")
            return

        # 1. Загружаем ингредиенты
        ingredient_ids = {}
        for product in products_data:
            name = product["name"]
            ingredient = Ingredient(
                name=name,
                category=guess_category(name),
                unit=guess_unit(name),
                kbzhu_per_100g={
                    "kcal": product["kcal_per_100g"],
                    "protein": product["protein"],
                    "fat": product["fat"],
                    "carbs": product["carbs"],
                },
                avg_price_rub=None,
            )
            session.add(ingredient)
            await session.flush()
            ingredient_ids[name] = ingredient.id
            print(f"  + Ингредиент: {name} (id={ingredient.id})")

        # 2. Загружаем рецепты
        for r in recipes_data:
            # Преобразуем ingredients в формат модели
            ingredients_json = []
            for ing in r["ingredients"]:
                name = ing["name"]
                # Пытаемся найти ingredient_id по точному или частичному совпадению
                ing_id = ingredient_ids.get(name)
                if not ing_id:
                    for db_name, db_id in ingredient_ids.items():
                        if db_name.lower() in name.lower() or name.lower() in db_name.lower():
                            ing_id = db_id
                            break
                ingredients_json.append({
                    "ingredient_id": ing_id,
                    "name": name,
                    "grams": ing["quantity"],
                    "unit": ing.get("unit", "г"),
                })

            # Объединяем tags и meal_types
            tags = list(set(r.get("tags", []) + r.get("meal_types", [])))

            recipe = Recipe(
                title=r["name"],
                ingredients=ingredients_json,
                steps=[],  # В JSON нет шагов — будут добавлены позже
                kbzhu_per_serving=r["kbzhu_per_serving"],
                tags=tags,
                time_min=r.get("prep_time_minutes", 0) + r.get("cook_time_minutes", 0),
                servings=r.get("servings", 1),
                source="basic_recipes.json",
                storage_instructions=r.get("storage_instructions"),
                heating_instructions=r.get("heating_instructions"),
            )
            session.add(recipe)
            await session.flush()
            print(f"  + Рецепт: {recipe.title} (id={recipe.id})")

        await session.commit()
        print(f"\nГотово: {len(products_data)} ингредиентов, {len(recipes_data)} рецептов.")


if __name__ == "__main__":
    asyncio.run(seed())
