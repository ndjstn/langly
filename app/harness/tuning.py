"""Heuristics for iterative harness tuning."""
from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field


class TuningAction(BaseModel):
    kind: str
    detail: dict[str, Any] = Field(default_factory=dict)


class TuningState(BaseModel):
    iterations: int | None = None
    auto_tools: list[str] | None = None
    research: bool | None = None
    prompt_enhance: bool | None = None
    citations: bool | None = None


class TuningSummary(BaseModel):
    actions: list[TuningAction] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    state: TuningState | None = None


class HarnessTuner:
    def suggest(
        self,
        *,
        grade: dict[str, Any] | None,
        tool_results: list[dict[str, Any]],
        scope: dict[str, Any],
    ) -> TuningSummary:
        actions: list[TuningAction] = []
        notes: list[str] = []

        if grade:
            correctness = float(grade.get("correctness", 0))
            completeness = float(grade.get("completeness", 0))
            if correctness < 6:
                actions.append(TuningAction(kind="enable_research", detail={"citations": True}))
            if completeness < 6:
                actions.append(TuningAction(kind="increase_iterations", detail={"delta": 1}))

        for tool in tool_results:
            if tool.get("status") != "error":
                continue
            name = tool.get("name")
            stderr = str(tool.get("stderr") or "")
            if "not found" in stderr.lower() or "command not found" in stderr.lower():
                actions.append(TuningAction(kind="disable_tool", detail={"name": name}))

        if scope.get("mode") == "knowing":
            actions.append(TuningAction(kind="ensure_prompt_enhance", detail={}))

        if not actions:
            notes.append("no_tuning_actions")
        return TuningSummary(actions=actions, notes=notes)

    def apply(self, state: TuningState, summary: TuningSummary) -> TuningState:
        next_state = state.model_copy()
        for action in summary.actions:
            if action.kind == "enable_research":
                next_state.research = True
                if action.detail.get("citations"):
                    next_state.citations = True
            elif action.kind == "increase_iterations":
                delta = int(action.detail.get("delta", 1))
                max_iter = int(os.getenv("LANGLY_ITERATION_MAX", "3"))
                next_state.iterations = min((next_state.iterations or 1) + delta, max_iter)
            elif action.kind == "disable_tool":
                name = action.detail.get("name")
                if name:
                    tools = list(next_state.auto_tools or [])
                    if name in tools:
                        tools.remove(name)
                    next_state.auto_tools = tools
            elif action.kind == "ensure_prompt_enhance":
                next_state.prompt_enhance = True
        return next_state
