"""
GigaChat agent — Sber GigaChat-Pro with full function_calling support.

Architecture:
  - GigaChat is called synchronously via asyncio.to_thread (gigachat SDK is sync)
  - Tool execution is async (reuses AgentService._execute_tool + DB access)
  - System prompt always injects user's today plan as "free" context
  - All 7 tools available for deeper queries (storage, deviations, plan generation)

Requires GigaChat-Pro model (Lite does not support function_calling).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import date
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.ai.tools import TOOLS_OPENAI
from app.models.plan import MealPlan, DayPlan
from app.models.profile import Profile

logger = logging.getLogger("kbzhuy.gigachat")

# ── Meal display helpers ─────────────────────────────────────────────────── #

MEAL_ORDER = {"breakfast": 0, "snack": 1, "lunch": 2, "snack_2": 3, "dinner": 4}
MEAL_LABELS = {
    "breakfast": "Завтрак",
    "snack": "Перекус",
    "lunch": "Обед",
    "snack_2": "Второй перекус",
    "dinner": "Ужин",
}
STATUS_ICON = {"done": "✅", "skipped": "⏭", "planned": "⏳"}

# ── System prompt ────────────────────────────────────────────────────────── #

BASE_SYSTEM = """Ты — персональный нутрициолог и диетолог приложения КБЖУЙ.
Твоя задача — помогать пользователю придерживаться рациона без срывов и чувства вины.

