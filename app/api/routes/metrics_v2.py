"""Metrics endpoint for v2 runtime."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.runtime.run_store import RunStore


router = APIRouter(prefix="/metrics", tags=["metrics-v2"])


class MetricsResponse(BaseModel):
    """Basic metrics for v2 runtime."""

    total_runs: int
    last_run_id: str | None = None
    last_run_status: str | None = None


@router.get("/", response_model=MetricsResponse)
async def metrics_v2() -> MetricsResponse:
    store = RunStore()
    runs = store.list_runs(limit=1)
    total = len(store.list_runs(limit=1000))
    if not runs:
        return MetricsResponse(total_runs=0)
    last = runs[0]
    return MetricsResponse(
        total_runs=total,
        last_run_id=last.get("id"),
        last_run_status=last.get("status"),
    )
