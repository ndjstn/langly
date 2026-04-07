"""Baseline graph nodes for V3."""
from __future__ import annotations

from typing import Iterable

from app.v3.graph import GraphNode, NodeContext, NodeResult
from app.v3.models import Task


class RouterNode(GraphNode):
    """Keyword router for specialist selection."""

    def __init__(self) -> None:
        self._keywords: dict[str, Iterable[str]] = {
            "coder": (
                "code",
                "implement",
                "bug",
                "fix",
                "refactor",
                "optimize",
            ),
            "architect": ("design", "architecture", "diagram", "system"),
            "tester": ("test", "verify", "coverage"),
            "reviewer": ("review", "audit", "quality"),
            "docs": ("document", "readme", "guide"),
        }

    @property
    def name(self) -> str:
        return "router"

    async def run(self, context: NodeContext, input_text: str) -> NodeResult:
        lowered = input_text.lower()
        best = "planner"
        best_score = 0
        for role, keywords in self._keywords.items():
            score = sum(1 for word in keywords if word in lowered)
            if score > best_score:
                best = role
                best_score = score
        context.state["route_role"] = best
        return NodeResult(output=best)


class PlannerNode(GraphNode):
    """Split a request into task units."""

    @property
    def name(self) -> str:
        return "planner"

    async def run(self, context: NodeContext, input_text: str) -> NodeResult:
        raw = [line.strip() for line in input_text.split("\n") if line.strip()]
        tasks = raw or [input_text]
        role = context.state.get("route_role")
        planned = [Task(description=item, assigned_agent=role) for item in tasks]
        return NodeResult(tasks=planned)
