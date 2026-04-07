"""Status endpoint for v2 runtime."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.runtime.hitl import get_hitl_manager
from app.runtime.run_store import RunStore
from app.runtime.snapshot_store import SnapshotStore


router = APIRouter(prefix="/status", tags=["status-v2"])


class StatusResponse(BaseModel):
    """Status response for v2 runtime."""

    runs: int
    pending_approvals: int
    snapshots: int


@router.get("/", response_model=StatusResponse)
async def status_v2() -> StatusResponse:
    run_store = RunStore()
    runs = run_store.list_runs(limit=1000)

    hitl = get_hitl_manager()
    pending = hitl.list_pending_tools()

    snapshot_store = SnapshotStore()
    snapshots = 0
    for run in runs:
        snapshots += len(snapshot_store.list_snapshots(run["session_id"], limit=1))

    return StatusResponse(
        runs=len(runs),
        pending_approvals=len(pending),
        snapshots=snapshots,
    )
