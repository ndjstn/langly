"""Response grading for harness runs."""
from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel

from app.core.constants import AGENT_MODEL_MAPPING, GRANITE_MODELS
from app.llm.ollama_client import get_ollama_client


logger = logging.getLogger(__name__)


class GradeResult(BaseModel):
    relevance: float
    completeness: float
    correctness: float
    clarity: float
    tool_use: float
    summary: str
    improvements: list[str]
    model: str | None = None
    fallback: bool = False


class ResponseGrader:
    def __init__(self) -> None:
        model_key = AGENT_MODEL_MAPPING.get("reviewer", "dense_2b")
        self._model = GRANITE_MODELS.get(model_key, "granite3.1-dense:2b")

    async def grade(
        self,
        *,
        message: str,
        scope: dict[str, Any],
        tool_results: list[dict[str, Any]],
        response: str,
    ) -> GradeResult:
        prompt = (
            "You are a strict evaluator. Score each category from 0 to 10. "
            "Return JSON with keys: relevance, completeness, correctness, clarity, tool_use, summary, improvements."
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
                return GradeResult(
                    relevance=float(data.get("relevance", 0)),
                    completeness=float(data.get("completeness", 0)),
                    correctness=float(data.get("correctness", 0)),
                    clarity=float(data.get("clarity", 0)),
                    tool_use=float(data.get("tool_use", 0)),
                    summary=str(data.get("summary", "")),
                    improvements=list(data.get("improvements", []) or []),
                    model=self._model,
                    fallback=False,
                )
        except Exception as exc:
            logger.warning("grading failed: %s", exc)
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

    def _fallback(self, response: str) -> GradeResult:
        score = min(max(len(response) / 400, 2.0), 8.0)
        return GradeResult(
            relevance=score,
            completeness=score,
            correctness=score,
            clarity=score,
            tool_use=0.0,
            summary="Fallback grading based on response length.",
            improvements=["Enable grading model for richer feedback."],
            model=None,
            fallback=True,
        )
