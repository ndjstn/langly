"""Model routing policy for harness runs."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.core.constants import AGENT_MODEL_MAPPING


class ModelRoutingDecision(BaseModel):
    overrides: dict[str, str]
    reason: str


class ModelRoutingPolicy:
    def __init__(self) -> None:
        self._defaults = dict(AGENT_MODEL_MAPPING)

    def plan(self, scope: dict[str, Any]) -> ModelRoutingDecision:
        difficulty = int(scope.get("difficulty", 1) or 1)
        intent = str(scope.get("intent", "")).lower()
        overrides: dict[str, str] = {}
        reason_parts: list[str] = []

        if difficulty <= 2 and intent in {"plan", "research", "summary", "explain"}:
            overrides["pm"] = "dense_2b"
            reason_parts.append("pm->dense_2b for low difficulty")
        elif difficulty >= 4:
            overrides["pm"] = "dense_8b"
            reason_parts.append("pm->dense_8b for high difficulty")

        if intent in {"debug", "code", "refactor"}:
            overrides["coder"] = "code_8b" if difficulty >= 3 else "code_3b"
            reason_parts.append("coder->code model for code intent")

        reason = "; ".join(reason_parts) if reason_parts else "default mapping"
        return ModelRoutingDecision(overrides=overrides, reason=reason)
