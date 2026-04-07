"""Small-model provider for V3."""
from __future__ import annotations

import logging
from typing import Any

from langchain_ollama import ChatOllama

from app.config import Settings, get_settings
from app.v3.registry import SmallModelRegistry


logger = logging.getLogger(__name__)


class TinyLLMProvider:
    """Resolve role -> ChatOllama with small-model fallback."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._registry = SmallModelRegistry()
        self._cache: dict[str, ChatOllama] = {}

    def _cache_key(self, model: str, temperature: float) -> str:
        return f"{model}:{temperature}"

    def get_models(self, role: str) -> list[ChatOllama]:
        specs = self._registry.resolve(role)
        models: list[ChatOllama] = []
        for spec in specs:
            key = self._cache_key(spec.name, 0.2)
            if key not in self._cache:
                try:
                    self._cache[key] = ChatOllama(
                        model=spec.name,
                        base_url=self._settings.ollama_host,
                        temperature=0.2,
                    )
                except Exception as exc:
                    logger.warning("Failed to init model %s: %s", spec.name, exc)
                    continue
            models.append(self._cache[key])
        return models

    async def invoke(self, role: str, messages: list[Any]) -> str:
        last_error: Exception | None = None
        for model in self.get_models(role):
            try:
                response = await model.ainvoke(messages)
                return str(getattr(response, "content", response))
            except Exception as exc:
                last_error = exc
                logger.warning("Model %s failed: %s", role, exc)
        raise RuntimeError(f"All models failed for role {role}: {last_error}")
