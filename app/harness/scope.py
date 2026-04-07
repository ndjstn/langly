"""Scope classification for harness requests."""
from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, Field

from app.core.constants import AGENT_MODEL_MAPPING, GRANITE_MODELS
from app.llm.ollama_client import get_ollama_client


logger = logging.getLogger(__name__)


class Scope(BaseModel):
    mode: Literal["doing", "knowing"] = "knowing"
    intent: str = "general"
    difficulty: int = Field(default=2, ge=1, le=5)
    tags: list[str] = Field(default_factory=list)
    requires_tools: list[str] = Field(default_factory=list)
    summary: str = ""


class ScopeClassifier:
    def __init__(self) -> None:
        self._model = GRANITE_MODELS.get(
            AGENT_MODEL_MAPPING.get("router", "moe_1b"),
            "granite3.1-moe:1b",
        )

    async def classify(self, message: str) -> Scope:
        prompt = (
            "Return JSON only with keys: mode (doing|knowing), "
            "intent, difficulty (1-5), tags (array), requires_tools (array), summary."
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": message},
        ]
        try:
            client = get_ollama_client()
            raw = await client.chat(self._model, messages)
            data = self._parse_json(str(raw))
            if data:
                return Scope(**data)
        except Exception as exc:
            logger.warning("scope classification failed: %s", exc)
        return self._heuristic_scope(message)

    def _parse_json(self, text: str) -> dict | None:
        cleaned = text.strip()
        if "```" in cleaned:
            cleaned = cleaned.replace("```json", "```")
            try:
                cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()
            except Exception:
                pass
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None

    def _heuristic_scope(self, message: str) -> Scope:
        lowered = message.lower()
        mode = "doing" if any(k in lowered for k in ["build", "fix", "implement", "update", "change", "refactor"]) else "knowing"
        intent = "debug" if any(k in lowered for k in ["error", "bug", "issue", "failing", "traceback"]) else "plan"
        tags = []
        if "test" in lowered:
            tags.append("testing")
        if "doc" in lowered:
            tags.append("docs")
        return Scope(mode=mode, intent=intent, tags=tags, summary=message[:80])
