"""Cleanup endpoints for v2 runtime."""
from __future__ import annotations

import os

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(prefix="/cleanup", tags=["cleanup-v2"])


class CleanupResponse(BaseModel):
    """Cleanup response."""

    status: str


@router.post("/prune", response_model=CleanupResponse)
async def prune_runs(max_runs: int = 100) -> CleanupResponse:
    db_path = os.environ.get("V2_DB_PATH", "./runtime_v2.db")
    if not os.path.exists(db_path):
        return CleanupResponse(status="no_db")

    import sqlite3

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT id FROM runs ORDER BY created_at DESC")
    rows = cur.fetchall()
    if len(rows) <= max_runs:
        return CleanupResponse(status="nothing_to_prune")

    prune = [row[0] for row in rows[max_runs:]]
    cur.executemany("DELETE FROM runs WHERE id = ?", [(rid,) for rid in prune])
    cur.executemany("DELETE FROM run_deltas WHERE run_id = ?", [(rid,) for rid in prune])
    conn.commit()
    return CleanupResponse(status=f"pruned_{len(prune)}")
