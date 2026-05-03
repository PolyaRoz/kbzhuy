"""
GigaChat agent — Sber GigaChat as the LLM backend.
Uses context-injection (no tool_use) so it works with any GigaChat model tier.

Auth: pass GIGACHAT_CREDENTIALS = base64(clientId:clientSecret)
      taken from https://developers.sber.ru/studio → GigaChat API → Settings.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.container import Container
from app.models.plan import DayPlan, MealPlan
from app.models.profile import Profile

logger = logging.getLogger("kbzhuy.gigachat")

MEAL_ORDER = {"breakfast": 0, "snack": 1, "lunch": 2, "snack_2": 3, "dinner": 4}
MEAL_LABELS = {
    "breakfast": "Завтрак",
    "snack": "Перекус",
    "lunch": "Обед",
    "snack_2": "Второй перекус",
    "dinner": "Ужин",
}
STATUS_ICON = {"done": "✅", "skipped": "⏭", "planned": "⏳"}

BASE_SYSTEM_PROMPT = """Ты — персональный нутрициолог и диетолог приложения КБЖУЙ.
Твоя задача — помогать пользователю придерживаться рациона, не срываясь и без чувства вины.

Принципы общения:
- Говори по-русски, дружелюбно и без осуждения
- Будь конкретным: называй числа, контейнеры, время
- При отклонениях от плана — не ругай, а адаптируй
- Если пользователь съел лишнего — спокойно перераспредели ккал на остаток дня
- Отвечай кратко (3-5 предложений) если вопрос простой, развёрнуто если сложный
- Если не знаешь точного ответа — скажи честно и предложи альтернативу"""


def _build_system_prompt(context: str) -> str:
    if context:
        return BASE_SYSTEM_PROMPT + "\n\n" + context
    return BASE_SYSTEM_PROMPT


def _sync_gigachat_call(credentials: str, model: str, messages_data: list[dict]) -> str:
    """Synchronous GigaChat call — run via asyncio.to_thread."""
    from gigachat import GigaChat  # imported here to avoid ImportError when not installed
    from gigachat.models import Chat, Messages, MessagesRole

    role_map = {
        "system": MessagesRole.SYSTEM,
        "user": MessagesRole.USER,
        "assistant": MessagesRole.ASSISTANT,
    }
    msgs = [
        Messages(role=role_map[m["role"]], content=m["content"])
        for m in messages_data
    ]

    with GigaChat(
        credentials=credentials,
        model=model,
        verify_ssl_certs=False,
    ) as giga:
        response = giga.chat(Chat(messages=msgs))
        return response.choices[0].message.content or ""


class GigachatAgentService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def chat(
        self,
        user_id: int,
        message: str,
        history: list[dict] | None = None,
    ) -> dict:
        settings = get_settings()

        # Build user context from DB and inject into system prompt
        context = await self._build_context(user_id)
        system_prompt = _build_system_prompt(context)

        # Assemble message list: system + history + new user message
        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        for m in (history or []):
            if m.get("role") in ("user", "assistant"):
                messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": message})

        logger.info(
            "gigachat.chat user=%d model=%s msgs=%d",
            user_id, settings.gigachat_model, len(messages),
        )

        try:
            reply = await asyncio.to_thread(
                _sync_gigachat_call,
                settings.gigachat_credentials,
                settings.gigachat_model,
                messages,
            )
        except Exception as exc:
            logger.error("gigachat.error %s", exc)
            raise

        logger.info("gigachat.done user=%d reply_len=%d", user_id, len(reply))
        return {"reply": reply, "tool_calls": [], "deviation_id": None}

    # ── Context builder ─────────────────────────────────────────────── #

    async def _build_context(self, user_id: int) -> str:
        today = date.today()
        lines: list[str] = ["=== КОНТЕКСТ ПОЛЬЗОВАТЕЛЯ ==="]

        # Profile / targets
        profile = await self._get_profile(user_id)
        if profile:
            lines.append(
                f"Цель: {profile.goal or 'не указана'} | "
                f"Нормы: {round(profile.target_kcal or 0)} ккал, "
                f"Б {round(profile.target_protein_g or 0)}г, "
                f"Ж {round(profile.target_fat_g or 0)}г, "
                f"У {round(profile.target_carbs_g or 0)}г"
            )

        # Active plan
        plan = await self._get_active_plan(user_id)
        if not plan:
            lines.append("Активного плана питания нет.")
            lines.append("=== КОНЕЦ КОНТЕКСТА ===")
            return "\n".join(lines)

        lines.append(
            f"Активный план: {plan.period_start} — {plan.period_end}"
        )

        # Today's meals
        day = await self._get_day(plan, today)
        if day and day.meals:
            lines.append(f"\nМеню на сегодня ({today.strftime('%d.%m.%Y')}):")
            for meal in sorted(day.meals, key=lambda m: MEAL_ORDER.get(m.meal_type, 9)):
                icon = STATUS_ICON.get(meal.status, "•")
                label = MEAL_LABELS.get(meal.meal_type, meal.meal_type)
                kcal_str = ""
                if meal.kbzhu_actual and meal.kbzhu_actual.get("kcal"):
                    kcal_str = f" ({round(meal.kbzhu_actual['kcal'])} ккал)"
                container_str = f" [контейнер {meal.container_id}]" if meal.container_id else ""
                lines.append(f"  {icon} {label}{kcal_str}{container_str}")
        else:
            lines.append("На сегодня план не расписан.")

        lines.append("=== КОНЕЦ КОНТЕКСТА ===")
        return "\n".join(lines)

    # ── DB helpers ───────────────────────────────────────────────────── #

    async def _get_profile(self, user_id: int) -> Profile | None:
        result = await self.session.execute(
            select(Profile).where(Profile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def _get_active_plan(self, user_id: int) -> MealPlan | None:
        today = date.today()
        result = await self.session.execute(
            select(MealPlan)
            .where(MealPlan.user_id == user_id)
            .where(MealPlan.period_start <= today)
            .where(MealPlan.period_end >= today)
        )
        return result.scalar_one_or_none()

    async def _get_day(self, plan: MealPlan, day_date: date) -> DayPlan | None:
        result = await self.session.execute(
            select(DayPlan)
            .where(DayPlan.plan_id == plan.id)
            .where(DayPlan.date == day_date)
            .options(selectinload(DayPlan.meals))
        )
        return result.scalar_one_or_none()
