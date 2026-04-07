"""Run history endpoints for v2 runtime."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.runtime.run_store import RunStore


router = APIRouter(prefix="/runs", tags=["runs-v2"])


class RunDeltasResponse(BaseModel):
    """List of deltas for a run."""

    run_id: UUID
    deltas: list[dict]


class RunListResponse(BaseModel):
    """List runs response."""

    runs: list[dict]


class RunDetailResponse(BaseModel):
    """Run detail response."""

    run: dict


@router.get("/{run_id}/deltas", response_model=RunDeltasResponse)
async def get_run_deltas(run_id: UUID) -> RunDeltasResponse:
    store = RunStore()
    deltas = store.list_deltas(run_id)
    if not deltas:
        raise HTTPException(status_code=404, detail="run_not_found")
    return RunDeltasResponse(run_id=run_id, deltas=deltas)


@router.get("/", response_model=RunListResponse)
async def list_runs(limit: int = 50) -> RunListResponse:
    store = RunStore()
    runs = store.list_runs(limit=limit)
    for run in runs:
        summary = store.get_run_summary(UUID(run["id"]))
        run.update(summary)
    return RunListResponse(runs=runs)


@router.get("/{run_id}", response_model=RunDetailResponse)
async def get_run(run_id: UUID) -> RunDetailResponse:
    store = RunStore()
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run_not_found")
    run.update(store.get_run_summary(run_id))
    return RunDetailResponse(run=run)
