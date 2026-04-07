"""Task capture and template suggestions for Taskwarrior workflows."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


BULLET_RE = re.compile(r"^(?:\s*[-*]\s+|\s*\d+[.)]\s+)(.+)$")


class TaskCandidate(BaseModel):
    description: str
    source: str = "response"
    tags: list[str] = Field(default_factory=list)


class TaskCaptureResult(BaseModel):
    candidates: list[TaskCandidate] = Field(default_factory=list)
    created: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    error: str | None = None


@dataclass
class TaskTemplate:
    name: str
    checklist: list[str]


class TaskTemplateResult(BaseModel):
    templates: list[TaskTemplate] = Field(default_factory=list)
    reason: str = ""


class TaskCapture:
    def extract(self, response: str, *, max_tasks: int = 8) -> list[TaskCandidate]:
        candidates: list[TaskCandidate] = []
        for line in response.splitlines():
            match = BULLET_RE.match(line)
            if not match:
                continue
            desc = match.group(1).strip()
            if not desc:
                continue
            candidates.append(TaskCandidate(description=desc))
            if len(candidates) >= max_tasks:
                break
        return candidates

    def commit(self, candidates: list[TaskCandidate]) -> TaskCaptureResult:
        if not shutil.which("task"):
            return TaskCaptureResult(
                candidates=candidates,
                skipped=[c.description for c in candidates],
                error="taskwarrior_not_installed",
            )
        created: list[str] = []
        skipped: list[str] = []
        for candidate in candidates:
            try:
                cmd = ["task", "add", candidate.description]
                if candidate.tags:
                    cmd.extend([f"+{tag}" for tag in candidate.tags])
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if proc.returncode == 0:
                    created.append(candidate.description)
                else:
                    skipped.append(candidate.description)
            except Exception:
                skipped.append(candidate.description)
        return TaskCaptureResult(
            candidates=candidates,
            created=created,
            skipped=skipped,
        )


class TaskTemplateEngine:
    def __init__(self) -> None:
        self._templates = {
            "read_file": TaskTemplate(
                name="read_file",
                checklist=[
                    "Confirm file exists and readable",
                    "Identify file type/encoding",
                    "Read minimal section first",
                    "Summarize key findings",
                ],
            ),
            "edit_file": TaskTemplate(
                name="edit_file",
                checklist=[
                    "Locate target file and backup if needed",
                    "Make minimal diff",
                    "Run formatter or linter if available",
                    "Summarize change",
                ],
            ),
            "debug": TaskTemplate(
                name="debug",
                checklist=[
                    "Capture exact error/stacktrace",
                    "Identify minimal repro",
                    "Inspect recent changes",
                    "Propose fix + verify",
                ],
            ),
            "test": TaskTemplate(
                name="test",
                checklist=[
                    "Run targeted unit tests",
                    "Capture failures",
                    "Fix root cause",
                    "Re-run tests",
                ],
            ),
            "deploy": TaskTemplate(
                name="deploy",
                checklist=[
                    "Confirm config/env",
                    "Run build",
                    "Deploy to staging",
                    "Smoke test",
                ],
            ),
        }

    def suggest(self, message: str, scope: dict[str, Any]) -> TaskTemplateResult:
        lowered = message.lower()
        selected: list[TaskTemplate] = []
        reason = "heuristic"
        if any(token in lowered for token in ["read", "open", "inspect", "view"]) and "/" in message:
            selected.append(self._templates["read_file"])
        if any(token in lowered for token in ["edit", "update", "change", "refactor"]):
            selected.append(self._templates["edit_file"])
        if scope.get("intent") == "debug" or any(token in lowered for token in ["error", "bug", "traceback"]):
            selected.append(self._templates["debug"])
        if "test" in lowered:
            selected.append(self._templates["test"])
        if "deploy" in lowered:
            selected.append(self._templates["deploy"])
        if not selected:
            reason = "none"
        return TaskTemplateResult(templates=selected, reason=reason)
