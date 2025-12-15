"""
Health and Status Endpoints for Langly API.

This module provides health check and status monitoring endpoints
for the multi-agent system.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.llm.ollama_client import (
    check_ollama_health,
    get_ollama_client,
)
from app.memory.neo4j_client import get_neo4j_client


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


# =============================================================================
# Response Models
# =============================================================================


class ServiceStatus(BaseModel):
    """Status of a single service."""

    name: str
    status: str  # "healthy", "degraded", "unhealthy"
    latency_ms: float | None = None
    details: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    """Overall health check response."""

    status: str
    timestamp: str
    version: str
    services: list[ServiceStatus]


class SystemInfo(BaseModel):
    """System information response."""

    app_name: str
    environment: str
    debug: bool
    ollama_host: str
    neo4j_uri: str


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/", response_model=HealthResponse)
async def health_check(
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """
    Perform a comprehensive health check of all services.

    Returns:
        Health status of the system and all dependencies.
    """
    services: list[ServiceStatus] = []
    overall_status = "healthy"

    # Check Ollama
    try:
        start_time = datetime.now()
        ollama_health = await check_ollama_health()
        latency = (datetime.now() - start_time).total_seconds() * 1000

        if ollama_health.get("healthy", False):
            services.append(
                ServiceStatus(
                    name="ollama",
                    status="healthy",
                    latency_ms=latency,
                    details=ollama_health,
                )
            )
        else:
            services.append(
                ServiceStatus(
                    name="ollama",
                    status="degraded",
                    latency_ms=latency,
                    details=ollama_health,
                )
            )
            overall_status = "degraded"
    except Exception as e:
        logger.error(f"Ollama health check failed: {e}")
        services.append(
            ServiceStatus(
                name="ollama",
                status="unhealthy",
                details={"error": str(e)},
            )
        )
        overall_status = "degraded"

    # Check Neo4j
    try:
        neo4j_client = get_neo4j_client()
        start_time = datetime.now()
        neo4j_health = await neo4j_client.health_check()
        latency = (datetime.now() - start_time).total_seconds() * 1000

        if neo4j_health.get("status") == "healthy":
            services.append(
                ServiceStatus(
                    name="neo4j",
                    status="healthy",
                    latency_ms=latency,
                    details=neo4j_health,
                )
            )
        else:
            services.append(
                ServiceStatus(
                    name="neo4j",
                    status="degraded",
                    latency_ms=latency,
                    details=neo4j_health,
                )
            )
            if overall_status == "healthy":
                overall_status = "degraded"
    except Exception as e:
        logger.error(f"Neo4j health check failed: {e}")
        services.append(
            ServiceStatus(
                name="neo4j",
                status="unhealthy",
                details={"error": str(e)},
            )
        )
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow().isoformat(),
        version="0.1.0",
        services=services,
    )


@router.get("/liveness")
async def liveness() -> dict[str, str]:
    """
    Simple liveness probe for container orchestration.

    Returns:
        Simple OK response indicating the service is alive.
    """
    return {"status": "ok"}


@router.get("/readiness")
async def readiness() -> dict[str, str]:
    """
    Readiness probe for container orchestration.

    Checks if the service is ready to accept traffic.

    Returns:
        Ready status or error.
    """
    try:
        # Quick check that core services are reachable
        ollama_health = await check_ollama_health()

        if not ollama_health.get("healthy", False):
            raise HTTPException(
                status_code=503,
                detail="Ollama service not ready",
            )

        return {"status": "ready"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Service not ready: {str(e)}",
        ) from e


@router.get("/info", response_model=SystemInfo)
async def system_info(
    settings: Settings = Depends(get_settings),
) -> SystemInfo:
    """
    Get system information and configuration.

    Returns:
        System configuration information.
    """
    return SystemInfo(
        app_name=settings.app_name,
        environment=settings.environment,
        debug=settings.debug,
        ollama_host=settings.ollama_host,
        neo4j_uri=settings.neo4j_uri,
    )


@router.get("/models")
async def list_available_models() -> dict[str, Any]:
    """
    List available Ollama models.

    Returns:
        List of available models.
    """
    try:
        ollama_client = get_ollama_client()
        models = await ollama_client.list_models()
        return {"models": models, "count": len(models)}
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list models: {str(e)}",
        ) from e
