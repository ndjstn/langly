"""Diagnostics endpoint for v2 runtime."""
from __future__ import annotations

import os

from fastapi import APIRouter
from pydantic import BaseModel

from app.runtime.run_store import RunStore


router = APIRouter(prefix="/diagnostics", tags=["diagnostics-v2"])


class DiagnosticsResponse(BaseModel):
    """Diagnostics response for v2 runtime."""

    db_path: str
    sqlite_status: str


@router.get("/", response_model=DiagnosticsResponse)
async def diagnostics_v2() -> DiagnosticsResponse:
    db_path = os.environ.get("V2_DB_PATH", "./runtime_v2.db")
    status = "ok"
    try:
        RunStore()
    except Exception:
        status = "error"
    return DiagnosticsResponse(db_path=db_path, sqlite_status=status)
