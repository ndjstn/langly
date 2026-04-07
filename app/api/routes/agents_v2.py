"""Agent endpoints for v2 runtime."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.constants import AGENT_MODEL_MAPPING, GRANITE_MODELS
from app.runtime.models import AgentRole


router = APIRouter(prefix="/agents", tags=["agents-v2"])


class AgentSummary(BaseModel):
    """Agent summary for v2."""

    role: AgentRole
    name: str
    description: str
    model: str
    status: str = "ready"


class AgentListResponse(BaseModel):
    """List of v2 agents."""

    agents: list[AgentSummary]
    total: int


_AGENT_DESCRIPTIONS: dict[AgentRole, tuple[str, str]] = {
    AgentRole.PM: ("Project Manager", "Coordinates tasks and responses"),
    AgentRole.CODER: ("Coder", "Implements code changes"),
    AgentRole.ARCHITECT: ("Architect", "Designs system architecture"),
    AgentRole.TESTER: ("Tester", "Writes and validates tests"),
    AgentRole.REVIEWER: ("Reviewer", "Reviews code quality"),
    AgentRole.DOCS: ("Docs", "Writes documentation"),
    AgentRole.ROUTER: ("Router", "Routes tasks to specialists"),
    AgentRole.GUARDIAN: ("Guardian", "Safety validation"),
}


def _model_for_role(role: AgentRole) -> str:
    key = AGENT_MODEL_MAPPING.get(role.value, "dense_8b")
    return GRANITE_MODELS.get(key, key)


@router.get("/", response_model=AgentListResponse)
async def list_agents() -> AgentListResponse:
    agents = []
    for role in AgentRole:
        name, description = _AGENT_DESCRIPTIONS.get(
            role, (role.value, "Agent")
        )
        agents.append(
            AgentSummary(
                role=role,
                name=name,
                description=description,
                model=_model_for_role(role),
            )
        )
    return AgentListResponse(agents=agents, total=len(agents))


@router.get("/{role}", response_model=AgentSummary)
async def get_agent(role: AgentRole) -> AgentSummary:
    name, description = _AGENT_DESCRIPTIONS.get(
        role, (role.value, "Agent")
    )
    if role not in AgentRole:
        raise HTTPException(status_code=404, detail="agent_not_found")
    return AgentSummary(
        role=role,
        name=name,
        description=description,
        model=_model_for_role(role),
    )
