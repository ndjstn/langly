"""
Neo4j Database Client for Graph Memory Storage.

This module provides an async client for Neo4j graph database operations
supporting agent memory, project knowledge, and conversation persistence.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator

from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession
from neo4j.exceptions import (
    AuthError,
    Neo4jError,
    ServiceUnavailable,
)

from app.config import Settings
from app.core.exceptions import LanglyMemoryError


logger = logging.getLogger(__name__)


class Neo4jClient:
    """
    Async Neo4j database client.

    Provides connection management and query execution for
    graph-based memory storage.
    """

    def __init__(
        self,
        settings: Settings | None = None,
    ) -> None:
        """
        Initialize Neo4j client.

        Args:
            settings: Application settings with Neo4j configuration.
        """
        self.settings = settings or Settings()
        self._driver: AsyncDriver | None = None
        self._connected = False

    @property
    def uri(self) -> str:
        """Get Neo4j connection URI."""
        return self.settings.neo4j_uri

    @property
    def database(self) -> str:
        """Get Neo4j database name."""
        return self.settings.neo4j_database

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._connected and self._driver is not None

    async def connect(self) -> None:
        """
        Establish connection to Neo4j database.

        Raises:
            MemoryError: If connection fails.
        """
        if self._connected:
            return

        try:
            self._driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(
                    self.settings.neo4j_user,
                    self.settings.neo4j_password,
                ),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_acquisition_timeout=60,
            )

            # Verify connectivity
            await self._driver.verify_connectivity()
            self._connected = True
            logger.info(f"Connected to Neo4j at {self.uri}")

        except AuthError as e:
            raise LanglyMemoryError(
                f"Neo4j authentication failed: {e}"
            ) from e
        except ServiceUnavailable as e:
            raise LanglyMemoryError(
                f"Neo4j service unavailable: {e}"
            ) from e
        except Exception as e:
            raise LanglyMemoryError(
                f"Failed to connect to Neo4j: {e}"
            ) from e

    async def close(self) -> None:
        """Close Neo4j connection."""
        if self._driver:
            await self._driver.close()
            self._driver = None
            self._connected = False
            logger.info("Disconnected from Neo4j")

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """
        Get a database session context manager.

        Yields:
            AsyncSession for database operations.

        Raises:
            MemoryError: If not connected.
        """
        if not self._driver:
            await self.connect()

        session = self._driver.session(database=self.database)
        try:
            yield session
        finally:
            await session.close()

    async def execute_query(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute a Cypher query and return results.

        Args:
            query: Cypher query string.
            parameters: Query parameters.

        Returns:
            List of result records as dictionaries.

        Raises:
            MemoryError: If query execution fails.
        """
        try:
            async with self.session() as session:
                result = await session.run(query, parameters or {})
                records = await result.data()
                return records

        except Neo4jError as e:
            raise LanglyMemoryError(f"Query execution failed: {e}") from e
        except Exception as e:
            raise LanglyMemoryError(f"Database error: {e}") from e

    async def execute_write(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute a write transaction and return summary.

        Args:
            query: Cypher write query.
            parameters: Query parameters.

        Returns:
            Transaction summary with counters.

        Raises:
            MemoryError: If write operation fails.
        """
        try:
            async with self.session() as session:

                async def _write_tx(tx):
                    result = await tx.run(query, parameters or {})
                    summary = await result.consume()
                    return {
                        "nodes_created": summary.counters.nodes_created,
                        "nodes_deleted": summary.counters.nodes_deleted,
                        "relationships_created": (
                            summary.counters.relationships_created
                        ),
                        "relationships_deleted": (
                            summary.counters.relationships_deleted
                        ),
                        "properties_set": summary.counters.properties_set,
                    }

                return await session.execute_write(_write_tx)

        except Neo4jError as e:
            raise LanglyMemoryError(f"Write operation failed: {e}") from e
        except Exception as e:
            raise LanglyMemoryError(f"Database error: {e}") from e

    async def health_check(self) -> dict[str, Any]:
        """
        Check Neo4j connection health.

        Returns:
            Health status dictionary.
        """
        try:
            if not self._driver:
                return {
                    "status": "disconnected",
                    "connected": False,
                }

            await self._driver.verify_connectivity()

            # Get server info
            records = await self.execute_query(
                "CALL dbms.components() YIELD name, versions "
                "RETURN name, versions[0] as version"
            )

            return {
                "status": "healthy",
                "connected": True,
                "uri": self.uri,
                "database": self.database,
                "server_info": records[0] if records else None,
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e),
            }

    async def create_indexes(self) -> None:
        """
        Create database indexes for optimal query performance.

        Raises:
            MemoryError: If index creation fails.
        """
        indexes = [
            # Session indexes
            "CREATE INDEX session_id IF NOT EXISTS "
            "FOR (s:Session) ON (s.session_id)",
            # Agent indexes
            "CREATE INDEX agent_id IF NOT EXISTS "
            "FOR (a:Agent) ON (a.agent_id)",
            "CREATE INDEX agent_type IF NOT EXISTS "
            "FOR (a:Agent) ON (a.agent_type)",
            # Task indexes
            "CREATE INDEX task_id IF NOT EXISTS "
            "FOR (t:Task) ON (t.task_id)",
            "CREATE INDEX task_status IF NOT EXISTS "
            "FOR (t:Task) ON (t.status)",
            # Message indexes
            "CREATE INDEX message_id IF NOT EXISTS "
            "FOR (m:Message) ON (m.message_id)",
            "CREATE INDEX message_timestamp IF NOT EXISTS "
            "FOR (m:Message) ON (m.timestamp)",
            # Error indexes
            "CREATE INDEX error_id IF NOT EXISTS "
            "FOR (e:Error) ON (e.error_id)",
            "CREATE INDEX error_type IF NOT EXISTS "
            "FOR (e:Error) ON (e.error_type)",
            # Knowledge indexes
            "CREATE INDEX knowledge_id IF NOT EXISTS "
            "FOR (k:Knowledge) ON (k.knowledge_id)",
            "CREATE INDEX knowledge_type IF NOT EXISTS "
            "FOR (k:Knowledge) ON (k.knowledge_type)",
            # Full-text search indexes
            "CREATE FULLTEXT INDEX message_content IF NOT EXISTS "
            "FOR (m:Message) ON EACH [m.content]",
            "CREATE FULLTEXT INDEX knowledge_content IF NOT EXISTS "
            "FOR (k:Knowledge) ON EACH [k.content, k.title]",
        ]

        for index_query in indexes:
            try:
                await self.execute_write(index_query)
            except LanglyMemoryError as e:
                # Index may already exist
                if "already exists" not in str(e).lower():
                    logger.warning(f"Index creation warning: {e}")

        logger.info("Database indexes created/verified")

    async def create_constraints(self) -> None:
        """
        Create database constraints for data integrity.

        Raises:
            MemoryError: If constraint creation fails.
        """
        constraints = [
            # Unique constraints
            "CREATE CONSTRAINT session_unique IF NOT EXISTS "
            "FOR (s:Session) REQUIRE s.session_id IS UNIQUE",
            "CREATE CONSTRAINT agent_unique IF NOT EXISTS "
            "FOR (a:Agent) REQUIRE a.agent_id IS UNIQUE",
            "CREATE CONSTRAINT task_unique IF NOT EXISTS "
            "FOR (t:Task) REQUIRE t.task_id IS UNIQUE",
            "CREATE CONSTRAINT message_unique IF NOT EXISTS "
            "FOR (m:Message) REQUIRE m.message_id IS UNIQUE",
            "CREATE CONSTRAINT error_unique IF NOT EXISTS "
            "FOR (e:Error) REQUIRE e.error_id IS UNIQUE",
            "CREATE CONSTRAINT knowledge_unique IF NOT EXISTS "
            "FOR (k:Knowledge) REQUIRE k.knowledge_id IS UNIQUE",
        ]

        for constraint_query in constraints:
            try:
                await self.execute_write(constraint_query)
            except LanglyMemoryError as e:
                # Constraint may already exist
                if "already exists" not in str(e).lower():
                    logger.warning(f"Constraint creation warning: {e}")

        logger.info("Database constraints created/verified")

    async def initialize_schema(self) -> None:
        """
        Initialize the complete database schema.

        Creates all indexes and constraints needed for
        the memory system.
        """
        await self.create_constraints()
        await self.create_indexes()
        logger.info("Database schema initialized")

    async def clear_database(self) -> dict[str, int]:
        """
        Clear all data from the database.

        WARNING: This deletes all nodes and relationships!

        Returns:
            Summary of deleted items.
        """
        result = await self.execute_write(
            "MATCH (n) DETACH DELETE n"
        )
        logger.warning("Database cleared - all data deleted")
        return result


# Module-level client instance
_neo4j_client: Neo4jClient | None = None


def get_neo4j_client() -> Neo4jClient:
    """
    Get the global Neo4j client instance.

    Returns:
        Neo4jClient singleton.
    """
    global _neo4j_client
    if _neo4j_client is None:
        _neo4j_client = Neo4jClient()
    return _neo4j_client


async def initialize_database() -> None:
    """
    Initialize the Neo4j database connection and schema.

    Call this during application startup.
    """
    client = get_neo4j_client()
    await client.connect()
    await client.initialize_schema()


async def close_database() -> None:
    """
    Close the Neo4j database connection.

    Call this during application shutdown.
    """
    global _neo4j_client
    if _neo4j_client:
        await _neo4j_client.close()
        _neo4j_client = None


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """
    Dependency injection helper for FastAPI.

    Yields:
        Neo4j session for the request.
    """
    client = get_neo4j_client()
    async with client.session() as session:
        yield session
