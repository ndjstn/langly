"""Research helpers for fact checking and citations."""
from __future__ import annotations

import os
import re
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field


URL_RE = re.compile(r"(https?://[^\s)]+)", re.IGNORECASE)


class ResearchSource(BaseModel):
    title: str
    url: str
    snippet: str | None = None
    score: float | None = None


class ResearchResult(BaseModel):
    query: str
    sources: list[ResearchSource] = Field(default_factory=list)
    used: bool = False
    error: str | None = None
    duration_ms: float | None = None


class ResearchPlan(BaseModel):
    enabled: bool
    query: str
    reason: str


class SearxClient:
    def __init__(self, base_url: str | None = None, *, timeout: float | None = None) -> None:
        self.base_url = (base_url or os.getenv("LANGLY_SEARX_URL", "")).rstrip("/")
        self.timeout = timeout or float(os.getenv("LANGLY_SEARX_TIMEOUT_SEC", "6"))

    async def search(self, query: str, *, limit: int = 5) -> ResearchResult:
        start = time.perf_counter()
        if not self.base_url:
            return ResearchResult(query=query, used=False, error="searx_url_not_configured")
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{self.base_url}/search",
                    params={"q": query, "format": "json"},
                )
                resp.raise_for_status()
                payload = resp.json()
        except Exception as exc:
            return ResearchResult(
                query=query,
                used=False,
                error=str(exc),
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        sources: list[ResearchSource] = []
        for item in payload.get("results", [])[:limit]:
            if not isinstance(item, dict):
                continue
            sources.append(
                ResearchSource(
                    title=str(item.get("title") or ""),
                    url=str(item.get("url") or ""),
                    snippet=str(item.get("content") or item.get("snippet") or "") or None,
                    score=float(item.get("score")) if item.get("score") is not None else None,
                )
            )
        return ResearchResult(
            query=query,
            sources=sources,
            used=True,
            duration_ms=(time.perf_counter() - start) * 1000,
        )


class ResearchPolicy:
    DEFAULT_KEYWORDS = (
        "latest",
        "today",
        "current",
        "now",
        "news",
        "price",
        "pricing",
        "compare",
        "best",
        "release",
        "date",
        "version",
        "release",
    )

    def plan(
        self,
        message: str,
        scope: dict[str, Any],
        *,
        requested: bool | None = None,
        query_override: str | None = None,
    ) -> ResearchPlan:
        if requested is False:
            return ResearchPlan(enabled=False, query="", reason="explicitly_disabled")
        query = query_override or message
        if requested is True:
            return ResearchPlan(enabled=True, query=query, reason="explicitly_enabled")
        lowered = message.lower()
        needs_research = any(keyword in lowered for keyword in self.DEFAULT_KEYWORDS)
        return ResearchPlan(
            enabled=needs_research,
            query=query,
            reason="heuristic" if needs_research else "not_needed",
        )


def extract_urls(text: str) -> list[str]:
    return [match.strip(".,)") for match in URL_RE.findall(text or "")]


def render_sources(sources: list[ResearchSource]) -> str:
    lines = []
    for idx, source in enumerate(sources, start=1):
        title = source.title or "source"
        url = source.url
        lines.append(f"[{idx}] {title} - {url}")
    return "\n".join(lines)
