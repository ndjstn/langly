"""
Agent Management Endpoints for Langly API.

This module provides endpoints for agent status monitoring,
listing, and state inspection.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.schemas import AgentInfo, AgentType


if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


# =============================================================================
# Response Models
# =============================================================================


class AgentListResponse(BaseModel):
    """Response containing list of available agents."""

    agents: list[AgentInfo]
    total: int


class AgentStateResponse(BaseModel):
    """Response containing agent state information."""

    agent_type: AgentType
    name: str
    status: str
    current_task: str | None = None
    scratchpad: dict[str, Any] = Field(default_factory=dict)
    iteration_count: int = 0
    last_active: str | None = None


class AgentMetricsResponse(BaseModel):
    """Response containing agent performance metrics."""

    agent_type: AgentType
    total_invocations: int = 0
    successful_completions: int = 0
    failed_executions: int = 0
    average_response_time_ms: float = 0.0
    last_invocation: str | None = None


# =============================================================================
# Agent Registry (in-memory for now)
# =============================================================================

_AGENT_REGISTRY: dict[AgentType, AgentInfo] = {
    AgentType.PM: AgentInfo(
        agent_type=AgentType.PM,
        name="Project Manager",
        description="Coordinates task delegation and workflow management",
        model="granite3.1-dense:8b",
        status="ready",
    ),
    AgentType.CODER: AgentInfo(
        agent_type=AgentType.CODER,
        name="Coder",
        description="Implements code solutions and modifications",
        model="granite-code:8b",
        status="ready",
    ),
    AgentType.ARCHITECT: AgentInfo(
        agent_type=AgentType.ARCHITECT,
        name="Architect",
        description="Designs system architecture and technical solutions",
        model="granite3.1-dense:8b",
        status="ready",
    ),
    AgentType.TESTER: AgentInfo(
        agent_type=AgentType.TESTER,
        name="Tester",
        description="Creates and executes test cases",
        model="granite-code:8b",
        status="ready",
    ),
    AgentType.REVIEWER: AgentInfo(
        agent_type=AgentType.REVIEWER,
        name="Code Reviewer",
        description="Reviews code for quality and best practices",
        model="granite3.1-dense:8b",
        status="ready",
    ),
    AgentType.DOCS: AgentInfo(
        agent_type=AgentType.DOCS,
        name="Documentation",
        description="Generates and maintains documentation",
        model="granite3.1-dense:2b",
        status="ready",
    ),
    AgentType.ROUTER: AgentInfo(
        agent_type=AgentType.ROUTER,
        name="Router",
        description="Routes tasks to appropriate specialist agents",
        model="granite3.1-moe:1b",
        status="ready",
    ),
    AgentType.GUARDIAN: AgentInfo(
        agent_type=AgentType.GUARDIAN,
        name="Guardian",
        description="Validates content for safety and compliance",
        model="granite-guardian:2b",
        status="ready",
    ),
}

# In-memory agent metrics (would be persisted in production)
_AGENT_METRICS: dict[AgentType, dict[str, Any]] = {
    agent_type: {
        "total_invocations": 0,
        "successful_completions": 0,
        "failed_executions": 0,
        "response_times": [],
        "last_invocation": None,
    }
    for agent_type in AgentType
}


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/", response_model=AgentListResponse)
async def list_agents() -> AgentListResponse:
    """
    List all available agents in the system.

    Returns:
        List of agent information.
    """
    agents = list(_AGENT_REGISTRY.values())
    return AgentListResponse(
        agents=agents,
        total=len(agents),
    )


@router.get("/{agent_type}", response_model=AgentInfo)
async def get_agent(agent_type: AgentType) -> AgentInfo:
    """
    Get information about a specific agent.

    Args:
        agent_type: The type of agent to retrieve.

    Returns:
        Agent information.

    Raises:
        HTTPException: If agent type not found.
    """
    if agent_type not in _AGENT_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"Agent type {agent_type} not found",
        )
    return _AGENT_REGISTRY[agent_type]


@router.get("/{agent_type}/state", response_model=AgentStateResponse)
async def get_agent_state(agent_type: AgentType) -> AgentStateResponse:
    """
    Get the current state of a specific agent.

    Args:
        agent_type: The type of agent.

    Returns:
        Agent state information.

    Raises:
        HTTPException: If agent type not found.
    """
    if agent_type not in _AGENT_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"Agent type {agent_type} not found",
        )

    agent_info = _AGENT_REGISTRY[agent_type]

    # In a real implementation, this would fetch from the workflow state
    return AgentStateResponse(
        agent_type=agent_type,
        name=agent_info.name,
        status=agent_info.status,
        current_task=None,
        scratchpad={},
        iteration_count=0,
        last_active=None,
    )


@router.get("/{agent_type}/metrics", response_model=AgentMetricsResponse)
async def get_agent_metrics(agent_type: AgentType) -> AgentMetricsResponse:
    """
    Get performance metrics for a specific agent.

    Args:
        agent_type: The type of agent.

    Returns:
        Agent metrics.

    Raises:
        HTTPException: If agent type not found.
    """
    if agent_type not in _AGENT_METRICS:
        raise HTTPException(
            status_code=404,
            detail=f"Agent type {agent_type} not found",
        )

    metrics = _AGENT_METRICS[agent_type]

    # Calculate average response time
    response_times = metrics.get("response_times", [])
    avg_response_time = (
        sum(response_times) / len(response_times)
        if response_times
        else 0.0
    )

    return AgentMetricsResponse(
        agent_type=agent_type,
        total_invocations=metrics.get("total_invocations", 0),
        successful_completions=metrics.get("successful_completions", 0),
        failed_executions=metrics.get("failed_executions", 0),
        average_response_time_ms=avg_response_time,
        last_invocation=metrics.get("last_invocation"),
    )


@router.post("/{agent_type}/reset")
async def reset_agent(agent_type: AgentType) -> dict[str, str]:
    """
    Reset an agent's state and metrics.

    Args:
        agent_type: The type of agent to reset.

    Returns:
        Reset confirmation.

    Raises:
        HTTPException: If agent type not found.
    """
    if agent_type not in _AGENT_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"Agent type {agent_type} not found",
        )

    # Reset metrics
    _AGENT_METRICS[agent_type] = {
        "total_invocations": 0,
        "successful_completions": 0,
        "failed_executions": 0,
        "response_times": [],
        "last_invocation": None,
    }

    logger.info(f"Reset agent {agent_type}")

    return {
        "agent_type": agent_type.value,
        "status": "reset",
        "message": f"Agent {agent_type.value} has been reset",
    }


@router.get("/types/list")
async def list_agent_types() -> dict[str, list[str]]:
    """
    List all available agent types.

    Returns:
        List of agent type names.
    """
    return {
        "agent_types": [agent_type.value for agent_type in AgentType],
    }
