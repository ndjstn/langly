"""Summary endpoint for v2 runtime."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.runtime.run_store import RunStore
from app.runtime.hitl import get_hitl_manager


router = APIRouter(prefix="/summary", tags=["summary-v2"])


class SummaryResponse(BaseModel):
    """Summary response for v2 runtime."""

    total_runs: int
    pending_approvals: int
    last_run: dict | None


@router.get("/", response_model=SummaryResponse)
async def summary_v2() -> SummaryResponse:
    store = RunStore()
    runs = store.list_runs(limit=1)
    total = len(store.list_runs(limit=1000))

    hitl = get_hitl_manager()
    pending = hitl.list_pending_tools()

    last_run = runs[0] if runs else None

    return SummaryResponse(
        total_runs=total,
        pending_approvals=len(pending),
        last_run=last_run,
    )
