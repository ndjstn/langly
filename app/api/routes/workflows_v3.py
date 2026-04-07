"""V3 workflow endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.v3.runtime import get_engine


router = APIRouter()


class RunRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: UUID | None = None


@router.post("/workflows/run")
async def run_workflow(payload: RunRequest) -> dict[str, str | None]:
    engine = get_engine()
    run, response = await engine.run(payload.message, payload.session_id)
    return {
        "run_id": str(run.id),
        "session_id": str(run.session_id),
        "status": run.status.value,
        "response": response,
    }
