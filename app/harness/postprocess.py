"""Post-processing for harness responses."""
from __future__ import annotations

import re
from typing import List

from pydantic import BaseModel, Field

from .research import ResearchResult, render_sources


CITATION_RE = re.compile(r"\[\d+\]")


class PostprocessResult(BaseModel):
    response: str
    citations_added: bool = False
    warnings: list[str] = Field(default_factory=list)


class ResponsePostProcessor:
    def apply(
        self,
        response: str,
        research: ResearchResult | None,
        *,
        enforce_citations: bool = False,
    ) -> PostprocessResult:
        warnings: List[str] = []
        updated = response
        added = False

        if enforce_citations and research and research.sources:
            if not CITATION_RE.search(response):
                sources_block = render_sources(research.sources)
                updated = (
                    f"{response.strip()}\n\nSources:\n{sources_block}"
                )
                added = True
                warnings.append("citations_missing_added_sources")
        return PostprocessResult(response=updated, citations_added=added, warnings=warnings)
