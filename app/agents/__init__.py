"""
Agents Package.

This package contains all agent implementations for the multi-agent
coding platform, including the PM, Coder, Architect, Tester, Reviewer,
Documentation, and Router agents.
"""
from app.agents.base import BaseAgent
from app.agents.coder_agent import CoderAgent
from app.agents.pm_agent import PMAgent
from app.agents.router_agent import (
    RouterAgent,
    get_route_destination,
    should_route,
)
from app.agents.specialist_agents import (
    ArchitectAgent,
    DocsAgent,
    ReviewerAgent,
    TesterAgent,
)

__all__ = [
    # Base
    "BaseAgent",
    # Agents
    "PMAgent",
    "CoderAgent",
    "ArchitectAgent",
    "TesterAgent",
    "ReviewerAgent",
    "DocsAgent",
    "RouterAgent",
    # Router utilities
    "should_route",
    "get_route_destination",
]
