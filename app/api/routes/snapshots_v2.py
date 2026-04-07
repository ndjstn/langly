"""Snapshot endpoints for v2 runtime."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.runtime.snapshot_store import SnapshotStore


router = APIRouter(prefix="/snapshots", tags=["snapshots-v2"])


class SnapshotListResponse(BaseModel):
    """List snapshots response."""

    session_id: UUID
    snapshots: list[dict]


class SnapshotLatestResponse(BaseModel):
    """Latest snapshot response."""

    session_id: UUID
    snapshot: dict


@router.get("/{session_id}", response_model=SnapshotListResponse)
async def list_snapshots(session_id: UUID, limit: int = 20) -> SnapshotListResponse:
    store = SnapshotStore()
    snapshots = store.list_snapshots(session_id, limit=limit)
    return SnapshotListResponse(session_id=session_id, snapshots=snapshots)


@router.get("/{session_id}/latest", response_model=SnapshotLatestResponse)
async def get_latest_snapshot(session_id: UUID) -> SnapshotLatestResponse:
    store = SnapshotStore()
    snapshots = store.list_snapshots(session_id, limit=1)
    if not snapshots:
        raise HTTPException(status_code=404, detail="snapshot_not_found")
    return SnapshotLatestResponse(session_id=session_id, snapshot=snapshots[0])
