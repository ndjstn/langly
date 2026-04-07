"""Timeline endpoints for v2 runtime."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from app.runtime.run_store import RunStore


router = APIRouter(prefix="/timeline", tags=["timeline-v2"])


class RunTimelineResponse(BaseModel):
    """Timeline response for a run."""

    run_id: UUID
    deltas: list[dict]


class RecentTimelineResponse(BaseModel):
    """Recent timeline for multiple runs."""

    runs: list[dict]


@router.get("/recent", response_model=RecentTimelineResponse)
async def get_recent_timelines(limit: int = 5) -> RecentTimelineResponse:
    store = RunStore()
    runs = store.list_runs(limit=limit)
    for run in runs:
        run["deltas"] = store.list_deltas(UUID(run["id"]))
    return RecentTimelineResponse(runs=runs)


@router.get("/{run_id}", response_model=RunTimelineResponse)
async def get_run_timeline(run_id: UUID) -> RunTimelineResponse:
    store = RunStore()
    deltas = store.list_deltas(run_id)
    return RunTimelineResponse(run_id=run_id, deltas=deltas)
