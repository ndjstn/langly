"""Critical thinking katas for harness agents."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class KataPhase(BaseModel):
    name: str
    steps: list[str] = Field(default_factory=list)


class KataPlan(BaseModel):
    phases: list[KataPhase] = Field(default_factory=list)
    intent: str = ""


class KataEngine:
    DEFAULT_BEFORE = [
        "Clarify the goal and constraints",
        "Identify required tools and data",
        "Check for missing context",
    ]
    DEFAULT_DURING = [
        "Work step-by-step and log assumptions",
        "Validate intermediate outputs",
        "Handle errors explicitly",
    ]
    DEFAULT_AFTER = [
        "Verify against requirements",
        "Summarize outcomes and risks",
        "Suggest next improvements",
    ]

    INTENT_KATAS = {
        "debug": {
            "before": ["Capture exact error and repro steps", "Identify recent changes"],
            "during": ["Isolate root cause", "Test minimal fix"],
            "after": ["Confirm fix with tests", "Document prevention"],
        },
        "plan": {
            "before": ["Define scope and success criteria"],
            "during": ["Draft phased plan", "Estimate risks"],
            "after": ["Confirm milestones", "List open questions"],
        },
        "research": {
            "before": ["Define questions and sources"],
            "during": ["Cross-check sources", "Track citations"],
            "after": ["Summarize evidence", "Call out uncertainty"],
        },
        "build": {
            "before": ["Identify dependencies", "Check environment constraints"],
            "during": ["Implement smallest change", "Run smoke checks"],
            "after": ["Validate behavior", "Note follow-up tasks"],
        },
    }

    def plan(self, scope: dict[str, Any]) -> KataPlan:
        intent = str(scope.get("intent") or "plan")
        kata = self.INTENT_KATAS.get(intent, {})
        phases = [
            KataPhase(name="before", steps=self.DEFAULT_BEFORE + kata.get("before", [])),
            KataPhase(name="during", steps=self.DEFAULT_DURING + kata.get("during", [])),
            KataPhase(name="after", steps=self.DEFAULT_AFTER + kata.get("after", [])),
        ]
        return KataPlan(phases=phases, intent=intent)
