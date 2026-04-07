"""Reset endpoint for v2 runtime."""
from __future__ import annotations

import os

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(prefix="/reset", tags=["reset-v2"])


class ResetResponse(BaseModel):
    """Reset response."""

    status: str


@router.post("/", response_model=ResetResponse)
async def reset_v2() -> ResetResponse:
    db_path = os.environ.get("V2_DB_PATH", "./runtime_v2.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    return ResetResponse(status="ok")
