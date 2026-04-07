"""Workflow v2 endpoints for Langly runtime."""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.runtime import RunStatus, WorkflowEngine
from app.runtime.errors import LanglyError


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflows", tags=["workflows-v2"])


class WorkflowRunRequest(BaseModel):
    """Request to run a v2 workflow."""

    message: str = Field(..., min_length=1)
    session_id: UUID | None = None


class WorkflowRunResponse(BaseModel):
    """Response from a v2 workflow run."""

    session_id: UUID
    response: str
    run_id: UUID
    status: RunStatus


@router.post("/run", response_model=WorkflowRunResponse)
async def run_workflow(request: WorkflowRunRequest) -> WorkflowRunResponse:
    """Run a single-step v2 workflow (PM response)."""
    engine = WorkflowEngine.get_instance()

    try:
        run, _state, response_text = await engine.run(
            message=request.message,
            session_id=request.session_id,
        )
    except LanglyError as exc:
        logger.error("v2 workflow failed: %s", exc)
        raise HTTPException(
            status_code=503 if exc.retryable else 500,
            detail=exc.as_dict(),
        ) from exc
    except Exception as exc:
        logger.exception("v2 workflow crashed")
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": str(exc)},
        ) from exc

    return WorkflowRunResponse(
        session_id=run.session_id,
        response=response_text,
        run_id=run.id,
        status=run.status,
    )
