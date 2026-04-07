"""A/B testing for harness responses."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.core.constants import AGENT_MODEL_MAPPING, GRANITE_MODELS
from app.llm.ollama_client import get_ollama_client


logger = logging.getLogger(__name__)


class ABTestResult(BaseModel):
    variant_a: str
    variant_b: str
    winner: str
    rationale: str
    scores: dict[str, float] | None = None
    used_model: str | None = None
    fallback: bool = False


@dataclass(frozen=True)
class ABTestConfig:
    judge_model: str


class ABTester:
    def __init__(self) -> None:
        model_key = AGENT_MODEL_MAPPING.get("router", "moe_1b")
        self._judge_model = GRANITE_MODELS.get(model_key, "granite3.1-moe:1b")

    async def run(
        self,
        *,
        message: str,
        scope: dict[str, Any],
        tool_results: list[dict[str, Any]],
        response: str,
    ) -> ABTestResult:
        variant_b = await self._generate_variant(response)
        if not variant_b:
            return self._fallback(response, response, "no_variant")

        judged = await self._judge(message, scope, tool_results, response, variant_b)
        if judged:
            return judged
        return self._fallback(response, variant_b, "heuristic")

    async def _generate_variant(self, response: str) -> str | None:
        prompt = (
            "Rewrite the response with a different emphasis: more structured, concise, and actionable."
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": response},
        ]
        try:
            client = get_ollama_client()
            raw = await client.chat(self._judge_model, messages)
            return str(raw).strip()
        except Exception as exc:
            logger.warning("ab test variant failed: %s", exc)
            return None

    async def _judge(
        self,
        message: str,
        scope: dict[str, Any],
        tool_results: list[dict[str, Any]],
        variant_a: str,
        variant_b: str,
    ) -> ABTestResult | None:
        prompt = (
            "You are an evaluator. Pick which response better satisfies the user. "
            "Return JSON with keys: winner (a|b|tie), rationale, scores (a,b)."
        )
        payload = {
            "message": message,
            "scope": scope,
            "tool_results": tool_results,
            "variant_a": variant_a,
            "variant_b": variant_b,
        }
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload)},
        ]
        try:
            client = get_ollama_client()
            raw = await client.chat(self._judge_model, messages)
            data = self._parse_json(str(raw))
            if not data:
                return None
            winner = data.get("winner", "tie")
            rationale = data.get("rationale", "")
            scores = data.get("scores") if isinstance(data.get("scores"), dict) else None
            return ABTestResult(
                variant_a=variant_a,
                variant_b=variant_b,
                winner=winner,
                rationale=rationale,
                scores=scores,
                used_model=self._judge_model,
                fallback=False,
            )
        except Exception as exc:
            logger.warning("ab test judge failed: %s", exc)
            return None

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

    def _fallback(self, variant_a: str, variant_b: str, rationale: str) -> ABTestResult:
        score_a = float(len(variant_a))
        score_b = float(len(variant_b))
        if score_a > score_b:
            winner = "a"
        elif score_b > score_a:
            winner = "b"
        else:
            winner = "tie"
        return ABTestResult(
            variant_a=variant_a,
            variant_b=variant_b,
            winner=winner,
            rationale=f"fallback: {rationale}",
            scores={"a": score_a, "b": score_b},
            used_model=None,
            fallback=True,
        )
