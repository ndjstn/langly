"""Docs index endpoint for v2 runtime."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(prefix="/docs", tags=["docs-v2"])


class DocsIndexResponse(BaseModel):
    """Docs index response."""

    endpoints: list[str]


@router.get("/", response_model=DocsIndexResponse)
async def docs_index() -> DocsIndexResponse:
    return DocsIndexResponse(
        endpoints=[
            "/api/v2/workflows/run",
            "/api/v2/runs",
            "/api/v2/runs/{run_id}",
            "/api/v2/runs/{run_id}/deltas",
            "/api/v2/timeline/{run_id}",
            "/api/v2/timeline/recent",
            "/api/v2/snapshots/{session_id}",
            "/api/v2/snapshots/{session_id}/latest",
            "/api/v2/hitl/requests",
            "/api/v2/hitl/pending-tools",
            "/api/v2/ws/deltas",
            "/api/v2/health/v2",
            "/api/v2/health/ready",
            "/api/v2/health/live",
            "/api/v2/agents",
            "/api/v2/agents/{role}",
            "/api/v2/sessions/{session_id}/runs",
            "/api/v2/sessions/{session_id}/messages",
            "/api/v2/sessions/{session_id}/summary",
            "/api/v2/sessions/{session_id}/clear",
            "/api/v2/sessions/runs/{run_id}",
            "/api/v2/dashboard",
            "/api/v2/seed/run",
            "/api/v2/status",
            "/api/v2/config",
            "/api/v2/overview",
            "/api/v2/metrics",
            "/api/v2/reset",
            "/api/v2/cleanup/prune",
            "/api/v2/diagnostics",
            "/api/v2/summary",
            "/api/v2/models",
            "/api/v2/neo4j",
            "/api/v2/tools",
        ]
    )
