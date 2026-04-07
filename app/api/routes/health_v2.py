"""Health endpoints for v2 runtime."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.llm.ollama_client import check_ollama_health
from app.runtime.run_store import RunStore


router = APIRouter(prefix="/health", tags=["health-v2"])


class V2HealthResponse(BaseModel):
    """Health check response for v2 runtime."""

    status: str
    timestamp: str
    ollama: dict
    sqlite: dict


class V2ProbeResponse(BaseModel):
    """Minimal probe response for readiness/liveness."""

    status: str
    timestamp: str


async def _collect_health() -> tuple[str, dict, dict]:
    ollama = await check_ollama_health()
    sqlite = {"status": "ok"}
    try:
        RunStore()
    except Exception as exc:
        sqlite = {"status": "error", "error": str(exc)}

    status = (
        "healthy"
        if ollama.get("healthy") and sqlite["status"] == "ok"
        else "degraded"
    )
    return status, ollama, sqlite


@router.get("/v2", response_model=V2HealthResponse)
async def health_v2() -> V2HealthResponse:
    status, ollama, sqlite = await _collect_health()
    return V2HealthResponse(
        status=status,
        timestamp=datetime.utcnow().isoformat(),
        ollama=ollama,
        sqlite=sqlite,
    )


@router.get("/ready", response_model=V2ProbeResponse)
async def readiness_v2() -> V2ProbeResponse:
    status, _ollama, _sqlite = await _collect_health()
    return V2ProbeResponse(
        status="ok" if status == "healthy" else "degraded",
        timestamp=datetime.utcnow().isoformat(),
    )


@router.get("/live", response_model=V2ProbeResponse)
async def liveness_v2() -> V2ProbeResponse:
    status, _ollama, _sqlite = await _collect_health()
    return V2ProbeResponse(
        status="ok" if status == "healthy" else "degraded",
        timestamp=datetime.utcnow().isoformat(),
    )
