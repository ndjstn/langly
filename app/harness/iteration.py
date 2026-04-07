"""Iteration planning for harness runs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class IterationPlan:
    iterations: int
    reason: str
    auto: bool


class IterationPlanner:
    def __init__(self, max_iterations: int = 3) -> None:
        self.max_iterations = max(1, max_iterations)

    def plan(
        self,
        *,
        scope: dict[str, Any],
        tool_results: list[dict[str, Any]],
        requested: int | None,
    ) -> IterationPlan:
        if requested is not None:
            iterations = max(1, min(requested, self.max_iterations))
            return IterationPlan(iterations=iterations, reason="user_override", auto=False)

        difficulty = int(scope.get("difficulty", 1) or 1)
        intent = str(scope.get("intent", "")).lower()
        has_errors = any(tool.get("status") == "error" for tool in tool_results)

        score = 1
        if difficulty >= 3:
            score += 1
        if intent in {"debug", "review", "plan", "research"}:
            score += 1
        if has_errors:
            score += 1

        iterations = max(1, min(score, self.max_iterations))
        reason = "heuristic: difficulty/intent/tool-errors"
        return IterationPlan(iterations=iterations, reason=reason, auto=True)
