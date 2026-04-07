"""V3 run and delta endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.v3.store import AsyncEventStore


router = APIRouter()
_store = AsyncEventStore()


@router.get("/runs")
async def list_runs(limit: int = 50) -> dict[str, list[dict[str, object]]]:
    runs = await _store.list_runs(limit=limit)
    return {"runs": runs}


@router.get("/runs/{run_id}")
async def get_run(run_id: UUID) -> dict[str, object]:
    run = await _store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/runs/{run_id}/deltas")
async def get_run_deltas(run_id: UUID) -> dict[str, list[dict[str, object]]]:
    deltas = await _store.list_deltas(run_id)
    return {"deltas": deltas}
