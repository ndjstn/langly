"""Tool reconfiguration based on recovery output."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ToolReconfiguration:
    disabled_tools: list[str]
    retry_overrides: dict[str, int]
    notes: list[str]

    @property
    def changed(self) -> bool:
        return bool(self.disabled_tools or self.retry_overrides)


class ToolReconfigurator:
    def plan(
        self,
        tool_results: list[dict[str, Any]],
        recovery: dict[str, Any] | None = None,
    ) -> ToolReconfiguration:
        disabled: set[str] = set()
        retry_overrides: dict[str, int] = {}
        notes: list[str] = []

        for tool in tool_results:
            if tool.get("status") != "error":
                continue
            name = self._normalize_tool(tool.get("name", ""))
            stderr = str(tool.get("stderr") or "")

            if "no jj repo" in stderr.lower():
                disabled.add("jj")
                notes.append("jj disabled: no jj repo detected")
            if "not found" in stderr.lower() or "command not found" in stderr.lower():
                disabled.add(name)
                notes.append(f"{name} disabled: command not found")
            if "greptile rpc failed" in stderr.lower():
                retry_overrides["greptile"] = 3
                notes.append("greptile retries increased")
            if "stub-ld" in stderr.lower() or "dynamically linked executable" in stderr.lower():
                disabled.add("lint")
                notes.append("lint disabled: uv on nix stub-ld failure")

        if recovery:
            summary = str(recovery.get("summary") or "")
            recovery_text = " ".join(
                [
                    summary,
                    " ".join(recovery.get("retry_plan", []) or []),
                    " ".join(recovery.get("next_steps", []) or []),
                ]
            ).lower()
            for tool in ("lint", "greptile", "jj", "taskwarrior", "browser"):
                if f"disable {tool}" in recovery_text:
                    disabled.add(tool)
            if "retry greptile" in recovery_text:
                retry_overrides["greptile"] = max(retry_overrides.get("greptile", 0), 3)

        return ToolReconfiguration(
            disabled_tools=sorted(disabled),
            retry_overrides=retry_overrides,
            notes=notes,
        )

    def _normalize_tool(self, name: str) -> str:
        if name.startswith("jj "):
            return "jj"
        if name.startswith("uv run ruff"):
            return "lint"
        return name
