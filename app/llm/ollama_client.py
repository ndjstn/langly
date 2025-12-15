"""
Ollama Client Module.

This module provides an async client wrapper for Ollama API interactions,
including model management, health checks, and LLM invocation utilities.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.core.constants import (
    DEFAULT_RETRY_ATTEMPTS,
    DEFAULT_RETRY_MAX_WAIT,
    DEFAULT_RETRY_MIN_WAIT,
    DEFAULT_TIMEOUT_SECONDS,
)
from app.core.exceptions import LLMError, ModelNotFoundError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


logger = logging.getLogger(__name__)


class OllamaClient:
    """
    Async client for Ollama API interactions.

    Provides methods for model management, health checks,
    and direct API calls with retry logic and error handling.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """
        Initialize the Ollama client.

        Args:
            base_url: Ollama API base URL. If None, uses settings.
            timeout: Request timeout in seconds.
        """
        settings = get_settings()
        self._base_url = base_url or settings.ollama_host
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> OllamaClient:
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get the HTTP client, creating if needed."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @retry(
        stop=stop_after_attempt(DEFAULT_RETRY_ATTEMPTS),
        wait=wait_exponential(
            min=DEFAULT_RETRY_MIN_WAIT,
            max=DEFAULT_RETRY_MAX_WAIT,
        ),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    async def health_check(self) -> bool:
        """
        Check if Ollama server is healthy and responsive.

        Returns:
            True if server is healthy.

        Raises:
            LLMError: If health check fails.
        """
        try:
            response = await self.client.get("/api/tags")
            response.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logger.error(f"Ollama health check failed: {e}")
            raise LLMError(f"Ollama health check failed: {e}") from e

    async def list_models(self) -> list[dict[str, Any]]:
        """
        List all available models in Ollama.

        Returns:
            List of model information dictionaries.

        Raises:
            LLMError: If listing fails.
        """
        try:
            response = await self.client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            return list(data.get("models", []))
        except httpx.HTTPError as e:
            logger.error(f"Failed to list models: {e}")
            raise LLMError(f"Failed to list models: {e}") from e

    async def model_exists(self, model_name: str) -> bool:
        """
        Check if a specific model exists in Ollama.

        Args:
            model_name: Name of the model to check.

        Returns:
            True if model exists.
        """
        try:
            models = await self.list_models()
            return any(m.get("name") == model_name for m in models)
        except LLMError:
            return False

    async def pull_model(
        self,
        model_name: str,
        stream: bool = False,
    ) -> AsyncGenerator[dict[str, Any], None] | dict[str, Any]:
        """
        Pull a model from the Ollama registry.

        Args:
            model_name: Name of the model to pull.
            stream: Whether to stream progress updates.

        Yields:
            Progress updates if streaming.

        Returns:
            Final result if not streaming.

        Raises:
            LLMError: If pull fails.
        """
        try:
            if stream:
                return self._pull_model_stream(model_name)
            else:
                response = await self.client.post(
                    "/api/pull",
                    json={"name": model_name, "stream": False},
                    timeout=600.0,  # Models can take time to download
                )
                response.raise_for_status()
                return dict(response.json())
        except httpx.HTTPError as e:
            logger.error(f"Failed to pull model {model_name}: {e}")
            raise LLMError(f"Failed to pull model: {e}") from e

    async def _pull_model_stream(
        self,
        model_name: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream model pull progress."""
        async with self.client.stream(
            "POST",
            "/api/pull",
            json={"name": model_name, "stream": True},
            timeout=600.0,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    import json
                    yield dict(json.loads(line))

    async def get_model_info(
        self,
        model_name: str,
    ) -> dict[str, Any]:
        """
        Get detailed information about a model.

        Args:
            model_name: Name of the model.

        Returns:
            Model information dictionary.

        Raises:
            ModelNotFoundError: If model doesn't exist.
            LLMError: If request fails.
        """
        try:
            response = await self.client.post(
                "/api/show",
                json={"name": model_name},
            )
            if response.status_code == 404:
                raise ModelNotFoundError(model_name)
            response.raise_for_status()
            return dict(response.json())
        except httpx.HTTPError as e:
            logger.error(f"Failed to get model info for {model_name}: {e}")
            raise LLMError(f"Failed to get model info: {e}") from e

    @retry(
        stop=stop_after_attempt(DEFAULT_RETRY_ATTEMPTS),
        wait=wait_exponential(
            min=DEFAULT_RETRY_MIN_WAIT,
            max=DEFAULT_RETRY_MAX_WAIT,
        ),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    async def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        options: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> AsyncGenerator[str, None] | str:
        """
        Generate text using a model.

        Args:
            model: Model name to use.
            prompt: The prompt to send.
            system: Optional system prompt.
            options: Model options (temperature, etc.).
            stream: Whether to stream the response.

        Yields:
            Text chunks if streaming.

        Returns:
            Complete response if not streaming.

        Raises:
            ModelNotFoundError: If model doesn't exist.
            LLMError: If generation fails.
        """
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
        }

        if system:
            payload["system"] = system
        if options:
            payload["options"] = options

        try:
            if stream:
                return self._generate_stream(payload)
            else:
                response = await self.client.post(
                    "/api/generate",
                    json=payload,
                )
                if response.status_code == 404:
                    raise ModelNotFoundError(model)
                response.raise_for_status()
                data = response.json()
                return str(data.get("response", ""))
        except httpx.HTTPError as e:
            logger.error(f"Generation failed: {e}")
            raise LLMError(f"Generation failed: {e}") from e

    async def _generate_stream(
        self,
        payload: dict[str, Any],
    ) -> AsyncGenerator[str, None]:
        """Stream generation response."""
        import json

        async with self.client.stream(
            "POST",
            "/api/generate",
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    data = json.loads(line)
                    if "response" in data:
                        yield str(data["response"])

    @retry(
        stop=stop_after_attempt(DEFAULT_RETRY_ATTEMPTS),
        wait=wait_exponential(
            min=DEFAULT_RETRY_MIN_WAIT,
            max=DEFAULT_RETRY_MAX_WAIT,
        ),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        options: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> AsyncGenerator[str, None] | str:
        """
        Chat with a model using conversation history.

        Args:
            model: Model name to use.
            messages: List of message dicts with 'role' and 'content'.
            options: Model options (temperature, etc.).
            stream: Whether to stream the response.

        Yields:
            Text chunks if streaming.

        Returns:
            Complete response if not streaming.

        Raises:
            ModelNotFoundError: If model doesn't exist.
            LLMError: If chat fails.
        """
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }

        if options:
            payload["options"] = options

        try:
            if stream:
                return self._chat_stream(payload)
            else:
                response = await self.client.post(
                    "/api/chat",
                    json=payload,
                )
                if response.status_code == 404:
                    raise ModelNotFoundError(model)
                response.raise_for_status()
                data = response.json()
                message = data.get("message", {})
                return str(message.get("content", ""))
        except httpx.HTTPError as e:
            logger.error(f"Chat failed: {e}")
            raise LLMError(f"Chat failed: {e}") from e

    async def _chat_stream(
        self,
        payload: dict[str, Any],
    ) -> AsyncGenerator[str, None]:
        """Stream chat response."""
        import json

        async with self.client.stream(
            "POST",
            "/api/chat",
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    data = json.loads(line)
                    message = data.get("message", {})
                    if content := message.get("content"):
                        yield str(content)

    async def embeddings(
        self,
        model: str,
        prompt: str,
    ) -> list[float]:
        """
        Generate embeddings for text.

        Args:
            model: Embedding model name.
            prompt: Text to embed.

        Returns:
            List of embedding floats.

        Raises:
            ModelNotFoundError: If model doesn't exist.
            LLMError: If embedding fails.
        """
        try:
            response = await self.client.post(
                "/api/embeddings",
                json={"model": model, "prompt": prompt},
            )
            if response.status_code == 404:
                raise ModelNotFoundError(model)
            response.raise_for_status()
            data = response.json()
            return list(data.get("embedding", []))
        except httpx.HTTPError as e:
            logger.error(f"Embedding failed: {e}")
            raise LLMError(f"Embedding failed: {e}") from e


# Module-level singleton instance
_ollama_client: OllamaClient | None = None


def get_ollama_client() -> OllamaClient:
    """
    Get or create the singleton Ollama client.

    Returns:
        The shared Ollama client instance.
    """
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient()
    return _ollama_client


async def ensure_model_available(model_name: str) -> bool:
    """
    Ensure a model is available, pulling if necessary.

    Args:
        model_name: Name of the model to ensure.

    Returns:
        True if model is available.

    Raises:
        LLMError: If model cannot be made available.
    """
    client = get_ollama_client()

    if await client.model_exists(model_name):
        logger.info(f"Model {model_name} is already available")
        return True

    logger.info(f"Pulling model {model_name}...")
    try:
        await client.pull_model(model_name, stream=False)
        logger.info(f"Successfully pulled model {model_name}")
        return True
    except LLMError:
        logger.error(f"Failed to pull model {model_name}")
        raise


async def check_ollama_health() -> dict[str, Any]:
    """
    Check Ollama server health and return status info.

    Returns:
        Dictionary with health status information.
    """
    client = get_ollama_client()

    try:
        is_healthy = await client.health_check()
        models = await client.list_models()
        return {
            "healthy": is_healthy,
            "model_count": len(models),
            "models": [m.get("name") for m in models],
            "base_url": client._base_url,
        }
    except LLMError as e:
        return {
            "healthy": False,
            "error": str(e),
            "base_url": client._base_url,
        }
