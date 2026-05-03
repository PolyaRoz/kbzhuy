import logging
import traceback

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.core.security import get_current_user_id
from app.ai.agent import AgentService
from app.ai.simple_agent import SimpleAgentService
from app.ai.gigachat_agent import GigachatAgentService, classify_tier

logger = logging.getLogger("kbzhuy.agent_route")


def _get_agent(session: AsyncSession, message: str = ""):
    """
    3-tier cost-optimised routing (when GigaChat is ON):
      free  → SimpleAgent  — rule-based, no API tokens
      lite  → GigaChat     — general chat, no tools
      pro   → GigaChat-Pro — function_calling for plan manipulation

    Fallback chain (when GigaChat is OFF):
      Anthropic / Ollama → SimpleAgent
    """
    s = get_settings()
    if s.use_gigachat and s.gigachat_credentials:
        tier = classify_tier(message)
        if tier == "free":
            return SimpleAgentService(session)
        elif tier == "lite":
            # Lite model = strip "-Pro" suffix from the configured pro model
            lite_model = s.gigachat_model.replace("-Pro", "") or "GigaChat"
            return GigachatAgentService(session, model=lite_model)
        else:  # "pro"
            return GigachatAgentService(session, model=s.gigachat_model)
    if s.anthropic_api_key or s.use_local_llm:
        return AgentService(session)
    return SimpleAgentService(session)

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None  # [{role, content}] for multi-turn context


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[dict] = []
    deviation_id: int | None = None


class AdaptRequest(BaseModel):
    reason: str         # e.g. "skipped lunch", "ate pizza"
    kcal_extra: int = 0


@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(
    body: ChatRequest,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    svc = _get_agent(session, body.message)
    try:
        result = await svc.chat(
            user_id=user_id,
            message=body.message,
            history=body.history,
        )
    except Exception as e:
        logger.error("agent_chat failed: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")
    return ChatResponse(**result)


@router.post("/adapt", response_model=ChatResponse)
async def adapt_plan(
    body: AdaptRequest,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Quick adapt: register deviation and return recalculated targets without full chat.
    Always uses Pro tier — this is a complex plan-manipulation operation.
    """
    # Build message first so routing can classify it correctly (forces "pro" tier)
    message = f"Перестрой план: {body.reason}."
    if body.kcal_extra:
        message += f" Это примерно {body.kcal_extra} лишних ккал."
    message += " Перестрой остаток недели."
    svc = _get_agent(session, message)
    try:
        result = await svc.chat(user_id=user_id, message=message)
    except Exception as e:
        logger.error("agent_chat failed: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")
    return ChatResponse(**result)
