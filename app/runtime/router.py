"""Routing logic for v2 runtime."""
from __future__ import annotations

import logging
from typing import Iterable

from langchain_core.messages import HumanMessage, SystemMessage

from app.runtime.llm import GraniteLLMProvider
from app.runtime.models import AgentRole


logger = logging.getLogger(__name__)


ROUTE_KEYWORDS: dict[AgentRole, Iterable[str]] = {
    AgentRole.CODER: (
        "write",
        "code",
        "implement",
        "function",
        "class",
        "module",
        "bug",
        "fix",
        "refactor",
        "optimize",
        "python",
        "javascript",
    ),
    AgentRole.ARCHITECT: (
        "design",
        "architecture",
        "system",
        "structure",
        "schema",
        "diagram",
        "service",
        "api",
    ),
    AgentRole.TESTER: (
        "test",
        "testing",
        "pytest",
        "coverage",
        "validate",
        "verify",
    ),
    AgentRole.REVIEWER: (
        "review",
        "audit",
        "inspect",
        "quality",
        "best practice",
    ),
    AgentRole.DOCS: (
        "document",
        "documentation",
        "readme",
        "guide",
        "explain",
    ),
}


class Router:
    """Route tasks to specialist agents using keywords or LLM."""

    def __init__(self, provider: GraniteLLMProvider) -> None:
        self._provider = provider

    def keyword_route(self, content: str) -> AgentRole | None:
        content_lower = content.lower()
        scores: dict[AgentRole, int] = {role: 0 for role in ROUTE_KEYWORDS}

        for role, keywords in ROUTE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in content_lower:
                    scores[role] += 1

        if not scores:
            return None

        max_score = max(scores.values())
        if max_score == 0:
            return None

        winners = [role for role, score in scores.items() if score == max_score]
        if len(winners) == 1 and max_score >= 2:
            return winners[0]

        return None

    async def llm_route(self, content: str) -> AgentRole:
        model = self._provider.get_model(AgentRole.ROUTER)
        system_prompt = (
            "You are a routing agent. Choose the single best agent: "
            "pm, coder, architect, tester, reviewer, docs. "
            "Respond with the agent name only."
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Route this request:\n\n{content}"),
        ]

        response = await model.ainvoke(messages)
        text = str(getattr(response, "content", response)).strip().lower()

        for role in (
            AgentRole.PM,
            AgentRole.CODER,
            AgentRole.ARCHITECT,
            AgentRole.TESTER,
            AgentRole.REVIEWER,
            AgentRole.DOCS,
        ):
            if role.value in text:
                return role

        return AgentRole.PM

    async def route(self, content: str) -> AgentRole:
        fast = self.keyword_route(content)
        if fast:
            logger.info("Router keyword route -> %s", fast.value)
            return fast

        try:
            slow = await self.llm_route(content)
            logger.info("Router LLM route -> %s", slow.value)
            return slow
        except Exception as exc:
            logger.warning("Router LLM failed, defaulting to PM: %s", exc)
            return AgentRole.PM