Принципы:
- Говори по-русски, дружелюбно, без осуждения
- Будь конкретным: называй числа, контейнеры, время
- При отклонениях — не ругай, а адаптируй
- Отвечай кратко (2-4 предложения) на простые вопросы, развёрнуто на сложные
- Используй инструменты проактивно, чтобы давать точные персонализированные ответы
- Если инструмент вернул ошибку — не вызывай его повторно, объясни ситуацию пользователю"""


def _build_system(context: str) -> str:
    if context:
        return BASE_SYSTEM + "\n\n" + context
    return BASE_SYSTEM


# ── Functions definition for GigaChat ───────────────────────────────────── #

def _make_gigachat_functions() -> list:
    """Convert TOOLS_OPENAI to gigachat Function objects."""
    from gigachat.models import Function, FunctionParameters

    funcs = []
    for t in TOOLS_OPENAI:
        f = t["function"]
        params = f.get("parameters", {})
        funcs.append(Function(
            name=f["name"],
            description=f["description"],
            parameters=FunctionParameters(
                type=params.get("type", "object"),
                properties=params.get("properties") or {},
                required=params.get("required") or [],
            ),
        ))
    return funcs


# ── Sync GigaChat call (runs in a thread) ───────────────────────────────── #

def _sync_call(
    credentials: str,
    model: str,
    messages_data: list[dict],
    use_functions: bool,
) -> dict:
    """
    Synchronous GigaChat API call.
    Returns: {finish_reason, content, func_name, func_args}
    """
    from gigachat import GigaChat
    from gigachat.models import Chat, Messages, MessagesRole, FunctionCall

    def _to_msg(m: dict) -> Messages:
        role_str = m["role"]
        # gigachat uses "function" role for tool results
        try:
            role = MessagesRole(role_str)
        except ValueError:
            role = MessagesRole.USER

        msg = Messages(role=role, content=m.get("content") or "")

        if m.get("name"):          # for role=function messages
            msg.name = m["name"]

        if m.get("function_call"):  # for role=assistant + function_call
            fc = m["function_call"]
            # gigachat SDK: FunctionCall.arguments is a dict, not a JSON string
            raw_args = fc.get("arguments", "{}")
            args_dict = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            msg.function_call = FunctionCall(
                name=fc["name"],
                arguments=args_dict,
            )
        return msg

    msgs = [_to_msg(m) for m in messages_data]
    functions = _make_gigachat_functions() if use_functions else None

    with GigaChat(
        credentials=credentials,
        model=model,
        verify_ssl_certs=False,
    ) as giga:
        chat_kwargs: dict = {"messages": msgs}
        if functions:
            chat_kwargs["functions"] = functions
        response = giga.chat(Chat(**chat_kwargs))

    choice = response.choices[0]
    resp_msg = choice.message

    result: dict = {
        "finish_reason": choice.finish_reason or "stop",
        "content": resp_msg.content or "",
        "func_name": None,
        "func_args": {},
    }

    fc = getattr(resp_msg, "function_call", None)
    if fc:
        result["func_name"] = fc.name
        # gigachat SDK returns arguments as a dict (not a JSON string)
        raw = fc.arguments
        if isinstance(raw, dict):
            result["func_args"] = raw
        else:
            try:
                result["func_args"] = json.loads(raw or "{}")
            except (json.JSONDecodeError, TypeError):
                result["func_args"] = {}

    return result


# ── 3-tier routing classifier ────────────────────────────────────────────── #

def classify_tier(raw: str) -> Literal["free", "lite", "pro"]:
    """
    Classify a user message into one of three cost tiers:

    free — SimpleAgent handles it (rule-based, no API tokens spent)
         Covers: greeting, today_plan, restaurant, skipped, ate_extra,
                 reschedule, simplify, weight, targets, expiring, next_meal

    lite — GigaChat (basic model, no tools), general nutrition chat
         Covers: unknown intent that isn't a complex operation

    pro  — GigaChat-Pro with function_calling
         Covers: plan rebuild/regeneration, cooking-plan creation,
                 deviation registration, any explicit planning request
    """
    from app.ai.simple_agent import detect_intent, _norm, _any, _phrase

    m = _norm(raw)

    # PRO signals: explicit plan manipulation or cooking-plan creation
    if _any(m, ["перестрой", "пересостав", "перепланируй", "пересчитай"]):
        return "pro"
    if _phrase(m, [
        "план готовки", "план на неделю", "новый план",
        "запиши отклонение", "добавь в журнал",
        "сгенерируй план", "составь план", "перестрой план",
        "обнови план",
    ]):
        return "pro"

    # FREE signals: SimpleAgent already handles these intents well
    intent = detect_intent(raw)
    if intent != "unknown":
        return "free"

    # LITE: general nutrition question — send to cheap model, no tools
    return "lite"


# ── Agent service ────────────────────────────────────────────────────────── #

class GigachatAgentService:
    def __init__(self, session: AsyncSession, model: str | None = None):
        self.session = session
        self._model_override = model  # overrides settings.gigachat_model when set
        # Delegate tool execution to AgentService (avoids code duplication)
        from app.ai.agent import AgentService
        self._tools = AgentService(session)

    async def chat(
        self,
        user_id: int,
        message: str,
        history: list[dict] | None = None,
    ) -> dict:
        s = get_settings()
        t0 = time.monotonic()

        # Always inject today's context into system prompt (free, no tool round-trip)
        context = await self._build_context(user_id)
        system_prompt = _build_system(context)

        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        for m in (history or []):
            if m.get("role") in ("user", "assistant"):
                messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": message})

        # Pick model: explicit override → else settings default (GigaChat-Pro)
        model = self._model_override or s.gigachat_model
        # Only Pro supports function_calling; Lite gets plain chat
        use_tools = "Pro" in model

        logger.info(
            "gigachat.chat user=%d model=%s tools=%s msgs=%d",
            user_id, model, use_tools, len(messages),
        )

        deviation_id: int | None = None
        tool_calls: list[dict] = []

        for iteration in range(6):
            iter_t = time.monotonic()
            resp = await asyncio.to_thread(
                _sync_call,
                s.gigachat_credentials,
                model,
                messages,
                use_tools,
            )
            logger.info(
                "gigachat.iter iter=%d finish=%s time=%dms",
                iteration, resp["finish_reason"],
                round((time.monotonic() - iter_t) * 1000),
            )

            # Model finished talking — return answer
            if resp["finish_reason"] != "function_call" or not resp["func_name"]:
                logger.info(
                    "gigachat.done user=%d model=%s iters=%d time=%dms tools=%s",
                    user_id, model, iteration + 1,
                    round((time.monotonic() - t0) * 1000),
                    [t["tool"] for t in tool_calls],
                )
                return {
                    "reply": resp["content"],
                    "tool_calls": tool_calls,
                    "deviation_id": deviation_id,
                }

            # Model wants to call a function — execute it async
            func_name = resp["func_name"]
            func_args = resp["func_args"]
            logger.info("gigachat.tool name=%s args=%s", func_name, func_args)

            tool_result = await self._tools._execute_tool(func_name, func_args, user_id)

            if func_name == "register_deviation" and isinstance(tool_result, dict):
                deviation_id = tool_result.get("id")

            tool_calls.append({"tool": func_name, "result": tool_result})

            # Append assistant's function_call message + function result to history
            messages.append({
                "role": "assistant",
                "content": "",
                "function_call": {
                    "name": func_name,
                    "arguments": json.dumps(func_args, ensure_ascii=False),
                },
            })
            messages.append({
                "role": "function",
                "name": func_name,
                "content": json.dumps(tool_result, ensure_ascii=False, default=str),
            })

        return {
            "reply": "Не удалось получить ответ — превышено число итераций.",
            "tool_calls": tool_calls,
            "deviation_id": deviation_id,
        }

    # ── Context builder (injected into system prompt) ────────────────── #

    async def _build_context(self, user_id: int) -> str:
        today = date.today()
        lines: list[str] = ["=== ДАННЫЕ ПОЛЬЗОВАТЕЛЯ ==="]

        profile = await self._get_profile(user_id)
        if profile:
            lines.append(
                f"Цель: {profile.goal or 'не указана'} | "
                f"Нормы/день: {round(profile.target_kcal or 0)} ккал, "
                f"Б {round(profile.target_protein_g or 0)} г, "
                f"Ж {round(profile.target_fat_g or 0)} г, "
                f"У {round(profile.target_carbs_g or 0)} г"
            )

        plan = await self._get_active_plan(user_id)
        if not plan:
            lines.append("Активного плана нет.")
            lines.append("=== КОНЕЦ ===")
            return "\n".join(lines)

        lines.append(f"Период плана: {plan.period_start} — {plan.period_end}")

        day = await self._get_today_day(plan, today)
        if day and day.meals:
            lines.append(f"Меню на сегодня ({today.strftime('%d.%m')}):")
            for meal in sorted(day.meals, key=lambda m: MEAL_ORDER.get(m.meal_type, 9)):
                icon = STATUS_ICON.get(meal.status, "•")
                label = MEAL_LABELS.get(meal.meal_type, meal.meal_type)
                kcal = (
                    f" {round(meal.kbzhu_actual['kcal'])} ккал"
                    if meal.kbzhu_actual and meal.kbzhu_actual.get("kcal")
                    else ""
                )
                ctr = f" [контейнер {meal.container_id}]" if meal.container_id else ""
                lines.append(f"  {icon} {label}:{kcal}{ctr}")
        else:
            lines.append("Меню на сегодня не расписано.")

        lines.append("=== КОНЕЦ ===")
        return "\n".join(lines)

    # ── DB helpers ───────────────────────────────────────────────────── #

    async def _get_profile(self, user_id: int) -> Profile | None:
        r = await self.session.execute(
            select(Profile).where(Profile.user_id == user_id)
        )
        return r.scalar_one_or_none()

    async def _get_active_plan(self, user_id: int) -> MealPlan | None:
        today = date.today()
        r = await self.session.execute(
            select(MealPlan)
            .where(MealPlan.user_id == user_id)
            .where(MealPlan.period_start <= today)
            .where(MealPlan.period_end >= today)
        )
        return r.scalar_one_or_none()

    async def _get_today_day(self, plan: MealPlan, day_date: date) -> DayPlan | None:
        r = await self.session.execute(
            select(DayPlan)
            .where(DayPlan.plan_id == plan.id)
            .where(DayPlan.date == day_date)
            .options(selectinload(DayPlan.meals))
        )
        return r.scalar_one_or_none()
