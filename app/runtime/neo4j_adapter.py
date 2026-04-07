"""Optional Neo4j adapter for v2 memory."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from app.memory.neo4j_client import Neo4jClient, get_neo4j_client


class Neo4jMemoryAdapter:
    """Minimal adapter for persisting summaries in Neo4j."""

    def __init__(self, client: Neo4jClient | None = None) -> None:
        self._client = client or get_neo4j_client()

    async def store_summary(self, session_id: UUID, summary: str) -> dict[str, Any]:
        query = """
        MERGE (s:Session {session_id: $session_id})
        SET s.summary = $summary,
            s.updated_at = datetime()
        RETURN s
        """
        records = await self._client.execute_query(
            query,
            {"session_id": str(session_id), "summary": summary},
        )
        return records[0]["s"] if records else {}

    async def get_summary(self, session_id: UUID) -> str | None:
        query = """
        MATCH (s:Session {session_id: $session_id})
        RETURN s.summary as summary
        """
        records = await self._client.execute_query(
            query,
            {"session_id": str(session_id)},
        )
        if not records:
            return None
        return records[0].get("summary")
