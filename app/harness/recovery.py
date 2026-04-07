"""Recovery planning for tool failures."""
from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel

from app.core.constants import AGENT_MODEL_MAPPING, GRANITE_MODELS
from app.llm.ollama_client import get_ollama_client


logger = logging.getLogger(__name__)


class RecoveryAdvice(BaseModel):
    summary: str
    hypotheses: list[str]
    retry_plan: list[str]
    next_steps: list[str]


class RecoveryPlanner:
    def __init__(self) -> None:
        self._model = GRANITE_MODELS.get(
            AGENT_MODEL_MAPPING.get("router", "moe_1b"),
            "granite3.1-moe:1b",
        )

    async def build(
        self,
        message: str,
        scope: dict[str, Any],
        tool_results: list[dict[str, Any]],
    ) -> RecoveryAdvice:
        prompt = (
            "You are the JJ thinking workflow. Given tool errors, propose an iterative "
            "recovery plan that can be retried. Return JSON only with keys: "
            "summary, hypotheses, retry_plan, next_steps."
        )
        payload = {
            "message": message,
            "scope": scope,
            "tool_results": tool_results,
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
                return RecoveryAdvice(**data)
        except Exception as exc:
            logger.warning("recovery plan failed: %s", exc)
        return self._fallback(tool_results)

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

    def _fallback(self, tool_results: list[dict[str, Any]]) -> RecoveryAdvice:
        errors = [
            f"{tool.get('name')}: {tool.get('stderr') or tool.get('output')}"
            for tool in tool_results
            if tool.get("status") == "error"
        ]
        if not errors:
            errors = ["No tool errors detected."]
        return RecoveryAdvice(
            summary="Tool errors detected; retry with adjusted config.",
            hypotheses=errors[:5],
            retry_plan=["Retry failed tools after verifying dependencies."],
            next_steps=[
                "Check Ollama models and server health.",
                "Verify greptile/taskwarrior availability.",
                "Re-run the request with fewer auto tools if needed.",
            ],
        )
