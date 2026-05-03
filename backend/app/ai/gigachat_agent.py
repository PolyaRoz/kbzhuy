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

MEAL_ORDER = {
    # Canonical types
    "breakfast": 0, "snack": 2, "lunch": 1, "snack_2": 3, "dinner": 4,
    # Alias used by meal_planner (meal_1..meal_5)
    "meal_1": 0, "meal_2": 1, "meal_3": 2, "meal_4": 3, "meal_5": 4,
}
MEAL_LABELS = {
    "breakfast": "Завтрак",
    "snack": "Перекус",
    "lunch": "Обед",
    "snack_2": "Второй перекус",
    "dinner": "Ужин",
    # The legacy/internal naming used by meal_planner_service stays in DB —
    # we still need to render it as human-readable in the agent context.
    "meal_1": "Завтрак",
    "meal_2": "Обед",
    "meal_3": "Перекус",
    "meal_4": "Ужин",
    "meal_5": "Второй перекус",
}
STATUS_ICON = {"done": "✅", "skipped": "⏭", "planned": "⏳", "eaten": "✅"}

# ── System prompt ────────────────────────────────────────────────────────── #

BASE_SYSTEM = """Ты — встроенный AI-агент приложения КБЖУЙ. Ты НЕ собеседник, ты ИСПОЛНИТЕЛЬ.
Каждый запрос ты обрабатываешь через function-call инструменты. Чистый текстовый ответ без tools, когда нужно действие — это БРАК.

═══ КАК ВЫБРАТЬ meal_id ═══

В системном контексте ниже есть блок с meal_id. Структура:
  «Меню на сегодня (DD.MM):  ⏳ Ужин (meal_id=N): … [контейнер 4ПН]»
  «Меню на завтра (DD.MM):  • Ужин (meal_id=N): … [контейнер 4ВТ]»

Правила выбора:
- «Сегодня я съел/съем …» → meal_id из секции «Меню на сегодня».
- «Завтра я планирую/съем …» → meal_id из секции «Меню на завтра».
- Тип приёма: ужин/ужинать/поужинать/на ужин → meal_id с label «Ужин».
- завтрак/позавтракать → «Завтрак»; обед/пообедать/на обед → «Обед»; перекус → «Перекус».
- НЕ ВЫДУМЫВАЙ meal_id. Если в контексте нужного дня/типа нет — вызови get_week_plan.

═══ ОБЯЗАТЕЛЬНЫЕ СЦЕНАРИИ ═══

▶ А. «Завтра/сегодня съем/поужинаю X (бургер, пицца, ресторан)»:
  1. update_meal_status(meal_id из правильного дня и типа, status='skipped', reason='заменил на X')
  2. register_deviation(description='X (вместо ужина)', kcal, protein_g, fat_g, carbs_g)
     Бургер ~600-800 ккал, пицца кусок ~280, пиво 0.5л ~200, ролл 8шт ~400, шаурма ~600.
  3. recalculate_plan(deviation_id из шага 2)
  4. Если у замененного приёма есть [контейнер X]: update_container(label, status='frozen', note='заменён на X, перенесён')
  5. Текст: «✅ Заменил ужин на X (≈… ккал). Контейнер 4ПН в морозилку. Чтобы остаться в норме — половина обеда или пропусти перекус. Норма: … ккал/день».

▶ Б. «Съел/съела X (уже произошло)» — пицца, пиво, торт:
  1. register_deviation(description, kcal, protein_g, fat_g, carbs_g)
  2. recalculate_plan(deviation_id)
  3. Если это заменило плановый приём (например, «ужинала бургером» = заменила ужин): шаги 1-3 из сценария А (skip + freezer контейнера) ПОСЛЕ deviation.
  4. Текст: что зарегистрировал, на сколько уменьшились нормы.

▶ В. «Пропустил приём»:
  1. update_meal_status(meal_id, status='skipped', reason='пропустил')
  2. Если есть контейнер: update_container(label, status='frozen', note='пропуск')
  3. Текст: что сделал.

▶ Г. Информация («что сегодня», «что испортится», «нормы»):
  → get_today_plan / get_expiring_soon / get_user_profile → текст.

═══ ПРАВИЛА ═══
1. Действие → tool. «Можно перенести…» без вызова — БРАК.
2. ВСЕГДА читай контекст. meal_id из контекста — НЕ выдумывай.
3. Не задавай уточняющих вопросов (время, размер). Действуй с разумным дефолтом.
4. КБЖУ оценивай сам.
5. Tools вызывай подряд: после результата первого вызова сразу решай нужен ли следующий.
6. Краткий ответ: что сделал + 1-2 предложения совета. Без «как могу помочь».
7. Tool ошибся — объясни и НЕ повторяй с теми же аргументами."""


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

    logger.info(
        "gigachat.call model=%s use_functions=%s functions_count=%d msgs=%d",
        model,
        use_functions,
        len(functions) if functions else 0,
        len(msgs),
    )

    with GigaChat(
        credentials=credentials,
        model=model,
        verify_ssl_certs=False,
    ) as giga:
        chat_kwargs: dict = {"messages": msgs}
        if functions:
            chat_kwargs["functions"] = functions
            # function_call='auto' tells GigaChat-Pro it's allowed (and encouraged) to invoke them
            chat_kwargs["function_call"] = "auto"
        response = giga.chat(Chat(**chat_kwargs))

    choice = response.choices[0]
    resp_msg = choice.message
    logger.info(
        "gigachat.resp finish=%s content_preview=%r has_func_call=%s",
        choice.finish_reason,
        (resp_msg.content or "")[:120],
        getattr(resp_msg, "function_call", None) is not None,
    )

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
    3-tier cost-optimised routing:

    free — SimpleAgent (rule-based, no API tokens)
         Pure information / generic advice — no plan changes needed.
         Covers: greeting, today_plan, expiring, next_meal, targets,
                 weight, simplify

    lite — GigaChat basic (no function_calling)
         General nutrition questions where actions aren't required.

    pro  — GigaChat-Pro with function_calling
         ANY message that requires the agent to TAKE ACTIONS:
         move meals, mark statuses, register deviations, recalc,
         move containers to freezer, build / rebuild plans.
    """
    from app.ai.simple_agent import detect_intent, _norm, _any, _phrase

    m = _norm(raw)

    # ── Action-requiring intents — always Pro (agent must use tools) ──
    intent = detect_intent(raw)
    action_intents = {
        "restaurant",      # "поем в ресторане" → перенести приём, контейнер в морозилку
        "skipped",         # "пропустил обед" → отметить, перенести контейнер
        "ate_extra",       # "съел пиццу" → register_deviation + recalc
        "ate_unplanned",   # "съел что-то" → register_deviation
        "reschedule",      # "перенеси приём" → update_meal_status
    }
    if intent in action_intents:
        return "pro"

    # Explicit plan-rebuild / cooking-plan keywords — Pro
    if _any(m, ["перестрой", "пересостав", "перепланируй", "пересчитай",
                "отмени", "перенеси"]):
        return "pro"
    if _phrase(m, [
        "план готовки", "план на неделю", "новый план",
        "запиши отклонение", "добавь в журнал",
        "сгенерируй план", "составь план", "перестрой план",
        "обнови план", "в морозилку", "в морозильник",
        "не буду есть", "не буду ужинать", "не буду обедать",
        "буду есть в", "поем в", "ужин в ресторане",
        "планирую ужин", "планирую обед", "планирую завтрак",
        "завтра ужин", "завтра обед", "завтра завтрак",
    ]):
        return "pro"

    # Time-marker + meal-type combo: "завтра/сегодня/буду + завтрак/обед/ужин/перекус" → Pro
    # (e.g. "завтра планирую есть на ужин бургер")
    has_time = _any(m, ["завтра", "сегодня", "буду", "планирую", "собираюсь"])
    has_meal = _any(m, ["завтрак", "обед", "ужин", "перекус", "ужина", "обеда",
                         "ужинать", "обедать", "завтракать", "перекусить"])
    has_food = _any(m, [
        "бургер", "пицц", "пиво", "вино", "торт", "шоколад", "печень",
        "мороженое", "чипс", "снек", "конфет", "сухарик", "крекер",
        "паст", "суш", "роллы", "шаурм", "донер", "хот-дог", "фастфуд",
        "ресторан", "кафе", "столовая", "макдак", "бургер кинг", "кфс",
    ])
    if has_time and (has_meal or has_food):
        return "pro"
    if has_meal and has_food:
        return "pro"

    # Pure-info intents handled by SimpleAgent for free
    free_intents = {
        "greeting", "today_plan", "expiring", "next_meal",
        "targets", "weight", "simplify",
    }
    if intent in free_intents:
        return "free"

    # Unknown / general nutrition question — cheap Lite model
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
                "gigachat.iter iter=%d finish=%s func=%s content_len=%d time=%dms",
                iteration,
                resp["finish_reason"],
                resp["func_name"],
                len(resp["content"] or ""),
                round((time.monotonic() - iter_t) * 1000),
            )

            # Model finished talking — return answer.
            # Be lenient: ANY response without a func_name is treated as text.
            if not resp["func_name"]:
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

        from datetime import timedelta as _td

        # Render today + tomorrow even if they live in DIFFERENT plans
        # (week boundary case: today's plan ends, next week's plan starts tomorrow).
        tomorrow = today + _td(days=1)

        today_day = await self._get_day_plan_anywhere(user_id, today)
        tom_day = await self._get_day_plan_anywhere(user_id, tomorrow)

        if not today_day and not tom_day:
            lines.append("Активного плана нет.")
            lines.append("=== КОНЕЦ ===")
            return "\n".join(lines)

        if today_day:
            lines.append(f"Меню на сегодня ({today.strftime('%d.%m')}):")
            for meal in sorted(today_day.meals, key=lambda m: MEAL_ORDER.get(m.meal_type, 9)):
                icon = STATUS_ICON.get(meal.status, "•")
                label = MEAL_LABELS.get(meal.meal_type, meal.meal_type)
                kcal = (
                    f" {round(meal.kbzhu_actual['kcal'])} ккал"
                    if meal.kbzhu_actual and meal.kbzhu_actual.get("kcal")
                    else ""
                )
                ctr_label = meal.container.label if meal.container else None
                ctr = f" [контейнер {ctr_label}]" if ctr_label else ""
                lines.append(f"  {icon} {label} (meal_id={meal.id}):{kcal}{ctr}")
        else:
            lines.append("Меню на сегодня не расписано.")

        if tom_day:
            lines.append(f"Меню на завтра ({tomorrow.strftime('%d.%m')}):")
            for meal in sorted(tom_day.meals, key=lambda m: MEAL_ORDER.get(m.meal_type, 9)):
                label = MEAL_LABELS.get(meal.meal_type, meal.meal_type)
                ctr_label = meal.container.label if meal.container else None
                ctr = f" [контейнер {ctr_label}]" if ctr_label else ""
                lines.append(f"  • {label} (meal_id={meal.id}):{ctr}")

        lines.append("=== КОНЕЦ ===")
        return "\n".join(lines)

    # ── DB helpers ───────────────────────────────────────────────────── #

    async def _get_profile(self, user_id: int) -> Profile | None:
        r = await self.session.execute(
            select(Profile).where(Profile.user_id == user_id)
        )
        return r.scalar_one_or_none()

    async def _get_active_plan(self, user_id: int) -> MealPlan | None:
        # The DB allows multiple plans per user/period (cancelled + active).
        # Filter by status and take the most recent — never use scalar_one_or_none here.
        today = date.today()
        r = await self.session.execute(
            select(MealPlan)
            .where(MealPlan.user_id == user_id)
            .where(MealPlan.period_start <= today)
            .where(MealPlan.period_end >= today)
            .where(MealPlan.status == "active")
            .order_by(MealPlan.created_at.desc())
            .limit(1)
        )
        return r.scalars().first()

    async def _get_today_day(self, plan: MealPlan, day_date: date) -> DayPlan | None:
        from app.models.plan import Meal
        r = await self.session.execute(
            select(DayPlan)
            .where(DayPlan.plan_id == plan.id)
            .where(DayPlan.date == day_date)
            .options(selectinload(DayPlan.meals).selectinload(Meal.container))
        )
        return r.scalar_one_or_none()

    async def _get_day_plan_anywhere(self, user_id: int, day_date: date) -> DayPlan | None:
        """
        Find a day plan for a specific date across ALL of the user's active plans.
        Handles week-boundary cases where today's date lives in plan A and tomorrow
        lives in plan B (the next week).
        """
        from app.models.plan import Meal
        r = await self.session.execute(
            select(DayPlan)
            .join(MealPlan, DayPlan.plan_id == MealPlan.id)
            .where(MealPlan.user_id == user_id)
            .where(MealPlan.status == "active")
            .where(DayPlan.date == day_date)
            .order_by(MealPlan.created_at.desc())
            .limit(1)
            .options(selectinload(DayPlan.meals).selectinload(Meal.container))
        )
        return r.scalars().first()
