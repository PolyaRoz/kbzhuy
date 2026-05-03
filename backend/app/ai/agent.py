"""
AI Agent service: nutrition coach with tool_use.
Supports two backends:
  - Anthropic (Claude) — cloud, set USE_LOCAL_LLM=false
  - Ollama (OpenAI-compatible) — local, set USE_LOCAL_LLM=true
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date, timedelta
from typing import Any

import anthropic
import openai
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.ai.tools import TOOLS, TOOLS_OPENAI
from app.models.profile import Profile
from app.models.plan import MealPlan, DayPlan, Meal
from app.models.container import Container
from app.services.deviation_service import DeviationService
from app.services.ai_menu_service import AIMenuService

settings = get_settings()
logger = logging.getLogger("kbzhuy.agent")

SYSTEM_PROMPT = """Ты — персональный диетолог и нутрициолог приложения КБЖУЙ.
Твоя задача — помогать пользователю придерживаться рациона, не срываясь и без чувства вины.

Принципы общения:
- Говори по-русски, дружелюбно и без осуждения
- Будь конкретным: называй числа, контейнеры, время
- При отклонениях от плана — не ругай, а адаптируй
- Если пользователь съел лишнего — спокойно перераспредели kcal на неделю
- Отвечай кратко (2-4 предложения) если вопрос простой

Доступные инструменты позволяют тебе видеть план питания, хранилище и регистрировать отклонения.
Используй их проактивно, чтобы давать точные, персонализированные ответы.

