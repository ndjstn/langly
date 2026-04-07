"""Policy for selecting auto tools per request."""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from .research import extract_urls


class ToolSelectionDecision(BaseModel):
    selected_tools: list[str] = Field(default_factory=list)
    excluded_tools: list[str] = Field(default_factory=list)
    reason: str = ""


class ToolSelectionPolicy:
    CODE_KEYWORDS = (
        "repo",
        "code",
        "file",
        "python",
        "refactor",
        "lint",
        "test",
        "bug",
        "error",
        "stacktrace",
        "traceback",
        "git",
        "diff",
    )

    def select(
        self,
        message: str,
        scope: dict[str, Any],
        *,
        available: list[str],
        defaults: list[str],
    ) -> ToolSelectionDecision:
        selected = set(defaults)
        excluded: set[str] = set()

        required = set(scope.get("requires_tools") or [])
        selected.update(required)

        lowered = message.lower()
        is_code = any(keyword in lowered for keyword in self.CODE_KEYWORDS)

        if not is_code and scope.get("mode") == "knowing":
            for tool in ("lint", "jj"):
                if tool in selected:
                    selected.remove(tool)
                    excluded.add(tool)

        if extract_urls(message):
            selected.add("browser")

        if any(token in lowered for token in ["task", "todo", "kanban", "backlog"]):
            if "taskwarrior_mcp" in available:
                selected.add("taskwarrior_mcp")
            else:
                selected.add("taskwarrior")

        if _has_path(message):
            selected.add("preflight")

        for tool in list(selected):
            if tool not in available:
                selected.remove(tool)
                excluded.add(tool)

        reason = "heuristic"
        if required:
            reason = "scope_requires_tools"
        return ToolSelectionDecision(
            selected_tools=sorted(selected),
            excluded_tools=sorted(excluded),
            reason=reason,
        )


def _has_path(message: str) -> bool:
    return bool(re.search(r"(?:\\.?/[^\\s'\\\"]+)", message or ""))
