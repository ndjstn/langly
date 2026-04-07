"""Session endpoints for v2 runtime."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.runtime.run_store import RunStore
from app.runtime.snapshot_store import SnapshotStore


router = APIRouter(prefix="/sessions", tags=["sessions-v2"])


class SessionRunsResponse(BaseModel):
    """Runs associated with a session."""

    session_id: UUID
    runs: list[dict]


class SessionMessagesResponse(BaseModel):
    """Latest messages for a session."""

    session_id: UUID
    messages: list[dict]


class SessionSummaryResponse(BaseModel):
    """Summary for a session."""

    session_id: UUID
    runs: int
    last_run: dict | None
    tool_calls: int
    tasks: int
    pending_approvals: int


class SessionClearResponse(BaseModel):
    """Clear session response."""

    session_id: UUID
    runs_deleted: int
    deltas_deleted: int
    snapshots_deleted: int
    approvals_cleared: int


class RunDeleteResponse(BaseModel):
    """Delete run response."""

    run_id: UUID
    deltas_deleted: int
    approvals_cleared: int


@router.get("/{session_id}/runs", response_model=SessionRunsResponse)
async def list_session_runs(session_id: UUID, limit: int = 50) -> SessionRunsResponse:
    store = RunStore()
    runs = store.list_runs_for_session(session_id, limit=limit)
    return SessionRunsResponse(session_id=session_id, runs=runs)


@router.get("/{session_id}/messages", response_model=SessionMessagesResponse)
async def get_session_messages(session_id: UUID) -> SessionMessagesResponse:
    store = SnapshotStore()
    snapshots = store.list_snapshots(session_id, limit=1)
    if not snapshots:
        raise HTTPException(status_code=404, detail="snapshot_not_found")
    state = snapshots[0].get("state", {})
    messages = state.get("messages", [])
    return SessionMessagesResponse(session_id=session_id, messages=messages)


@router.get("/{session_id}/summary", response_model=SessionSummaryResponse)
async def get_session_summary(session_id: UUID) -> SessionSummaryResponse:
    run_store = RunStore()
    runs = run_store.list_runs_for_session(session_id, limit=100)
    last_run = runs[0] if runs else None

    tool_calls = 0
    tasks = 0
    for run in runs:
        summary = run_store.get_run_summary(UUID(run["id"]))
        tool_calls += summary.get("tool_calls", 0)
        tasks = max(tasks, summary.get("tasks", 0))

    from app.runtime.hitl import get_hitl_manager

    pending = get_hitl_manager().list_pending_tools()

    return SessionSummaryResponse(
        session_id=session_id,
        runs=len(runs),
        last_run=last_run,
        tool_calls=tool_calls,
        tasks=tasks,
        pending_approvals=len(pending),
    )


@router.post("/{session_id}/clear", response_model=SessionClearResponse)
async def clear_session(session_id: UUID) -> SessionClearResponse:
    run_store = RunStore()
    run_ids = run_store.delete_runs_for_session(session_id)
    deltas_deleted = run_store.delete_deltas_for_runs(run_ids)

    snapshot_store = SnapshotStore()
    snapshots_deleted = snapshot_store.delete_snapshots(session_id)

    from app.runtime.hitl import get_hitl_manager

    approvals_cleared = get_hitl_manager().clear_for_runs(run_ids)

    return SessionClearResponse(
        session_id=session_id,
        runs_deleted=len(run_ids),
        deltas_deleted=deltas_deleted,
        snapshots_deleted=snapshots_deleted,
        approvals_cleared=approvals_cleared,
    )


@router.delete("/runs/{run_id}", response_model=RunDeleteResponse)
async def delete_run(run_id: UUID) -> RunDeleteResponse:
    run_store = RunStore()
    deltas_deleted = run_store.delete_deltas_for_runs([str(run_id)])
    run_store.delete_run(run_id)
    from app.runtime.hitl import get_hitl_manager

    approvals_cleared = get_hitl_manager().clear_for_runs([str(run_id)])
    return RunDeleteResponse(
        run_id=run_id,
        deltas_deleted=deltas_deleted,
        approvals_cleared=approvals_cleared,
    )
