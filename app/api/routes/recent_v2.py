"""Recent deltas endpoint for v2 runtime."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.runtime.run_store import RunStore


router = APIRouter(prefix="/recent", tags=["recent-v2"])


class RecentDeltasResponse(BaseModel):
    """Recent deltas response."""

    deltas: list[dict]


@router.get("/deltas", response_model=RecentDeltasResponse)
async def get_recent_deltas(limit: int = 50) -> RecentDeltasResponse:
    store = RunStore()
    runs = store.list_runs(limit=limit)
    deltas: list[dict] = []
    for run in runs:
        run_id = run["id"]
        deltas.extend(store.list_deltas(run_id))
    return RecentDeltasResponse(deltas=deltas[-limit:])
