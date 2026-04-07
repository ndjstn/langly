"""Neo4j diagnostics endpoint for v2 runtime."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.memory.neo4j_client import get_neo4j_client


router = APIRouter(prefix="/neo4j", tags=["neo4j-v2"])


class Neo4jStatusResponse(BaseModel):
    """Neo4j status response."""

    enabled: bool
    status: str
    details: dict | None = None


@router.get("/", response_model=Neo4jStatusResponse)
async def neo4j_status() -> Neo4jStatusResponse:
    settings = get_settings()
    if not settings.enable_neo4j_memory:
        return Neo4jStatusResponse(enabled=False, status="disabled")

    client = get_neo4j_client()
    health = await client.health_check()
    status = health.get("status", "unknown")
    return Neo4jStatusResponse(
        enabled=True,
        status=status,
        details=health,
    )
