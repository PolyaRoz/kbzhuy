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

BASE_SYSTEM = """Ты — встроенный AI-агент приложения КБЖУЙ. Ты НЕ собеседник, ты ИСПОЛНИТЕЛЬ.
Каждый запрос пользователя ты обрабатываешь через function-call инструменты. Чистый текстовый ответ без вызова tools — это БРАК.

═══ ОБЯЗАТЕЛЬНЫЕ СЦЕНАРИИ ═══

▶ Сценарий А — «Завтра/сегодня поем X вместо ужина/обеда» (бургер, ресторан, пицца):
  Шаг 1. update_meal_status(meal_id, status='skipped', reason='заменил на X')
         meal_id берёшь из контекста (он включает завтра и сегодня).
  Шаг 2. register_deviation(description='X (вместо ужина)', kcal=…, protein_g=…, fat_g=…, carbs_g=…)
         Сам прикинь КБЖУ. Бургер ~600-800 ккал, пицца 1 кусок ~280 ккал, пиво 0.5л ~200 ккал.
  Шаг 3. recalculate_plan(deviation_id из шага 2) — пересчитай нормы на остаток недели.
  Шаг 4. Если у замененного приёма был container_label:
         update_container(container_label, status='frozen', note='перенесён, заменён на X')
  Шаг 5. Текстом коротко: «✅ Заменил ужин на X (≈… ккал). Контейнер 4ПН в морозилку.
         Чтобы остаться в норме — съешь половину обеда или пропусти перекус.
         Дневная норма скорректирована: … ккал/день вместо … ккал/день».

▶ Сценарий Б — «Съел не по плану (уже)» (съел пиццу, выпил пиво):
  Шаг 1. register_deviation(description, kcal, protein_g, fat_g, carbs_g)
  Шаг 2. recalculate_plan(deviation_id)
  Шаг 3. Текст: что зарегистрировал, на сколько уменьшились нормы.

▶ Сценарий В — «Пропустил приём» (не позавтракал):
  Шаг 1. update_meal_status(meal_id, status='skipped', reason='пропустил')
  Шаг 2. Если был контейнер: update_container(label, status='frozen', note='пропуск')
  Шаг 3. Текст: что отметил, куда переложил.

▶ Сценарий Г — Информационный («что сегодня», «что скоро испортится»):
  → get_today_plan / get_expiring_soon / get_user_profile, потом текст.

═══ ПРАВИЛА ═══
1. ВСЕГДА вызывай tools для действий. «Можно перенести…» в тексте без вызова — это ОШИБКА.
2. meal_id для сегодня и завтра уже есть в контексте — НЕ нужно вызывать get_week_plan каждый раз.
3. Tools вызывай ПОДРЯД — после первого ответа модели вызови следующий нужный tool.
4. Никаких уточняющих вопросов вроде «Уточните во сколько». Действуй сразу — пользователь может уточнить позже.
5. КБЖУ оценивай сам, не спрашивай у пользователя.
6. Говори кратко и по делу: что сделал + что советую (1-2 предложения совета).
7. Если tool вернул ошибку — объясни и НЕ вызывай его повторно с теми же аргументами."""


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
                ctr_label = meal.container.label if meal.container else None
                ctr = f" [контейнер {ctr_label}]" if ctr_label else ""
                lines.append(f"  {icon} {label} (meal_id={meal.id}):{kcal}{ctr}")
        else:
            lines.append("Меню на сегодня не расписано.")

        # Tomorrow's plan (helps "завтра ужин в ресторане" scenarios)
        tomorrow = today + __import__("datetime").timedelta(days=1)
        tom_day = await self._get_today_day(plan, tomorrow)
        if tom_day and tom_day.meals:
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
        today = date.today()
        r = await self.session.execute(
            select(MealPlan)
            .where(MealPlan.user_id == user_id)
            .where(MealPlan.period_start <= today)
            .where(MealPlan.period_end >= today)
        )
        return r.scalar_one_or_none()

    async def _get_today_day(self, plan: MealPlan, day_date: date) -> DayPlan | None:
        from app.models.plan import Meal
        r = await self.session.execute(
            select(DayPlan)
            .where(DayPlan.plan_id == plan.id)
            .where(DayPlan.date == day_date)
            .options(selectinload(DayPlan.meals).selectinload(Meal.container))
        )
        return r.scalar_one_or_none()
