"""Research helpers for fact checking and citations."""
from __future__ import annotations

import os
import re
import time
import html
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
        self.base_url = (base_url or os.getenv("LANGLY_SEARX_URL") or "http://localhost:8080").rstrip("/")
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
                sources = _parse_json_sources(payload, limit)
                return ResearchResult(
                    query=query,
                    sources=sources,
                    used=True,
                    duration_ms=(time.perf_counter() - start) * 1000,
                )
        except Exception as exc:
            # Fall back to HTML parsing for locked-down Searx instances.
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    html_resp = await client.get(f"{self.base_url}/search", params={"q": query})
                    html_resp.raise_for_status()
                    html_sources = _parse_html_sources(html_resp.text, limit)
                    if html_sources:
                        return ResearchResult(
                            query=query,
                            sources=html_sources,
                            used=True,
                            duration_ms=(time.perf_counter() - start) * 1000,
                        )
            except Exception as html_exc:
                return ResearchResult(
                    query=query,
                    used=False,
                    error=str(html_exc),
                    duration_ms=(time.perf_counter() - start) * 1000,
                )
            return ResearchResult(
                query=query,
                used=False,
                error=str(exc),
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        return ResearchResult(
            query=query,
            sources=[],
            used=False,
            error="searx_no_results",
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


def _parse_json_sources(payload: Any, limit: int) -> list[ResearchSource]:
    sources: list[ResearchSource] = []
    for item in (payload.get("results") or [])[:limit]:
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
    return sources


def _parse_html_sources(html_text: str, limit: int) -> list[ResearchSource]:
    sources: list[ResearchSource] = []
    for block in re.findall(r"<article class=\\\"result[^\\\"]*\\\">(.*?)</article>", html_text, flags=re.DOTALL):
        url_match = re.search(r'href=\\\"(https?://[^\\\"]+)\\\"', block)
        title_match = re.search(r"<h3>.*?<a[^>]*>(.*?)</a>", block, flags=re.DOTALL)
        snippet_match = re.search(r"<p class=\\\"content\\\">(.*?)</p>", block, flags=re.DOTALL)
        if not url_match:
            continue
        url = html.unescape(url_match.group(1))
        title = html.unescape(_strip_tags(title_match.group(1)) if title_match else url)
        snippet = html.unescape(_strip_tags(snippet_match.group(1)) if snippet_match else \"\") or None
        sources.append(ResearchSource(title=title, url=url, snippet=snippet))
        if len(sources) >= limit:
            break
    return sources


def _strip_tags(text: str) -> str:
    return re.sub(r\"<[^>]+>\", \"\", text or \"\").strip()
