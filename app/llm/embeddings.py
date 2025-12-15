"""
Granite Embedding Client for Semantic Memory.

This module provides embedding generation using IBM Granite Embedding model
for semantic search, similarity matching, and memory retrieval.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config import Settings
from app.core.constants import EMBEDDING_DIMENSIONS, GRANITE_MODELS
from app.core.exceptions import EmbeddingError, LLMConnectionError


logger = logging.getLogger(__name__)


class GraniteEmbeddingClient:
    """
    Client for generating embeddings using Granite Embedding model.

    Provides both synchronous and asynchronous methods for embedding
    text for semantic search and similarity operations.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        timeout: float = 30.0,
    ) -> None:
        """
        Initialize embedding client.

        Args:
            settings: Application settings.
            timeout: Request timeout in seconds.
        """
        self.settings = settings or Settings()
        self.timeout = timeout
        self.model_name = GRANITE_MODELS.get(
            "embedding",
            "granite-embedding:278m",
        )
        self._async_client: httpx.AsyncClient | None = None
        self._sync_client: httpx.Client | None = None

    @property
    def base_url(self) -> str:
        """Get Ollama base URL."""
        return self.settings.ollama_host.rstrip("/")

    @property
    def dimensions(self) -> int:
        """Get embedding dimensions."""
        return EMBEDDING_DIMENSIONS

    async def _get_async_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._async_client

    def _get_sync_client(self) -> httpx.Client:
        """Get or create sync HTTP client."""
        if self._sync_client is None or self._sync_client.is_closed:
            self._sync_client = httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._sync_client

    async def close(self) -> None:
        """Close all HTTP clients."""
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None
        if self._sync_client is not None:
            self._sync_client.close()
            self._sync_client = None

    async def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector as list of floats.

        Raises:
            EmbeddingError: If embedding generation fails.
        """
        if not text or not text.strip():
            raise EmbeddingError("Cannot embed empty text")

        try:
            client = await self._get_async_client()
            response = await client.post(
                "/api/embeddings",
                json={
                    "model": self.model_name,
                    "prompt": text,
                },
            )
            response.raise_for_status()
            data = response.json()
            embedding = data.get("embedding", [])

            if not embedding:
                raise EmbeddingError("Empty embedding returned")

            return embedding

        except httpx.ConnectError as e:
            raise LLMConnectionError(
                f"Failed to connect to Ollama: {e}"
            ) from e
        except httpx.HTTPStatusError as e:
            raise EmbeddingError(
                f"Embedding request failed: {e.response.text}"
            ) from e
        except Exception as e:
            raise EmbeddingError(f"Embedding error: {e}") from e

    async def embed_texts(
        self,
        texts: list[str],
        batch_size: int = 10,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.
            batch_size: Number of concurrent requests.

        Returns:
            List of embedding vectors.

        Raises:
            EmbeddingError: If embedding generation fails.
        """
        if not texts:
            return []

        embeddings: list[list[float]] = []

        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            tasks = [self.embed_text(text) for text in batch]
            batch_results = await asyncio.gather(*tasks)
            embeddings.extend(batch_results)

        return embeddings

    def embed_text_sync(self, text: str) -> list[float]:
        """
        Synchronously generate embedding for text.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector as list of floats.

        Raises:
            EmbeddingError: If embedding generation fails.
        """
        if not text or not text.strip():
            raise EmbeddingError("Cannot embed empty text")

        try:
            client = self._get_sync_client()
            response = client.post(
                "/api/embeddings",
                json={
                    "model": self.model_name,
                    "prompt": text,
                },
            )
            response.raise_for_status()
            data = response.json()
            embedding = data.get("embedding", [])

            if not embedding:
                raise EmbeddingError("Empty embedding returned")

            return embedding

        except httpx.ConnectError as e:
            raise LLMConnectionError(
                f"Failed to connect to Ollama: {e}"
            ) from e
        except httpx.HTTPStatusError as e:
            raise EmbeddingError(
                f"Embedding request failed: {e.response.text}"
            ) from e
        except Exception as e:
            raise EmbeddingError(f"Embedding error: {e}") from e

    def embed_texts_sync(self, texts: list[str]) -> list[list[float]]:
        """
        Synchronously generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors.
        """
        return [self.embed_text_sync(text) for text in texts]


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    Args:
        vec1: First vector.
        vec2: Second vector.

    Returns:
        Cosine similarity score between -1 and 1.
    """
    if len(vec1) != len(vec2):
        raise ValueError("Vectors must have same length")

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = sum(a * a for a in vec1) ** 0.5
    norm2 = sum(b * b for b in vec2) ** 0.5

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)


def euclidean_distance(vec1: list[float], vec2: list[float]) -> float:
    """
    Compute Euclidean distance between two vectors.

    Args:
        vec1: First vector.
        vec2: Second vector.

    Returns:
        Euclidean distance.
    """
    if len(vec1) != len(vec2):
        raise ValueError("Vectors must have same length")

    return sum((a - b) ** 2 for a, b in zip(vec1, vec2)) ** 0.5


def find_most_similar(
    query_embedding: list[float],
    embeddings: list[list[float]],
    top_k: int = 5,
    threshold: float = 0.0,
) -> list[tuple[int, float]]:
    """
    Find most similar embeddings to a query.

    Args:
        query_embedding: Query vector.
        embeddings: List of vectors to search.
        top_k: Number of results to return.
        threshold: Minimum similarity threshold.

    Returns:
        List of (index, similarity) tuples sorted by similarity.
    """
    similarities = [
        (i, cosine_similarity(query_embedding, emb))
        for i, emb in enumerate(embeddings)
    ]

    # Filter by threshold and sort
    filtered = [
        (idx, sim) for idx, sim in similarities if sim >= threshold
    ]
    sorted_results = sorted(filtered, key=lambda x: x[1], reverse=True)

    return sorted_results[:top_k]


class SemanticSearch:
    """
    High-level semantic search interface.

    Provides methods for indexing and searching text using embeddings.
    """

    def __init__(
        self,
        embedding_client: GraniteEmbeddingClient | None = None,
    ) -> None:
        """
        Initialize semantic search.

        Args:
            embedding_client: Embedding client instance.
        """
        self.client = embedding_client or GraniteEmbeddingClient()
        self._documents: list[str] = []
        self._embeddings: list[list[float]] = []
        self._metadata: list[dict[str, Any]] = []

    async def index_documents(
        self,
        documents: list[str],
        metadata: list[dict[str, Any]] | None = None,
    ) -> int:
        """
        Index documents for search.

        Args:
            documents: Documents to index.
            metadata: Optional metadata for each document.

        Returns:
            Number of documents indexed.
        """
        embeddings = await self.client.embed_texts(documents)

        self._documents.extend(documents)
        self._embeddings.extend(embeddings)

        if metadata:
            self._metadata.extend(metadata)
        else:
            self._metadata.extend([{} for _ in documents])

        return len(documents)

    async def search(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """
        Search indexed documents.

        Args:
            query: Search query.
            top_k: Number of results.
            threshold: Minimum similarity.

        Returns:
            List of search results with document, score, metadata.
        """
        if not self._embeddings:
            return []

        query_embedding = await self.client.embed_text(query)
        results = find_most_similar(
            query_embedding,
            self._embeddings,
            top_k=top_k,
            threshold=threshold,
        )

        return [
            {
                "document": self._documents[idx],
                "score": score,
                "metadata": self._metadata[idx],
                "index": idx,
            }
            for idx, score in results
        ]

    def clear(self) -> None:
        """Clear all indexed documents."""
        self._documents.clear()
        self._embeddings.clear()
        self._metadata.clear()

    @property
    def document_count(self) -> int:
        """Get number of indexed documents."""
        return len(self._documents)


# Module-level client instance
_embedding_client: GraniteEmbeddingClient | None = None


def get_embedding_client() -> GraniteEmbeddingClient:
    """
    Get the global embedding client instance.

    Returns:
        GraniteEmbeddingClient singleton.
    """
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = GraniteEmbeddingClient()
    return _embedding_client


async def embed_text(text: str) -> list[float]:
    """
    Convenience function to embed text.

    Args:
        text: Text to embed.

    Returns:
        Embedding vector.
    """
    client = get_embedding_client()
    return await client.embed_text(text)


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Convenience function to embed multiple texts.

    Args:
        texts: Texts to embed.

    Returns:
        List of embedding vectors.
    """
    client = get_embedding_client()
    return await client.embed_texts(texts)
