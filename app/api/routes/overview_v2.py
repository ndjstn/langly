"""Overview endpoint for v2 runtime."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from app.runtime.hitl import get_hitl_manager
from app.runtime.run_store import RunStore
from app.runtime.snapshot_store import SnapshotStore


router = APIRouter(prefix="/overview", tags=["overview-v2"])


class OverviewResponse(BaseModel):
    """Overview aggregation response."""

    runs: list[dict]
    pending_approvals: list[dict]
    recent_deltas: list[dict]
    latest_snapshots: list[dict]


@router.get("/", response_model=OverviewResponse)
async def overview(limit: int = 5, deltas_limit: int = 50) -> OverviewResponse:
    store = RunStore()
    runs = store.list_runs(limit=limit)
    for run in runs:
        summary = store.get_run_summary(run_id=UUID(run["id"]))
        run.update(summary)

    hitl = get_hitl_manager()
    pending = hitl.list_pending_tools()

    recent_deltas: list[dict] = []
    for run in runs:
        recent_deltas.extend(store.list_deltas(UUID(run["id"])))
    recent_deltas = recent_deltas[-deltas_limit:]

    snapshot_store = SnapshotStore()
    latest_snapshots: list[dict] = []
    for run in runs:
        session_id = UUID(run["session_id"])
        latest = snapshot_store.list_snapshots(session_id, limit=1)
        if latest:
            latest_snapshots.append(latest[0])

    return OverviewResponse(
        runs=runs,
        pending_approvals=pending,
        recent_deltas=recent_deltas,
        latest_snapshots=latest_snapshots,
    )