Важно: если инструмент вернул {"error": "..."} — не вызывай его повторно. Сообщи пользователю об ошибке простым языком и предложи что делать (например, сначала создать план питания)."""


class AgentService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def chat(
        self,
        user_id: int,
        message: str,
        history: list[dict] | None = None,
    ) -> dict:
        """
        Single chat turn with the agent.
        Returns {reply: str, tool_calls: list, deviation_id: int | None}.
        """
        logger.info("agent.chat user=%d backend=%s message=%r",
                    user_id, "ollama" if settings.use_local_llm else "anthropic", message[:100])

        if settings.use_local_llm:
            return await self._chat_openai(user_id, message, history)
        return await self._chat_anthropic(user_id, message, history)

    # ------------------------------------------------------------------ #
    # Anthropic backend
    # ------------------------------------------------------------------ #

    async def _chat_anthropic(self, user_id: int, message: str, history: list[dict] | None) -> dict:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        messages = list(history or [])
        messages.append({"role": "user", "content": message})

        deviation_id: int | None = None
        tool_results_accumulated: list[dict] = []
        total_input_tokens = total_output_tokens = 0
        t0 = time.monotonic()

        for iteration in range(5):
            iter_start = time.monotonic()
            response = await client.messages.create(
                model=settings.ai_model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )
            iter_ms = round((time.monotonic() - iter_start) * 1000)
            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens
            logger.info("agent.llm iter=%d stop=%s in=%d out=%d time=%dms",
                        iteration, response.stop_reason,
                        response.usage.input_tokens, response.usage.output_tokens, iter_ms)

            if response.stop_reason == "end_turn":
                reply = self._extract_text_anthropic(response)
                logger.info("agent.done user=%d iters=%d total_in=%d total_out=%d time=%dms tools=%s",
                            user_id, iteration + 1, total_input_tokens, total_output_tokens,
                            round((time.monotonic() - t0) * 1000),
                            [t["tool"] for t in tool_results_accumulated])
                return {"reply": reply, "tool_calls": tool_results_accumulated, "deviation_id": deviation_id}

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_result_blocks = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    tool_start = time.monotonic()
                    result = await self._execute_tool(block.name, block.input, user_id)
                    logger.info("agent.tool name=%s time=%dms", block.name,
                                round((time.monotonic() - tool_start) * 1000))
                    if block.name == "register_deviation" and isinstance(result, dict):
                        deviation_id = result.get("id")
                    tool_results_accumulated.append({"tool": block.name, "result": result})
                    tool_result_blocks.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    })
                messages.append({"role": "user", "content": tool_result_blocks})
                continue

            logger.warning("agent.unexpected_stop reason=%s", response.stop_reason)
            break

        reply = self._extract_text_anthropic(response) if response else "Не удалось получить ответ."
        return {"reply": reply, "tool_calls": tool_results_accumulated, "deviation_id": deviation_id}

    def _extract_text_anthropic(self, response: anthropic.types.Message) -> str:
        for block in response.content:
            if hasattr(block, "text"):
                return block.text
        return ""

    # ------------------------------------------------------------------ #
    # OpenAI-compatible backend (Ollama)
    # ------------------------------------------------------------------ #

    async def _chat_openai(self, user_id: int, message: str, history: list[dict] | None) -> dict:
        client = openai.AsyncOpenAI(
            base_url=settings.local_llm_url,
            api_key="ollama",  # Ollama ignores this but openai SDK requires it
        )
        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in (history or []):
            messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": message})

        deviation_id: int | None = None
        tool_results_accumulated: list[dict] = []
        t0 = time.monotonic()

        for iteration in range(5):
            iter_start = time.monotonic()
            response = await client.chat.completions.create(
                model=settings.local_llm_model,
                max_tokens=1024,
                messages=messages,
                tools=TOOLS_OPENAI,
                tool_choice="auto",
            )
            iter_ms = round((time.monotonic() - iter_start) * 1000)
            msg = response.choices[0].message
            stop = response.choices[0].finish_reason
            logger.info("agent.llm iter=%d stop=%s time=%dms", iteration, stop, iter_ms)

            if stop == "stop" or not msg.tool_calls:
                reply = msg.content or "Не удалось получить ответ."
                logger.info("agent.done user=%d iters=%d time=%dms tools=%s",
                            user_id, iteration + 1,
                            round((time.monotonic() - t0) * 1000),
                            [t["tool"] for t in tool_results_accumulated])
                return {"reply": reply, "tool_calls": tool_results_accumulated, "deviation_id": deviation_id}

            if stop == "tool_calls":
                # Add assistant message with tool_calls
                messages.append(msg)
                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    try:
                        tool_input = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        tool_input = {}
                    tool_start = time.monotonic()
                    result = await self._execute_tool(tool_name, tool_input, user_id)
                    logger.info("agent.tool name=%s time=%dms", tool_name,
                                round((time.monotonic() - tool_start) * 1000))
                    if tool_name == "register_deviation" and isinstance(result, dict):
                        deviation_id = result.get("id")
                    tool_results_accumulated.append({"tool": tool_name, "result": result})
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    })
                continue

            logger.warning("agent.unexpected_stop reason=%s", stop)
            break

        reply = response.choices[0].message.content or "Не удалось получить ответ."
        return {"reply": reply, "tool_calls": tool_results_accumulated, "deviation_id": deviation_id}

    # ------------------------------------------------------------------ #
    # Tool dispatch
    # ------------------------------------------------------------------ #

    async def _execute_tool(self, tool_name: str, tool_input: dict, user_id: int) -> Any:
        if tool_name == "get_user_profile":
            return await self._get_user_profile(user_id)
        if tool_name == "get_today_plan":
            return await self._get_today_plan(user_id)
        if tool_name == "get_storage":
            return await self._get_storage(user_id)
        if tool_name == "register_deviation":
            return await self._register_deviation(user_id, tool_input)
        if tool_name == "recalculate_plan":
            return await self._recalculate_plan(user_id, tool_input)
        if tool_name == "get_expiring_soon":
            return await self._get_expiring_soon(user_id)
        if tool_name == "get_week_plan":
            return await self._get_week_plan(user_id)
        if tool_name == "update_meal_status":
            return await self._update_meal_status(user_id, tool_input)
        if tool_name == "update_container":
            return await self._update_container(user_id, tool_input)
        if tool_name == "build_meal_plan":
            return await self._build_meal_plan(user_id, tool_input)
        return {"error": f"unknown tool: {tool_name}"}

    # ------------------------------------------------------------------ #
    # Tool implementations
    # ------------------------------------------------------------------ #

    async def _get_user_profile(self, user_id: int) -> dict:
        result = await self.session.execute(
            select(Profile).where(Profile.user_id == user_id)
        )
        p = result.scalar_one_or_none()
        if not p:
            return {"error": "profile not found"}
        return {
            "goal": p.goal,
            "weight_kg": p.weight_kg,
            "height_cm": p.height_cm,
            "age": p.age,
            "activity_level": p.activity_level,
            "daily_targets": {
                "kcal": p.target_kcal,
                "protein": p.target_protein_g,
                "fat": p.target_fat_g,
                "carbs": p.target_carbs_g,
            },
            "eating_schedule": p.eating_schedule,
            "planned_deviations": p.planned_deviations,
        }

    async def _get_today_plan(self, user_id: int) -> dict:
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
        plan = result.scalars().first()
        if not plan:
            return {"error": "no active plan"}

        day_result = await self.session.execute(
            select(DayPlan)
            .where(DayPlan.plan_id == plan.id)
            .where(DayPlan.date == today)
            .options(selectinload(DayPlan.meals).selectinload(Meal.container))
        )
        day = day_result.scalar_one_or_none()
        if not day:
            return {"error": "no day plan for today"}

        return {
            "date": str(today),
            "daily_targets": plan.daily_targets,
            "meals": [
                {
                    "meal_id": m.id,
                    "meal_type": m.meal_type,
                    "status": m.status,
                    "kbzhu": m.kbzhu_actual,
                    "container_id": m.container_id,
                    "container_label": m.container.label if m.container else None,
                }
                for m in day.meals
            ],
        }

    async def _get_week_plan(self, user_id: int) -> dict:
        """Full active plan with all days/meals + IDs — for the agent to pick what to modify."""
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
        plan = result.scalars().first()
        if not plan:
            return {"error": "no active plan"}

        days_result = await self.session.execute(
            select(DayPlan)
            .where(DayPlan.plan_id == plan.id)
            .where(DayPlan.date >= today)
            .order_by(DayPlan.date)
            .options(selectinload(DayPlan.meals).selectinload(Meal.container))
        )
        days = days_result.scalars().all()

        return {
            "plan_id": plan.id,
            "period_start": str(plan.period_start),
            "period_end": str(plan.period_end),
            "daily_targets": plan.daily_targets,
            "days": [
                {
                    "date": str(d.date),
                    "notes": d.notes,
                    "meals": [
                        {
                            "meal_id": m.id,
                            "meal_type": m.meal_type,
                            "status": m.status,
                            "kcal": (m.kbzhu_actual or {}).get("kcal"),
                            "container_label": m.container.label if m.container else None,
                        }
                        for m in d.meals
                    ],
                }
                for d in days
            ],
        }

    async def _update_meal_status(self, user_id: int, inp: dict) -> dict:
        """Mark a meal as eaten/skipped/planned. Verifies meal belongs to the user."""
        meal_id = inp.get("meal_id")
        new_status = inp.get("status")
        reason = inp.get("reason") or ""
        if not meal_id or new_status not in ("eaten", "skipped", "planned"):
            return {"error": "meal_id and valid status required"}

        # Join Meal → DayPlan → MealPlan to check ownership
        result = await self.session.execute(
            select(Meal, DayPlan, MealPlan)
            .join(DayPlan, Meal.day_id == DayPlan.id)
            .join(MealPlan, DayPlan.plan_id == MealPlan.id)
            .where(Meal.id == meal_id)
            .where(MealPlan.user_id == user_id)
        )
        row = result.first()
        if not row:
            return {"error": f"meal {meal_id} not found for this user"}

        meal, day, _plan = row
        old_status = meal.status
        meal.status = new_status
        self.session.add(meal)

        if reason:
            note = f"{meal.meal_type} → {new_status}: {reason}"
            day.notes = f"{day.notes} | {note}" if day.notes else note
            self.session.add(day)

        await self.session.commit()
        return {
            "meal_id": meal.id,
            "meal_type": meal.meal_type,
            "date": str(day.date),
            "old_status": old_status,
            "new_status": new_status,
            "reason": reason,
            "ok": True,
        }

    async def _update_container(self, user_id: int, inp: dict) -> dict:
        """Update container status (filled/eaten/expired/frozen) and/or append a note."""
        label = inp.get("container_label")
        new_status = inp.get("status")
        note = inp.get("note")
        if not label:
            return {"error": "container_label required"}

        # Containers from old/cancelled plans share labels with current ones —
        # always pick the most recent one for this user.
        result = await self.session.execute(
            select(Container)
            .where(Container.user_id == user_id)
            .where(Container.label == label)
            .order_by(Container.created_at.desc())
            .limit(1)
        )
        container = result.scalars().first()
        if not container:
            return {"error": f"container '{label}' not found"}

        old_status = container.status
        if new_status:
            container.status = new_status
        if note:
            existing = container.contents_description or ""
            container.contents_description = (
                f"{existing} | {note}".strip(" |") if existing else note
            )
        self.session.add(container)
        await self.session.commit()
        return {
            "label": container.label,
            "old_status": old_status,
            "new_status": container.status,
            "description": container.contents_description,
            "ok": True,
        }

    async def _get_storage(self, user_id: int) -> dict:
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
        plan = result.scalars().first()
        if not plan:
            return {"containers": []}

        c_result = await self.session.execute(
            select(Container).where(Container.plan_id == plan.id)
        )
        containers = c_result.scalars().all()
        return {
            "containers": [
                {
                    "label": c.label,
                    "description": c.contents_description,
                    "status": c.status,
                    "expiry_date": str(c.expiry_date) if c.expiry_date else None,
                    "kbzhu": c.kbzhu,
                    "heating_instructions": c.heating_instructions,
                }
                for c in containers
            ]
        }

    async def _register_deviation(self, user_id: int, inp: dict) -> dict:
        svc = DeviationService(self.session)
        plan = await svc.get_active_plan(user_id)
        dev = await svc.register(
            user_id=user_id,
            description=inp.get("description", ""),
            deviation_type="spontaneous",
            kbzhu_impact={
                "kcal": inp.get("kcal", 0),
                "protein": inp.get("protein_g", 0),
                "fat": inp.get("fat_g", 0),
                "carbs": inp.get("carbs_g", 0),
            },
            plan_id=plan.id if plan else None,
        )
        return {"id": dev.id, "description": dev.description, "kcal_impact": inp.get("kcal", 0)}

    async def _recalculate_plan(self, user_id: int, inp: dict) -> dict:
        svc = DeviationService(self.session)
        return await svc.recalculate(user_id=user_id, deviation_id=inp["deviation_id"])

    async def _build_meal_plan(self, user_id: int, inp: dict) -> dict:
        """Tool: generate a meal plan via AI menu service with deterministic fallback."""
        week_start_str = inp.get("week_start")
        if not week_start_str:
            return {"error": "week_start is required"}
        try:
            week_start = date.fromisoformat(week_start_str)
        except ValueError:
            return {"error": f"invalid date: {week_start_str}"}

        svc = AIMenuService(self.session)
        result = await svc.generate(user_id=user_id, week_start=week_start, notes=inp.get("notes"))
        plan = result["plan"]
        return {
            "plan_id": plan.id,
            "period_start": plan.period_start.isoformat(),
            "period_end": plan.period_end.isoformat(),
            "daily_targets": plan.daily_targets,
            "source": result.get("source"),
            "summary": result.get("summary"),
            "status": "generated",
        }

    async def generate_plan(self, user_id: int, week_start: date) -> dict:
        """
        AI-assisted plan generation.
        Agent reads user profile, then calls build_meal_plan tool.
        Returns {plan_id, reply}.
        """
        svc = AIMenuService(self.session)
        result = await svc.generate(user_id=user_id, week_start=week_start)
        plan = result["plan"]
        return {
            "reply": result["summary"],
            "tool_calls": [{
                "tool": "build_meal_plan",
                "result": {
                    "plan_id": plan.id,
                    "period_start": plan.period_start.isoformat(),
                    "period_end": plan.period_end.isoformat(),
                    "source": result["source"],
                },
            }],
            "deviation_id": None,
        }

    async def _get_expiring_soon(self, user_id: int) -> dict:
        today = date.today()
        deadline = today + timedelta(days=2)
        result = await self.session.execute(
            select(MealPlan)
            .where(MealPlan.user_id == user_id)
            .where(MealPlan.period_start <= today)
            .where(MealPlan.period_end >= today)
            .where(MealPlan.status == "active")
            .order_by(MealPlan.created_at.desc())
            .limit(1)
        )
        plan = result.scalars().first()
        if not plan:
            return {"expiring": []}

        c_result = await self.session.execute(
            select(Container)
            .where(Container.plan_id == plan.id)
            .where(Container.expiry_date <= deadline)
            .where(Container.status == "filled")
        )
        containers = c_result.scalars().all()
        return {
            "expiring": [
                {
                    "label": c.label,
                    "description": c.contents_description,
                    "expiry_date": str(c.expiry_date),
                    "days_left": (c.expiry_date - today).days if c.expiry_date else None,
                }
                for c in containers
            ]
        }
