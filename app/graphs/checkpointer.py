"""
Checkpointer Module.

This module provides checkpointing functionality for LangGraph workflows,
enabling state persistence, recovery, and time-travel debugging.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from langgraph.checkpoint.memory import MemorySaver

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver


logger = logging.getLogger(__name__)


def create_memory_checkpointer() -> MemorySaver:
    """
    Create an in-memory checkpointer for development and testing.

    The MemorySaver stores checkpoints in memory, which means
    they are lost when the process terminates. Use this for
    development and testing purposes.

    Returns:
        A configured MemorySaver instance.
    """
    logger.info("Creating in-memory checkpointer")
    return MemorySaver()


def get_checkpointer(
    storage_type: str = "memory",
    **kwargs: Any,
) -> BaseCheckpointSaver[Any]:
    """
    Factory function to create a checkpointer based on storage type.

    Args:
        storage_type: Type of storage ("memory", "sqlite", "postgres").
        **kwargs: Additional arguments for the specific checkpointer.

    Returns:
        A configured checkpointer instance.

    Raises:
        ValueError: If storage_type is not supported.

    Note:
        For production, consider using persistent storage like
        SQLite or PostgreSQL checkpointers when available.
    """
    if storage_type == "memory":
        return create_memory_checkpointer()
    elif storage_type == "sqlite":
        # SQLite checkpointer requires additional dependencies
        # and configuration. For now, fall back to memory.
        logger.warning(
            "SQLite checkpointer not yet implemented, using memory"
        )
        return create_memory_checkpointer()
    elif storage_type == "postgres":
        # PostgreSQL checkpointer requires additional dependencies
        # and configuration. For now, fall back to memory.
        logger.warning(
            "PostgreSQL checkpointer not yet implemented, using memory"
        )
        return create_memory_checkpointer()
    else:
        raise ValueError(f"Unsupported storage type: {storage_type}")


def create_checkpointer(
    storage_type: str = "memory",
    **kwargs: Any,
) -> BaseCheckpointSaver[Any]:
    """
    Backward-compatible wrapper for creating a checkpointer.

    Args:
        storage_type: Type of storage ("memory", "sqlite", "postgres").
        **kwargs: Additional arguments for the specific checkpointer.

    Returns:
        A configured checkpointer instance.
    """
    return get_checkpointer(storage_type=storage_type, **kwargs)


class CheckpointManager:
    """
    Manager class for handling checkpoint operations.

    This class provides a higher-level interface for checkpoint
    operations including listing, retrieving, and managing
    checkpoints for workflow state inspection and time-travel.
    """

    def __init__(
        self,
        checkpointer: BaseCheckpointSaver[Any],
    ) -> None:
        """
        Initialize the checkpoint manager.

        Args:
            checkpointer: The underlying checkpointer to manage.
        """
        self._checkpointer = checkpointer

    @property
    def checkpointer(self) -> BaseCheckpointSaver[Any]:
        """Get the underlying checkpointer."""
        return self._checkpointer

    async def get_checkpoint(
        self,
        thread_id: str,
        checkpoint_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Retrieve a checkpoint for a given thread.

        Args:
            thread_id: The thread/session identifier.
            checkpoint_id: Optional specific checkpoint to retrieve.
                          If None, returns the latest checkpoint.

        Returns:
            The checkpoint data if found, None otherwise.
        """
        config = {"configurable": {"thread_id": thread_id}}
        if checkpoint_id:
            config["configurable"]["checkpoint_id"] = checkpoint_id

        try:
            checkpoint = self._checkpointer.get(config)
            if checkpoint:
                return dict(checkpoint)
            return None
        except Exception as e:
            logger.error(f"Error retrieving checkpoint: {e}")
            return None

    async def list_checkpoints(
        self,
        thread_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        List checkpoints for a given thread.

        Args:
            thread_id: The thread/session identifier.
            limit: Maximum number of checkpoints to return.

        Returns:
            List of checkpoint metadata.
        """
        config = {"configurable": {"thread_id": thread_id}}

        try:
            checkpoints = list(self._checkpointer.list(config, limit=limit))
            return [
                {
                    "checkpoint_id": cp.config.get(
                        "configurable", {}
                    ).get("checkpoint_id"),
                    "thread_id": thread_id,
                    "parent_id": cp.parent_config.get(
                        "configurable", {}
                    ).get("checkpoint_id")
                    if cp.parent_config
                    else None,
                }
                for cp in checkpoints
            ]
        except Exception as e:
            logger.error(f"Error listing checkpoints: {e}")
            return []

    async def get_checkpoint_state(
        self,
        thread_id: str,
        checkpoint_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Get the full state from a checkpoint.

        Args:
            thread_id: The thread/session identifier.
            checkpoint_id: Optional specific checkpoint to retrieve.

        Returns:
            The full state dictionary if found.
        """
        checkpoint = await self.get_checkpoint(thread_id, checkpoint_id)
        if checkpoint and "channel_values" in checkpoint:
            return dict(checkpoint["channel_values"])
        return None
