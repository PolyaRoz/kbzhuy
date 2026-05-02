from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.shopping import ShoppingItem
from app.models.storage import InventoryItem, StorageLocation
from app.services.meal_planner_service import MealPlannerService


class InventoryService:
    DEFAULT_LOCATIONS = {
        "fridge": "Холодильник",
        "freezer": "Морозилка",
        "pantry": "Шкаф",
    }

    def __init__(self, session: AsyncSession):
        self.session = session
        self.planner = MealPlannerService(session)

    async def ensure_default_locations(self, user_id: int) -> dict[str, StorageLocation]:
        result = await self.session.execute(
            select(StorageLocation)
            .where(StorageLocation.user_id == user_id)
        )
        locations = {loc.type: loc for loc in result.scalars().all()}
        created = False
        for loc_type, loc_name in self.DEFAULT_LOCATIONS.items():
            if loc_type not in locations:
                loc = StorageLocation(user_id=user_id, type=loc_type, name=loc_name)
                self.session.add(loc)
                locations[loc_type] = loc
                created = True
        if created:
            await self.session.flush()
        return locations

    @staticmethod
    def infer_location_type(category: str) -> str:
        pantry_categories = {
            "Крупы и хлеб",
            "Орехи и семечки",
            "Специи и масла",
            "Соусы и добавки",
            "Напитки",
        }
        if category in pantry_categories:
            return "pantry"
        return "fridge"

    async def normalize_item(
        self,
        name: str,
        quantity: float,
        unit: str,
        category: str | None = None,
    ) -> tuple[str, float, str, str]:
        canonical = self.planner._canonical_ingredient_name(name)
        if not canonical:
            canonical = name.strip()
        qty, norm_unit = self.planner._normalize_quantity(canonical, float(quantity or 0), unit)
        final_category = category or self.planner._ingredient_category(canonical)
        return canonical, qty, norm_unit, final_category

    async def upsert_item(
        self,
        *,
        user_id: int,
        name: str,
        quantity: float,
        unit: str,
        location_type: str | None = None,
        category: str | None = None,
        raw: bool = False,
    ) -> InventoryItem | None:
        if raw:
            # Skip normalization — preserve exact name/unit (e.g. for pre-cooked meals with container labels)
            canonical = name.strip()
            qty = float(quantity or 0)
            norm_unit = unit.strip()
            final_category = category or "Готовая еда"
        else:
            canonical, qty, norm_unit, final_category = await self.normalize_item(name, quantity, unit, category)
        if not canonical or qty <= 0:
            return None
        locations = await self.ensure_default_locations(user_id)
        loc_type = location_type or self.infer_location_type(final_category)
        location = locations[loc_type]

        result = await self.session.execute(
            select(InventoryItem)
            .where(InventoryItem.user_id == user_id)
            .where(InventoryItem.location_id == location.id)
            .where(InventoryItem.name == canonical)
            .where(InventoryItem.unit == norm_unit)
        )
        item = result.scalar_one_or_none()
        if item is None:
            item = InventoryItem(
                user_id=user_id,
                location_id=location.id,
                name=canonical,
                category=final_category,
                quantity=qty,
                unit=norm_unit,
            )
            self.session.add(item)
        else:
            item.quantity += qty
            item.category = final_category
        await self.session.flush()
        return item

    async def add_from_shopping_item(
        self,
        user_id: int,
        shopping_item: ShoppingItem,
        location_type: str | None = None,
    ) -> InventoryItem | None:
        try:
            quantity = float(str(shopping_item.quantity).split()[0].replace(",", "."))
        except Exception:
            quantity = 0.0
        return await self.upsert_item(
            user_id=user_id,
            name=shopping_item.name,
            quantity=quantity,
            unit=shopping_item.unit,
            location_type=location_type,
            category=shopping_item.category,
        )

    async def get_inventory(self, user_id: int) -> list[StorageLocation]:
        await self.ensure_default_locations(user_id)
        result = await self.session.execute(
            select(StorageLocation)
            .where(StorageLocation.user_id == user_id)
            .options(selectinload(StorageLocation.inventory_items))
            .order_by(StorageLocation.id)
        )
        return result.scalars().all()

    async def use_item(self, user_id: int, item_id: int, quantity: float) -> InventoryItem | None:
        result = await self.session.execute(
            select(InventoryItem)
            .where(InventoryItem.user_id == user_id)
            .where(InventoryItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            return None
        item.quantity = max(0.0, float(item.quantity) - float(quantity))
        if item.quantity <= 0:
            await self.session.delete(item)
            return None
        await self.session.flush()
        return item

    async def use_by_name(self, user_id: int, name: str, quantity: float, unit: str) -> float:
        canonical, qty, norm_unit, _category = await self.normalize_item(name, quantity, unit)
        if not canonical or qty <= 0:
            return 0.0
        result = await self.session.execute(
            select(InventoryItem)
            .join(StorageLocation, InventoryItem.location_id == StorageLocation.id)
            .where(InventoryItem.user_id == user_id)
            .where(InventoryItem.name == canonical)
            .where(InventoryItem.unit == norm_unit)
            .order_by(StorageLocation.type, InventoryItem.id)
        )
        remaining = qty
        used = 0.0
        for item in result.scalars().all():
            if remaining <= 0:
                break
            take = min(float(item.quantity or 0), remaining)
            item.quantity = max(0.0, float(item.quantity or 0) - take)
            remaining -= take
            used += take
            if item.quantity <= 0:
                await self.session.delete(item)
        await self.session.flush()
        return used

    async def update_item(
        self,
        user_id: int,
        item_id: int,
        *,
        location_type: str | None = None,
        quantity: float | None = None,
        unit: str | None = None,
    ) -> InventoryItem | None:
        result = await self.session.execute(
            select(InventoryItem)
            .where(InventoryItem.user_id == user_id)
            .where(InventoryItem.id == item_id)
            .options(selectinload(InventoryItem.location))
        )
        item = result.scalar_one_or_none()
        if item is None:
            return None
        if location_type:
            locations = await self.ensure_default_locations(user_id)
            item.location_id = locations[location_type].id
        if quantity is not None:
            item.quantity = max(0.0, float(quantity))
        if unit is not None:
            item.unit = unit
        if item.quantity <= 0:
            await self.session.delete(item)
            return None
        await self.session.flush()
        return item

    async def delete_by_location(self, user_id: int, location_type: str | None = None) -> int:
        """Delete all inventory items for a user, optionally filtered by location type."""
        locations = await self.ensure_default_locations(user_id)
        if location_type:
            loc = locations.get(location_type)
            if not loc:
                return 0
            result = await self.session.execute(
                select(InventoryItem)
                .where(InventoryItem.user_id == user_id)
                .where(InventoryItem.location_id == loc.id)
            )
        else:
            result = await self.session.execute(
                select(InventoryItem)
                .where(InventoryItem.user_id == user_id)
            )
        items = result.scalars().all()
        for item in items:
            await self.session.delete(item)
        await self.session.flush()
        return len(items)

    async def delete_item(self, user_id: int, item_id: int) -> bool:
        result = await self.session.execute(
            select(InventoryItem)
            .where(InventoryItem.user_id == user_id)
            .where(InventoryItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            return False
        await self.session.delete(item)
        await self.session.flush()
        return True

    async def aggregate_for_user(self, user_id: int) -> dict[tuple[str, str], float]:
        result = await self.session.execute(
            select(InventoryItem)
            .where(InventoryItem.user_id == user_id)
        )
        agg: dict[tuple[str, str], float] = {}
        for item in result.scalars().all():
            key = (item.name, item.unit)
            agg[key] = agg.get(key, 0.0) + float(item.quantity or 0)
        return agg
