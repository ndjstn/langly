"""Legacy chat endpoint backed by v2 runtime."""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.runtime import RunStatus, WorkflowEngine
from app.runtime.errors import LanglyError


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """Legacy chat request."""

    message: str = Field(..., min_length=1)
    session_id: UUID | None = None


class ChatResponse(BaseModel):
    """Legacy chat response."""

    session_id: UUID
    response: str
    run_id: UUID
    status: RunStatus


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Handle legacy chat by delegating to v2 workflow engine."""
    engine = WorkflowEngine.get_instance()

    try:
        run, _state, response_text = await engine.run(
            message=request.message,
            session_id=request.session_id,
        )
    except LanglyError as exc:
        logger.error("legacy chat failed: %s", exc)
        raise HTTPException(
            status_code=503 if exc.retryable else 500,
            detail=exc.as_dict(),
        ) from exc
    except Exception as exc:
        logger.exception("legacy chat crashed")
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": str(exc)},
        ) from exc

    return ChatResponse(
        session_id=run.session_id,
        response=response_text,
        run_id=run.id,
        status=run.status,
    )
