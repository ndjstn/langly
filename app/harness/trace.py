"""Trace generation for harness responses."""
from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel

from app.core.constants import AGENT_MODEL_MAPPING, GRANITE_MODELS
from app.llm.ollama_client import get_ollama_client


logger = logging.getLogger(__name__)


class Trace(BaseModel):
    why: str
    how: str
    suggestions: str
    hindsight: str
    foresight: str


class TraceBuilder:
    def __init__(self) -> None:
        self._model = GRANITE_MODELS.get(
            AGENT_MODEL_MAPPING.get("docs", "dense_2b"),
            "granite3.1-dense:2b",
        )

    async def build(
        self,
        message: str,
        scope: dict[str, Any],
        tool_results: list[dict[str, Any]],
        response: str,
    ) -> Trace:
        prompt = (
            "Return JSON only with keys: why, how, suggestions, hindsight, foresight. "
            "Be concise and user-facing."
        )
        payload = {
            "message": message,
            "scope": scope,
            "tool_results": tool_results,
            "response": response,
        }
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload)},
        ]
        try:
            client = get_ollama_client()
            raw = await client.chat(self._model, messages)
            data = self._parse_json(str(raw))
            if data:
                return Trace(**data)
        except Exception as exc:
            logger.warning("trace generation failed: %s", exc)
        return self._fallback(response)

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

    def _fallback(self, response: str) -> Trace:
        return Trace(
            why="Answered based on available context and tool outputs.",
            how="Classified scope, ran auto tools, and generated a response.",
            suggestions="If needed, refine the scope or provide more context.",
            hindsight="Additional tool coverage could improve accuracy.",
            foresight="Use tool outputs as evidence for future steps.",
        )
