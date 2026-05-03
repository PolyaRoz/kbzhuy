"""
Simple rule-based agent.
Handles everyday nutrition questions without a LLM API key.
Falls back to "in development" for unrecognised queries.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.container import Container
from app.models.plan import DayPlan, MealPlan

# ── Labels ──────────────────────────────────────────────────────────────── #

MEAL_ORDER: dict[str, int] = {
    "breakfast": 0,
    "snack": 1,
    "lunch": 2,
    "snack_2": 3,
    "dinner": 4,
}

MEAL_LABELS: dict[str, str] = {
    "breakfast": "завтрак",
    "snack": "перекус",
    "lunch": "обед",
    "snack_2": "второй перекус",
    "dinner": "ужин",
}

STATUS_ICON: dict[str, str] = {
    "done": "✅",
    "skipped": "⏭",
    "planned": "⏳",
}

# ── Intent detection ─────────────────────────────────────────────────────── #


def _norm(text: str) -> str:
    return text.lower().strip()


# Tokenise by Cyrillic/Latin/digits — returns list of word stems
def _tokens(msg: str) -> list[str]:
    return re.findall(r"[а-яёa-z0-9]+", msg)


def _any(msg: str, prefixes: list[str]) -> bool:
    """Token prefix matching — handles Russian inflection.
    'ресторан' matches 'ресторане' (tok starts with prefix),
    but 'перенос' does NOT match 'непереносимости' (tok doesn't start with it).
    """
    toks = _tokens(msg)
    return any(tok.startswith(p) for p in prefixes for tok in toks)


def _phrase(msg: str, phrases: list[str]) -> bool:
    """Substring matching on the full normalised message — for multi-word phrases."""
    return any(p in msg for p in phrases)


def detect_intent(raw: str) -> str:
    m = _norm(raw)

    if _any(m, ["привет", "здравствуй", "добрый день", "добрый вечер", "хай"]):
        return "greeting"

    if _any(m, ["ресторан", "кафе", "столовая", "суши", "пиццерия", "фастфуд",
                "макдак", "бургер кинг", "кфс", "доставка еды"]):
        return "restaurant"

    if _any(m, ["пропустил", "пропустила", "не поел", "не поела",
                "забыл поесть", "забыла поесть", "не ел", "не ела",
                "пропуск приёма", "пропуск приема"]):
        return "skipped"

    # "Съел лишнего / не по плану"
    if _any(m, ["съел", "съела", "поел", "поела", "перекусил", "перекусила",
                "выпил", "выпила"]):
        if _any(m, ["не по плану", "лишнего", "лишнее", "сладк", "пицц",
                    "пиво", "вино", "торт", "шоколад", "печень", "печение",
                    "мороженое", "бургер", "чипс", "снек", "конфет",
                    "сухарик", "крекер"]):
            return "ate_extra"
        return "ate_unplanned"

    # "Что у меня сегодня / что есть / план на сегодня"
    if _phrase(m, ["что сегодня", "план сегодня", "что у меня сегодня",
                   "меню сегодня", "покажи план", "план на сегодня",
                   "что мне есть", "что есть сегодня"]):
        return "today_plan"
    # single-word trigger: message contains "сегодня" + intent word
    if _any(m, ["сегодня"]) and _any(m, ["план", "меню", "ест", "покажи", "расскажи"]):
        return "today_plan"

    if _any(m, ["испортит", "протухн", "срок"]) or _phrase(m, ["скоро испортится", "что скоро"]):
        return "expiring"

    if _phrase(m, ["какой контейнер", "что взять", "следующий приём",
                   "следующая еда", "что дальше есть"]):
        return "next_meal"

    if _any(m, ["перенести", "перенеси"]) or _phrase(m, ["следующий период", "следующую неделю"]):
        return "reschedule"

    if _any(m, ["упрости", "попроще", "простой вариант", "меньше готовить",
                "упростить меню"]):
        return "simplify"

    if _any(m, ["похудел", "похудела", "набрал вес", "набрала вес",
                "прогресс", "результат", "сколько потерял"]):
        return "weight"

    if _any(m, ["норма белка", "сколько белка", "норма калорий",
                "сколько калорий", "мои цели", "мои нормы"]):
        return "targets"

    return "unknown"


def _extract_meal_label(msg: str) -> str:
    m = _norm(msg)
    for en, ru in MEAL_LABELS.items():
        if ru in m:
            return ru
    return "приём пищи"


# ── Service ──────────────────────────────────────────────────────────────── #


class SimpleAgentService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def chat(
        self,
        user_id: int,
        message: str,
        history: list[dict] | None = None,
    ) -> dict:
        intent = detect_intent(message)
        reply = await self._dispatch(intent, message, user_id)
        return {"reply": reply, "tool_calls": [], "deviation_id": None}

    # ── Dispatcher ───────────────────────────────────────────────────── #

    async def _dispatch(self, intent: str, message: str, user_id: int) -> str:
        match intent:
            case "greeting":
                return self._greeting()
            case "today_plan":
                return await self._today_plan(user_id)
            case "expiring":
                return await self._expiring(user_id)
            case "next_meal":
                return await self._next_meal(user_id)
            case "restaurant":
                return self._restaurant(message)
            case "skipped":
                return self._skipped(message)
            case "ate_extra" | "ate_unplanned":
                return self._ate_extra(message)
            case "reschedule":
                return self._reschedule()
            case "simplify":
                return self._simplify()
            case "weight":
                return self._weight()
            case "targets":
                return await self._targets(user_id)
            case _:
                return self._unknown()

    # ── Static responses ─────────────────────────────────────────────── #

    def _greeting(self) -> str:
        return (
            "Привет! 👋\n\n"
            "Я помогу с питанием. Можешь спросить:\n"
            "• «Что у меня сегодня?»\n"
            "• «Поел в ресторане вместо ужина»\n"
            "• «Съел лишнего»\n"
            "• «Что скоро испортится?»"
        )

    def _restaurant(self, message: str) -> str:
        meal = _extract_meal_label(message)
        return (
            f"Понял, поел в ресторане вместо запланированного — {meal} зачтён ✅\n\n"
            "Один раз вне плана не разрушает прогресс. "
            "Если порции были примерно в норме — просто продолжай дальше. "
            "Если явно переел — уменьши следующий приём пищи на треть.\n\n"
            "Совет: в ресторане выбирай блюда на основе белка + овощи, "
            "избегай жареного и сладких напитков — тогда отклонение минимальное."
        )

    def _skipped(self, message: str) -> str:
        meal = _extract_meal_label(message)
        return (
            f"Понял, {meal} пропущен.\n\n"
            "Лучшая стратегия — не «добирать» пропущенные калории специально. "
            "Следующий приём пищи в обычном режиме и обычной порции.\n\n"
            "Организм легко переносит один пропуск — это нормально."
        )

    def _ate_extra(self, message: str) -> str:
        m = _norm(message)
        what_map = {
            "пицц":      ("съел", "пиццу"),
            "пиво":      ("выпил", "пиво"),
            "вино":      ("выпил", "вино"),
            "торт":      ("съел", "торт"),
            "шоколад":   ("съел", "шоколад"),
            "мороженое": ("съел", "мороженое"),
            "бургер":    ("съел", "бургер"),
            "печень":    ("съел", "печенье"),
            "конфет":    ("съел", "конфеты"),
            "чипс":      ("съел", "чипсы"),
        }
        matches = [(verb, label) for key, (verb, label) in what_map.items() if key in m]
        if matches:
            verb, what = matches[0]
            what_str = ", ".join(lbl for _, lbl in matches)
        else:
            verb, what_str = "съел", "что-то вкусное"

        return (
            f"{verb.capitalize()} {what_str} не по плану — бывает! 🙂\n\n"
            "Один раз не ломает прогресс. Что делать дальше:\n"
            "• Следующий приём — чуть меньше порция (на 20–30%)\n"
            "• Или просто продолжай план как обычно\n"
            "• Не голодай «в наказание» — это приводит к новым срывам\n\n"
            "Главное — не бросать план из-за одного отступления."
        )

    def _reschedule(self) -> str:
        return (
            "Переносить приём пищи на следующую неделю обычно не нужно — "
            "просто продолжай план с текущего момента.\n\n"
            "Если пропустил целый день:\n"
            "• Не пытайся «наверстать» двойными порциями\n"
            "• Вернись к обычному ритму со следующего приёма\n\n"
            "Если планируешь пропустить заранее (командировка, праздник) — "
            "скажи об этом при создании плана, и рацион сразу учтёт это."
        )

    def _simplify(self) -> str:
        return (
            "Хорошая идея! Самый простой недельный шаблон:\n\n"
            "• Завтрак: каша (гречка/овсянка) + яйца\n"
            "• Обед: крупа + мясо/рыба + овощи\n"
            "• Ужин: творог или яйца + овощной салат\n"
            "• Перекус: фрукт или орехи\n\n"
            "2–3 блюда на всю неделю — готовишь один раз, не думаешь каждый день. "
            "Для пересоставления плана зайди в раздел «План»."
        )

    def _weight(self) -> str:
        return (
            "Следить за прогрессом важно, но ежедневные колебания — норма (±1–2 кг от воды).\n\n"
            "Рекомендую:\n"
            "• Взвешиваться раз в неделю, утром натощак\n"
            "• Смотреть на тренд за 3–4 недели, не на ежедневные цифры\n"
            "• Ориентироваться также на самочувствие и объёмы, не только на вес"
        )

    def _unknown(self) -> str:
        return (
            "Этот вопрос пока в разработке 🔧\n\n"
            "Сейчас я умею помочь с:\n"
            "• «Что у меня сегодня?» — покажу план дня\n"
            "• «Поел в ресторане вместо ужина» — зафиксирую отклонение\n"
            "• «Съел лишнего / пиццу / пиво» — подскажу как скорректироваться\n"
            "• «Что скоро испортится?» — проверю контейнеры\n"
            "• «Пропустил обед» — объясню что делать\n\n"
            "Полноценный ИИ-агент появится в следующей версии 🚀"
        )

    # ── DB-backed responses ──────────────────────────────────────────── #

    async def _today_plan(self, user_id: int) -> str:
        today = date.today()
        plan, day = await self._get_day(user_id, today)

        if not plan:
            return (
                "У тебя пока нет активного плана питания.\n"
                "Создай его в разделе «План» — займёт пару минут."
            )
        if not day or not day.meals:
            return "На сегодня приёмов пищи не запланировано."

        meals = sorted(day.meals, key=lambda x: MEAL_ORDER.get(x.meal_type, 99))
        lines = [f"📅 План на {today.strftime('%d.%m')}:\n"]

        for meal in meals:
            icon = STATUS_ICON.get(meal.status, "•")
            label = MEAL_LABELS.get(meal.meal_type, meal.meal_type).capitalize()
            kcal_str = ""
            if meal.kbzhu_actual and meal.kbzhu_actual.get("kcal"):
                kcal_str = f" · {round(meal.kbzhu_actual['kcal'])} ккал"
            container_str = ""
            if meal.container_id:
                container_str = f" · 📦 {meal.container_id}"
            lines.append(f"{icon} {label}{kcal_str}{container_str}")

        targets = plan.daily_targets or {}
        if targets.get("kcal"):
            lines.append(f"\n🎯 Цель дня: {round(targets['kcal'])} ккал")

        done_count = sum(1 for m in meals if m.status == "done")
        if done_count == len(meals):
            lines.append("\n🎉 Все приёмы пищи выполнены!")

        return "\n".join(lines)

    async def _expiring(self, user_id: int) -> str:
        today = date.today()
        deadline = today + timedelta(days=2)

        plan = await self._get_active_plan(user_id)
        if not plan:
            return "У тебя нет активного плана — нечего проверять."

        result = await self.session.execute(
            select(Container)
            .where(Container.plan_id == plan.id)
            .where(Container.expiry_date <= deadline)
            .where(Container.status == "filled")
        )
        containers = result.scalars().all()

        if not containers:
            return "Всё свежее — контейнеров с близким сроком нет 👍"

        containers_sorted = sorted(
            containers, key=lambda c: c.expiry_date or date.max
        )
        lines = ["⏰ Скоро истекает срок:\n"]
        for c in containers_sorted:
            days = (c.expiry_date - today).days if c.expiry_date else 0
            desc = c.contents_description or "содержимое не указано"
            when = (
                "сегодня последний день" if days == 0
                else "завтра" if days == 1
                else f"через {days} дня"
            )
            lines.append(f"📦 {c.label} — {desc} ({when})")

        lines.append("\nСъешь их в первую очередь!")
        return "\n".join(lines)

    async def _next_meal(self, user_id: int) -> str:
        today = date.today()
        _, day = await self._get_day(user_id, today)

        if not day:
            return "У тебя нет активного плана питания."

        planned = [m for m in day.meals if m.status == "planned"]
        if not planned:
            return "На сегодня все приёмы пищи выполнены! 🎉"

        planned.sort(key=lambda x: MEAL_ORDER.get(x.meal_type, 99))
        nxt = planned[0]
        label = MEAL_LABELS.get(nxt.meal_type, nxt.meal_type).capitalize()

        lines = [f"Следующий приём: {label}"]
        if nxt.container_id:
            lines.append(f"Контейнер: 📦 {nxt.container_id}")
        if nxt.kbzhu_actual and nxt.kbzhu_actual.get("kcal"):
            lines.append(f"Примерно: {round(nxt.kbzhu_actual['kcal'])} ккал")

        return "\n".join(lines)

    async def _targets(self, user_id: int) -> str:
        plan = await self._get_active_plan(user_id)
        if not plan:
            return "У тебя пока нет активного плана — нормы не рассчитаны."

        t = plan.daily_targets or {}
        if not t:
            return "Нормы в плане не заданы."

        lines = ["🎯 Твои дневные нормы:\n"]
        if t.get("kcal"):
            lines.append(f"• Калории: {round(t['kcal'])} ккал")
        if t.get("protein"):
            lines.append(f"• Белок: {round(t['protein'])} г")
        if t.get("fat"):
            lines.append(f"• Жиры: {round(t['fat'])} г")
        if t.get("carbs"):
            lines.append(f"• Углеводы: {round(t['carbs'])} г")

        return "\n".join(lines)

    # ── DB helpers ───────────────────────────────────────────────────── #

    async def _get_active_plan(self, user_id: int) -> MealPlan | None:
        today = date.today()
        result = await self.session.execute(
            select(MealPlan)
            .where(MealPlan.user_id == user_id)
            .where(MealPlan.period_start <= today)
            .where(MealPlan.period_end >= today)
            .where(MealPlan.status == "active")
            .order_by(MealPlan.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def _get_day(
        self, user_id: int, day_date: date
    ) -> tuple[MealPlan | None, DayPlan | None]:
        plan = await self._get_active_plan(user_id)
        if not plan:
            return None, None

        result = await self.session.execute(
            select(DayPlan)
            .where(DayPlan.plan_id == plan.id)
            .where(DayPlan.date == day_date)
            .options(selectinload(DayPlan.meals))
        )
        return plan, result.scalar_one_or_none()
