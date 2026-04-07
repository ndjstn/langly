"""Model registry for V3 small-model routing."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    name: str
    max_params_b: float
    notes: str = ""


class SmallModelRegistry:
    """Role-to-model mapping with small-model constraints."""

    def __init__(self) -> None:
        self._roles: dict[str, list[ModelSpec]] = {
            "router": [ModelSpec("granite3-moe:1b", 1.0)],
            "planner": [ModelSpec("granite3.1-dense:2b", 2.0)],
            "coder": [ModelSpec("granite-code:3b", 3.0)],
            "reviewer": [ModelSpec("granite-code:3b", 3.0)],
            "tester": [ModelSpec("granite-code:3b", 3.0)],
            "docs": [ModelSpec("granite3.1-dense:2b", 2.0)],
            "summarizer": [
                ModelSpec("phi-3-mini:3b", 3.0, "preferred"),
                ModelSpec("granite3.1-dense:2b", 2.0, "fallback"),
            ],
            "embeddings": [ModelSpec("granite-embedding:278m", 0.278)],
        }

    def resolve(self, role: str) -> list[ModelSpec]:
        """Return ordered model specs for a role."""
        return list(self._roles.get(role, []))

    def roles(self) -> list[str]:
        return sorted(self._roles.keys())
