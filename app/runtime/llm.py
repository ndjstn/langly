"""Granite model provider for the v2 runtime."""
from __future__ import annotations

import logging
from typing import Any

from langchain_ollama import ChatOllama

from app.config import Settings, get_settings
from app.core.constants import AGENT_MODEL_MAPPING, GRANITE_MODELS, MODEL_FALLBACKS
from app.runtime.models import AgentRole


logger = logging.getLogger(__name__)


class GraniteLLMProvider:
    """Factory for ChatOllama instances with optional fallbacks."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._cache: dict[str, ChatOllama] = {}

    def _resolve_model_key(self, role: AgentRole) -> str:
        return AGENT_MODEL_MAPPING.get(role.value, "dense_8b")

    def _resolve_model_name(self, model_key: str) -> str:
        return GRANITE_MODELS.get(model_key, model_key)

    def get_model(
        self,
        role: AgentRole,
        *,
        temperature: float | None = None,
        model_override: str | None = None,
        **kwargs: Any,
    ) -> ChatOllama:
        """Get or create a ChatOllama model for a role."""
        model_key = model_override or self._resolve_model_key(role)
        model_name = self._resolve_model_name(model_key)
        cache_key = f"{model_name}:{temperature}:{sorted(kwargs.items())}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        chat = ChatOllama(
            model=model_name,
            base_url=self._settings.ollama_host,
            temperature=temperature if temperature is not None else 0.2,
            **kwargs,
        )
        self._cache[cache_key] = chat
        return chat

    def get_fallback_models(
        self,
        role: AgentRole,
        *,
        model_override: str | None = None,
    ) -> list[ChatOllama]:
        """Return fallback ChatOllama models for a role."""
        model_key = model_override or self._resolve_model_key(role)
        fallbacks = MODEL_FALLBACKS.get(model_key, [])
        models: list[ChatOllama] = []

        for fallback_key in fallbacks:
            model_name = self._resolve_model_name(fallback_key)
            try:
                models.append(
                    ChatOllama(
                        model=model_name,
                        base_url=self._settings.ollama_host,
                        temperature=0.2,
                    )
                )
            except Exception as exc:
                logger.warning(
                    "Failed to create fallback model %s: %s",
                    model_name,
                    exc,
                )
        return models
