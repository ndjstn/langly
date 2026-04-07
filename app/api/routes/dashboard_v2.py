"""Aggregate dashboard endpoint for v2 runtime."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from app.runtime.hitl import get_hitl_manager
from app.runtime.run_store import RunStore
from app.runtime.snapshot_store import SnapshotStore


router = APIRouter(prefix="/dashboard", tags=["dashboard-v2"])


class DashboardResponse(BaseModel):
    """Dashboard aggregation response."""

    runs: list[dict]
    pending_approvals: list[dict]
    snapshots: list[dict]


@router.get("/", response_model=DashboardResponse)
async def get_dashboard() -> DashboardResponse:
    store = RunStore()
    runs = store.list_runs(limit=10)
    for run in runs:
        summary = store.get_run_summary(run_id=UUID(run["id"]))
        run.update(summary)

    hitl = get_hitl_manager()
    pending = hitl.list_pending_tools()

    snapshot_store = SnapshotStore()
    snapshots = []
    for run in runs:
        session_id = UUID(run["session_id"])
        latest = snapshot_store.list_snapshots(session_id, limit=1)
        if latest:
            snapshots.append(latest[0])

    return DashboardResponse(
        runs=runs,
        pending_approvals=pending,
        snapshots=snapshots,
    )
