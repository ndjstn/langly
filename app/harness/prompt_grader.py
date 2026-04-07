"""Prompt grading for harness inputs."""
from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel

from app.core.constants import AGENT_MODEL_MAPPING, GRANITE_MODELS
from app.llm.ollama_client import get_ollama_client


logger = logging.getLogger(__name__)


class PromptGrade(BaseModel):
    clarity: float
    specificity: float
    completeness: float
    feasibility: float
    summary: str
    missing_info: list[str]
    model: str | None = None
    fallback: bool = False


class PromptGrader:
    def __init__(self) -> None:
        model_key = AGENT_MODEL_MAPPING.get("reviewer", "dense_2b")
        self._model = GRANITE_MODELS.get(model_key, "granite3.1-dense:2b")

    async def grade(self, message: str) -> PromptGrade:
        prompt = (
            "Score the prompt 0-10 for clarity, specificity, completeness, feasibility. "
            "Return JSON with keys: clarity, specificity, completeness, feasibility, summary, missing_info."
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
                return PromptGrade(
                    clarity=float(data.get("clarity", 0)),
                    specificity=float(data.get("specificity", 0)),
                    completeness=float(data.get("completeness", 0)),
                    feasibility=float(data.get("feasibility", 0)),
                    summary=str(data.get("summary", "")),
                    missing_info=list(data.get("missing_info", []) or []),
                    model=self._model,
                    fallback=False,
                )
        except Exception as exc:
            logger.warning("prompt grade failed: %s", exc)
        return self._fallback(message)

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

    def _fallback(self, message: str) -> PromptGrade:
        base = min(max(len(message) / 80, 2.0), 8.0)
        return PromptGrade(
            clarity=base,
            specificity=base,
            completeness=base,
            feasibility=base,
            summary="Fallback prompt grading based on length.",
            missing_info=["Add concrete constraints or desired outputs."],
            model=None,
            fallback=True,
        )
