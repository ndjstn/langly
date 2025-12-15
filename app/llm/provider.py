"""
LLM Provider Factory for LangChain Integration.

This module provides factory functions for creating LangChain-compatible
LLM instances using Ollama with IBM Granite models.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

from app.config import Settings
from app.core.constants import AGENT_MODEL_MAPPING, GRANITE_MODELS
from app.core.exceptions import LLMError, ModelNotFoundError
from app.llm.models import (
    ModelCapability,
    get_first_fallback,
    get_model_config,
    get_model_options,
)


if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage


logger = logging.getLogger(__name__)


class GraniteChatModel:
    """
    Wrapper for Granite models with fallback support.

    This class provides a high-level interface for using Granite models
    with automatic fallback when the primary model is unavailable.
    """

    def __init__(
        self,
        model_key: str,
        settings: Settings | None = None,
        temperature: float | None = None,
        fallback_enabled: bool = True,
        **kwargs: Any,
    ) -> None:
        """
        Initialize Granite chat model.

        Args:
            model_key: Key from GRANITE_MODELS.
            settings: Application settings.
            temperature: Override temperature.
            fallback_enabled: Enable automatic fallback.
            **kwargs: Additional model options.
        """
        self.settings = settings or Settings()
        self.model_key = model_key
        self.fallback_enabled = fallback_enabled
        self.extra_options = kwargs

        # Resolve model name from key
        self.model_name = GRANITE_MODELS.get(model_key)
        if not self.model_name:
            raise ModelNotFoundError(f"Model key not found: {model_key}")

        # Get model config for defaults
        config = get_model_config(self.model_name)
        self.temperature = (
            temperature
            if temperature is not None
            else (config.default_temperature if config else 0.7)
        )

        # Create primary model
        self._llm = self._create_llm(self.model_name)
        self._fallback_llm: ChatOllama | None = None

    def _create_llm(
        self,
        model_name: str,
        **overrides: Any,
    ) -> ChatOllama:
        """
        Create ChatOllama instance.

        Args:
            model_name: Ollama model name.
            **overrides: Override options.

        Returns:
            Configured ChatOllama instance.
        """
        options = get_model_options(
            model_name,
            temperature=self.temperature,
            **self.extra_options,
        )
        options.update(overrides)

        return ChatOllama(
            model=model_name,
            base_url=self.settings.ollama_host,
            temperature=options.pop("temperature", self.temperature),
            **options,
        )

    @property
    def llm(self) -> ChatOllama:
        """Get the primary LLM instance."""
        return self._llm

    def get_fallback(self) -> ChatOllama | None:
        """
        Get fallback LLM if available.

        Returns:
            Fallback ChatOllama instance or None.
        """
        if not self.fallback_enabled:
            return None

        if self._fallback_llm is None:
            fallback_key = get_first_fallback(self.model_key)
            if fallback_key:
                fallback_name = GRANITE_MODELS.get(fallback_key)
                if fallback_name:
                    self._fallback_llm = self._create_llm(fallback_name)
                    logger.info(
                        "Created fallback LLM: %s", fallback_name
                    )

        return self._fallback_llm

    async def ainvoke(
        self,
        messages: list[BaseMessage],
        **kwargs: Any,
    ) -> Any:
        """
        Async invoke with fallback support.

        Args:
            messages: Input messages.
            **kwargs: Additional options.

        Returns:
            Model response.

        Raises:
            LLMError: If both primary and fallback fail.
        """
        try:
            return await self._llm.ainvoke(messages, **kwargs)
        except Exception as e:
            logger.warning(
                "Primary model failed: %s, trying fallback",
                str(e),
            )
            fallback = self.get_fallback()
            if fallback:
                try:
                    return await fallback.ainvoke(messages, **kwargs)
                except Exception as fb_err:
                    raise LLMError(
                        f"Both primary and fallback failed: {fb_err}"
                    ) from fb_err
            raise LLMError(f"Model invocation failed: {e}") from e

    def invoke(
        self,
        messages: list[BaseMessage],
        **kwargs: Any,
    ) -> Any:
        """
        Sync invoke with fallback support.

        Args:
            messages: Input messages.
            **kwargs: Additional options.

        Returns:
            Model response.

        Raises:
            LLMError: If both primary and fallback fail.
        """
        try:
            return self._llm.invoke(messages, **kwargs)
        except Exception as e:
            logger.warning(
                "Primary model failed: %s, trying fallback",
                str(e),
            )
            fallback = self.get_fallback()
            if fallback:
                try:
                    return fallback.invoke(messages, **kwargs)
                except Exception as fb_err:
                    raise LLMError(
                        f"Both primary and fallback failed: {fb_err}"
                    ) from fb_err
            raise LLMError(f"Model invocation failed: {e}") from e


@lru_cache(maxsize=16)
def get_llm_for_agent(
    agent_type: str,
    temperature: float | None = None,
) -> ChatOllama:
    """
    Get cached LLM instance for an agent type.

    Args:
        agent_type: Type of agent.
        temperature: Override temperature.

    Returns:
        ChatOllama instance configured for the agent.
    """
    model_key = AGENT_MODEL_MAPPING.get(agent_type, "dense_8b")
    model_name = GRANITE_MODELS.get(model_key, GRANITE_MODELS["dense_8b"])

    settings = Settings()
    options = get_model_options(model_name, temperature=temperature)

    logger.debug(
        "Creating LLM for agent=%s, model=%s",
        agent_type,
        model_name,
    )

    return ChatOllama(
        model=model_name,
        base_url=settings.ollama_host,
        temperature=options.get("temperature", 0.7),
    )


def create_chat_model(
    model_key: str | None = None,
    model_name: str | None = None,
    temperature: float | None = None,
    **kwargs: Any,
) -> ChatOllama:
    """
    Create a ChatOllama instance.

    Args:
        model_key: Key from GRANITE_MODELS (preferred).
        model_name: Direct Ollama model name.
        temperature: Override temperature.
        **kwargs: Additional options.

    Returns:
        Configured ChatOllama instance.

    Raises:
        ModelNotFoundError: If model not found.
    """
    settings = Settings()

    if model_key:
        resolved_name = GRANITE_MODELS.get(model_key)
        if not resolved_name:
            raise ModelNotFoundError(f"Model key not found: {model_key}")
        model_name = resolved_name

    if not model_name:
        model_name = GRANITE_MODELS["dense_8b"]

    options = get_model_options(model_name, temperature=temperature)
    options.update(kwargs)

    return ChatOllama(
        model=model_name,
        base_url=settings.ollama_host,
        temperature=options.pop("temperature", 0.7),
        **options,
    )


def create_code_model(
    temperature: float = 0.2,
    **kwargs: Any,
) -> ChatOllama:
    """
    Create a code-specialized model.

    Args:
        temperature: Generation temperature.
        **kwargs: Additional options.

    Returns:
        ChatOllama configured for code tasks.
    """
    return create_chat_model(
        model_key="code_8b",
        temperature=temperature,
        **kwargs,
    )


def create_routing_model(
    temperature: float = 0.3,
    **kwargs: Any,
) -> ChatOllama:
    """
    Create a fast routing model.

    Args:
        temperature: Generation temperature.
        **kwargs: Additional options.

    Returns:
        ChatOllama configured for routing.
    """
    return create_chat_model(
        model_key="moe_1b",
        temperature=temperature,
        **kwargs,
    )


def create_general_model(
    prefer_fast: bool = False,
    temperature: float = 0.7,
    **kwargs: Any,
) -> ChatOllama:
    """
    Create a general-purpose model.

    Args:
        prefer_fast: Use smaller, faster model.
        temperature: Generation temperature.
        **kwargs: Additional options.

    Returns:
        ChatOllama configured for general tasks.
    """
    model_key = "dense_2b" if prefer_fast else "dense_8b"
    return create_chat_model(
        model_key=model_key,
        temperature=temperature,
        **kwargs,
    )


class LLMProvider:
    """
    Central provider for LLM instances.

    Manages LLM lifecycle and provides access to different model types.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """
        Initialize LLM provider.

        Args:
            settings: Application settings.
        """
        self.settings = settings or Settings()
        self._models: dict[str, ChatOllama] = {}

    def get_model(
        self,
        model_key: str,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> ChatOllama:
        """
        Get or create a model instance.

        Args:
            model_key: Key from GRANITE_MODELS.
            temperature: Override temperature.
            **kwargs: Additional options.

        Returns:
            ChatOllama instance.
        """
        cache_key = f"{model_key}:{temperature}"
        if cache_key not in self._models:
            self._models[cache_key] = create_chat_model(
                model_key=model_key,
                temperature=temperature,
                **kwargs,
            )
        return self._models[cache_key]

    def get_for_agent(
        self,
        agent_type: str,
        temperature: float | None = None,
    ) -> ChatOllama:
        """
        Get model for specific agent type.

        Args:
            agent_type: Type of agent.
            temperature: Override temperature.

        Returns:
            ChatOllama configured for agent.
        """
        model_key = AGENT_MODEL_MAPPING.get(agent_type, "dense_8b")
        return self.get_model(model_key, temperature=temperature)

    @property
    def code_model(self) -> ChatOllama:
        """Get code-specialized model."""
        return self.get_model("code_8b", temperature=0.2)

    @property
    def routing_model(self) -> ChatOllama:
        """Get fast routing model."""
        return self.get_model("moe_1b", temperature=0.3)

    @property
    def general_model(self) -> ChatOllama:
        """Get general-purpose model."""
        return self.get_model("dense_8b", temperature=0.7)

    @property
    def fast_model(self) -> ChatOllama:
        """Get fast general model."""
        return self.get_model("dense_2b", temperature=0.7)

    def clear_cache(self) -> None:
        """Clear cached model instances."""
        self._models.clear()
        get_llm_for_agent.cache_clear()


# Module-level provider instance
_provider: LLMProvider | None = None


def get_provider() -> LLMProvider:
    """
    Get the global LLM provider instance.

    Returns:
        LLMProvider singleton.
    """
    global _provider
    if _provider is None:
        _provider = LLMProvider()
    return _provider
