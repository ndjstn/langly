"""Seed endpoints for v2 runtime."""
from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter
from pydantic import BaseModel

from app.runtime.run_store import RunStore
from app.runtime.models import RunStatus, WorkflowRun


router = APIRouter(prefix="/seed", tags=["seed-v2"])


class SeedRunResponse(BaseModel):
    """Seed run response."""

    run_id: UUID
    session_id: UUID


@router.post("/run", response_model=SeedRunResponse)
async def seed_run() -> SeedRunResponse:
    run = WorkflowRun(session_id=uuid4(), status=RunStatus.CREATED)
    RunStore().save_run(run)
    return SeedRunResponse(run_id=run.id, session_id=run.session_id)
