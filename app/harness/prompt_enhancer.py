"""Prompt enhancement pipeline for harness calls."""
from __future__ import annotations

import os
import re
from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from .research import ResearchResult, ResearchSource, render_sources


class PromptEnhancement(BaseModel):
    enhanced_message: str
    applied: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    citations_required: bool = False
    current_date: str = ""
    cutoff_date: str = ""
    sources: list[ResearchSource] = Field(default_factory=list)


class PromptEnhancer:
    def __init__(self) -> None:
        self.default_cutoff = os.getenv("LANGLY_MODEL_CUTOFF_DATE", "2024-06-01")

    def enhance(
        self,
        *,
        message: str,
        scope: dict[str, Any],
        context: str,
        tool_results: list[dict[str, Any]],
        research: ResearchResult | None = None,
        citations_required: bool = False,
        current_date: str | None = None,
        cutoff_date: str | None = None,
    ) -> PromptEnhancement:
        applied: list[str] = []
        notes: list[str] = []
        today = current_date or date.today().isoformat()
        cutoff = cutoff_date or self.default_cutoff

        header_lines = [
            "You are the Langly harness. Follow the instructions carefully.",
            f"Today's date: {today}.",
            f"Model knowledge cutoff: {cutoff}.",
        ]
        applied.append("date_context")

        if citations_required:
            header_lines.append(
                "If you state factual claims, cite sources inline as [n] and include a Sources section."
            )
            applied.append("citations_required")

        if research and research.sources:
            header_lines.append("Sources (use for citations):")
            header_lines.append(render_sources(research.sources))
            applied.append("research_sources")
        elif research and research.error:
            notes.append(f"research_error: {research.error}")

        tool_summary = _summarize_tools(tool_results)
        if tool_summary:
            header_lines.append("Tool summary:")
            header_lines.append(tool_summary)
            applied.append("tool_summary")

        if _has_image(message):
            header_lines.append(
                "Image present: use vision tool output for image analysis. Greptile is for code search, not images."
            )
            applied.append("vision_guidance")

        header = "\n".join(header_lines)
        enhanced_message = (
            f"{header}\n\n"
            "User message:\n"
            f"{message}\n\n"
            "[HarnessContext]\n"
            f"{context}"
        )
        return PromptEnhancement(
            enhanced_message=enhanced_message,
            applied=applied,
            notes=notes,
            citations_required=citations_required,
            current_date=today,
            cutoff_date=cutoff,
            sources=list(research.sources) if research else [],
        )


def _summarize_tools(tool_results: list[dict[str, Any]]) -> str:
    if not tool_results:
        return ""
    lines: list[str] = []
    for tool in tool_results:
        name = tool.get("name")
        status = tool.get("status")
        stderr = str(tool.get("stderr") or "")
        if status == "error" and stderr:
            lines.append(f"- {name}: {status} ({stderr[:140]})")
        else:
            lines.append(f"- {name}: {status}")
    return "\n".join(lines)


def _has_image(message: str) -> bool:
    if not message:
        return False
    lowered = message.lower()
    if "attachment" in lowered or "screenshot" in lowered or "image" in lowered or "photo" in lowered:
        return True
    return bool(re.search(r"\\.(png|jpe?g|webp|bmp|gif)\\b", lowered))
