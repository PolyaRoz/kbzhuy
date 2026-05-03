from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.core.security import get_current_user_id
from app.ai.agent import AgentService
from app.ai.simple_agent import SimpleAgentService


def _get_agent(session: AsyncSession):
    """Return SimpleAgentService unless a real API key is configured."""
    settings = get_settings()
    if settings.anthropic_api_key or settings.use_local_llm:
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
    svc = _get_agent(session)
    try:
        result = await svc.chat(
            user_id=user_id,
            message=body.message,
            history=body.history,
        )
    except Exception as e:
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
    """
    svc = _get_agent(session)
    message = f"Я отклонился от плана: {body.reason}."
    if body.kcal_extra:
        message += f" Это примерно {body.kcal_extra} лишних ккал."
    message += " Перестрой остаток недели."
    try:
        result = await svc.chat(user_id=user_id, message=message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")
    return ChatResponse(**result)
