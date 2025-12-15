"""
Memory Stores for Agent System.

This module provides specialized memory stores for different aspects
of the multi-agent system including agent context, project knowledge,
error patterns, and conversation history.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from app.memory.neo4j_client import Neo4jClient, get_neo4j_client


logger = logging.getLogger(__name__)


# =============================================================================
# Agent Memory Store
# =============================================================================


class AgentMemoryStore:
    """
    Store for agent-specific working memory.

    Manages current task context, scratchpad data, and
    per-agent state persistence.
    """

    def __init__(
        self,
        client: Neo4jClient | None = None,
    ) -> None:
        """
        Initialize agent memory store.

        Args:
            client: Neo4j client instance.
        """
        self.client = client or get_neo4j_client()

    async def create_agent(
        self,
        agent_id: str,
        agent_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create a new agent node in the graph.

        Args:
            agent_id: Unique agent identifier.
            agent_type: Type of agent (pm, coder, reviewer, etc.).
            metadata: Additional agent metadata.

        Returns:
            Created agent data.
        """
        query = """
        MERGE (a:Agent {agent_id: $agent_id})
        ON CREATE SET
            a.agent_type = $agent_type,
            a.created_at = datetime(),
            a.metadata = $metadata
        ON MATCH SET
            a.updated_at = datetime()
        RETURN a
        """

        results = await self.client.execute_query(
            query,
            {
                "agent_id": agent_id,
                "agent_type": agent_type,
                "metadata": metadata or {},
            },
        )

        return results[0]["a"] if results else {}

    async def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        """
        Get agent by ID.

        Args:
            agent_id: Agent identifier.

        Returns:
            Agent data or None.
        """
        query = """
        MATCH (a:Agent {agent_id: $agent_id})
        RETURN a
        """

        results = await self.client.execute_query(
            query,
            {"agent_id": agent_id},
        )

        return results[0]["a"] if results else None

    async def update_scratchpad(
        self,
        agent_id: str,
        scratchpad_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Update agent's scratchpad/working memory.

        Args:
            agent_id: Agent identifier.
            scratchpad_data: Scratchpad data to store.

        Returns:
            Updated scratchpad data.
        """
        query = """
        MATCH (a:Agent {agent_id: $agent_id})
        SET a.scratchpad = $scratchpad_data,
            a.scratchpad_updated_at = datetime()
        RETURN a.scratchpad as scratchpad
        """

        results = await self.client.execute_query(
            query,
            {
                "agent_id": agent_id,
                "scratchpad_data": scratchpad_data,
            },
        )

        return results[0]["scratchpad"] if results else {}

    async def get_scratchpad(
        self,
        agent_id: str,
    ) -> dict[str, Any]:
        """
        Get agent's current scratchpad.

        Args:
            agent_id: Agent identifier.

        Returns:
            Scratchpad data.
        """
        query = """
        MATCH (a:Agent {agent_id: $agent_id})
        RETURN a.scratchpad as scratchpad
        """

        results = await self.client.execute_query(
            query,
            {"agent_id": agent_id},
        )

        return results[0]["scratchpad"] if results else {}

    async def assign_task(
        self,
        agent_id: str,
        task_id: str,
    ) -> dict[str, Any]:
        """
        Assign a task to an agent.

        Args:
            agent_id: Agent identifier.
            task_id: Task identifier.

        Returns:
            Assignment relationship data.
        """
        query = """
        MATCH (a:Agent {agent_id: $agent_id})
        MATCH (t:Task {task_id: $task_id})
        MERGE (a)-[r:ASSIGNED_TO]->(t)
        ON CREATE SET r.assigned_at = datetime()
        RETURN r
        """

        results = await self.client.execute_query(
            query,
            {
                "agent_id": agent_id,
                "task_id": task_id,
            },
        )

        return results[0]["r"] if results else {}

    async def get_agent_tasks(
        self,
        agent_id: str,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get tasks assigned to an agent.

        Args:
            agent_id: Agent identifier.
            status: Optional status filter.

        Returns:
            List of task data.
        """
        if status:
            query = """
            MATCH (a:Agent {agent_id: $agent_id})-[:ASSIGNED_TO]->(t:Task)
            WHERE t.status = $status
            RETURN t
            ORDER BY t.created_at DESC
            """
            params = {"agent_id": agent_id, "status": status}
        else:
            query = """
            MATCH (a:Agent {agent_id: $agent_id})-[:ASSIGNED_TO]->(t:Task)
            RETURN t
            ORDER BY t.created_at DESC
            """
            params = {"agent_id": agent_id}

        results = await self.client.execute_query(query, params)
        return [r["t"] for r in results]


# =============================================================================
# Project Knowledge Store
# =============================================================================


class ProjectKnowledgeStore:
    """
    Store for project-wide knowledge and context.

    Manages shared knowledge, code snippets, documentation,
    and architectural decisions accessible by all agents.
    """

    def __init__(
        self,
        client: Neo4jClient | None = None,
    ) -> None:
        """
        Initialize project knowledge store.

        Args:
            client: Neo4j client instance.
        """
        self.client = client or get_neo4j_client()

    async def add_knowledge(
        self,
        title: str,
        content: str,
        knowledge_type: str,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        embedding: list[float] | None = None,
    ) -> dict[str, Any]:
        """
        Add knowledge to the project knowledge base.

        Args:
            title: Knowledge title.
            content: Knowledge content.
            knowledge_type: Type (code, doc, architecture, etc.).
            tags: Optional tags for categorization.
            metadata: Additional metadata.
            embedding: Optional embedding vector.

        Returns:
            Created knowledge node data.
        """
        knowledge_id = str(uuid.uuid4())

        query = """
        CREATE (k:Knowledge {
            knowledge_id: $knowledge_id,
            title: $title,
            content: $content,
            knowledge_type: $knowledge_type,
            tags: $tags,
            metadata: $metadata,
            embedding: $embedding,
            created_at: datetime()
        })
        RETURN k
        """

        results = await self.client.execute_query(
            query,
            {
                "knowledge_id": knowledge_id,
                "title": title,
                "content": content,
                "knowledge_type": knowledge_type,
                "tags": tags or [],
                "metadata": metadata or {},
                "embedding": embedding,
            },
        )

        return results[0]["k"] if results else {}

    async def search_knowledge(
        self,
        query_text: str,
        knowledge_type: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search knowledge by text using full-text search.

        Args:
            query_text: Search query.
            knowledge_type: Optional type filter.
            limit: Maximum results.

        Returns:
            List of matching knowledge nodes.
        """
        if knowledge_type:
            query = """
            CALL db.index.fulltext.queryNodes(
                'knowledge_content', $query_text
            ) YIELD node, score
            WHERE node.knowledge_type = $knowledge_type
            RETURN node, score
            ORDER BY score DESC
            LIMIT $limit
            """
            params = {
                "query_text": query_text,
                "knowledge_type": knowledge_type,
                "limit": limit,
            }
        else:
            query = """
            CALL db.index.fulltext.queryNodes(
                'knowledge_content', $query_text
            ) YIELD node, score
            RETURN node, score
            ORDER BY score DESC
            LIMIT $limit
            """
            params = {"query_text": query_text, "limit": limit}

        results = await self.client.execute_query(query, params)
        return [
            {"knowledge": r["node"], "score": r["score"]}
            for r in results
        ]

    async def get_by_type(
        self,
        knowledge_type: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Get knowledge by type.

        Args:
            knowledge_type: Knowledge type filter.
            limit: Maximum results.

        Returns:
            List of knowledge nodes.
        """
        query = """
        MATCH (k:Knowledge)
        WHERE k.knowledge_type = $knowledge_type
        RETURN k
        ORDER BY k.created_at DESC
        LIMIT $limit
        """

        results = await self.client.execute_query(
            query,
            {"knowledge_type": knowledge_type, "limit": limit},
        )

        return [r["k"] for r in results]

    async def get_by_tags(
        self,
        tags: list[str],
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Get knowledge by tags (match any).

        Args:
            tags: Tags to search for.
            limit: Maximum results.

        Returns:
            List of knowledge nodes.
        """
        query = """
        MATCH (k:Knowledge)
        WHERE any(tag IN $tags WHERE tag IN k.tags)
        RETURN k
        ORDER BY k.created_at DESC
        LIMIT $limit
        """

        results = await self.client.execute_query(
            query,
            {"tags": tags, "limit": limit},
        )

        return [r["k"] for r in results]

    async def link_knowledge(
        self,
        from_id: str,
        to_id: str,
        relationship_type: str,
    ) -> dict[str, Any]:
        """
        Create a relationship between knowledge nodes.

        Args:
            from_id: Source knowledge ID.
            to_id: Target knowledge ID.
            relationship_type: Type of relationship.

        Returns:
            Relationship data.
        """
        query = f"""
        MATCH (k1:Knowledge {{knowledge_id: $from_id}})
        MATCH (k2:Knowledge {{knowledge_id: $to_id}})
        MERGE (k1)-[r:{relationship_type}]->(k2)
        ON CREATE SET r.created_at = datetime()
        RETURN r
        """

        results = await self.client.execute_query(
            query,
            {"from_id": from_id, "to_id": to_id},
        )

        return results[0]["r"] if results else {}


# =============================================================================
# Error Pattern Store
# =============================================================================


class ErrorPatternStore:
    """
    Store for error patterns and prevention strategies.

    Tracks errors encountered during execution, their solutions,
    and patterns for prevention.
    """

    def __init__(
        self,
        client: Neo4jClient | None = None,
    ) -> None:
        """
        Initialize error pattern store.

        Args:
            client: Neo4j client instance.
        """
        self.client = client or get_neo4j_client()

    async def log_error(
        self,
        error_type: str,
        error_message: str,
        context: dict[str, Any],
        agent_id: str | None = None,
        task_id: str | None = None,
        stack_trace: str | None = None,
    ) -> dict[str, Any]:
        """
        Log an error occurrence.

        Args:
            error_type: Type/class of error.
            error_message: Error message.
            context: Error context data.
            agent_id: Optional agent that encountered error.
            task_id: Optional task during which error occurred.
            stack_trace: Optional stack trace.

        Returns:
            Created error node data.
        """
        error_id = str(uuid.uuid4())

        query = """
        CREATE (e:Error {
            error_id: $error_id,
            error_type: $error_type,
            error_message: $error_message,
            context: $context,
            stack_trace: $stack_trace,
            created_at: datetime(),
            resolved: false
        })
        RETURN e
        """

        results = await self.client.execute_query(
            query,
            {
                "error_id": error_id,
                "error_type": error_type,
                "error_message": error_message,
                "context": context,
                "stack_trace": stack_trace,
            },
        )

        error_node = results[0]["e"] if results else {}

        # Link to agent if provided
        if agent_id:
            await self.client.execute_query(
                """
                MATCH (e:Error {error_id: $error_id})
                MATCH (a:Agent {agent_id: $agent_id})
                MERGE (a)-[:ENCOUNTERED]->(e)
                """,
                {"error_id": error_id, "agent_id": agent_id},
            )

        # Link to task if provided
        if task_id:
            await self.client.execute_query(
                """
                MATCH (e:Error {error_id: $error_id})
                MATCH (t:Task {task_id: $task_id})
                MERGE (e)-[:OCCURRED_IN]->(t)
                """,
                {"error_id": error_id, "task_id": task_id},
            )

        return error_node

    async def add_solution(
        self,
        error_id: str,
        solution: str,
        effectiveness: float = 1.0,
    ) -> dict[str, Any]:
        """
        Add a solution for an error.

        Args:
            error_id: Error identifier.
            solution: Solution description.
            effectiveness: Solution effectiveness (0-1).

        Returns:
            Updated error data.
        """
        query = """
        MATCH (e:Error {error_id: $error_id})
        SET e.solution = $solution,
            e.effectiveness = $effectiveness,
            e.resolved = true,
            e.resolved_at = datetime()
        RETURN e
        """

        results = await self.client.execute_query(
            query,
            {
                "error_id": error_id,
                "solution": solution,
                "effectiveness": effectiveness,
            },
        )

        return results[0]["e"] if results else {}

    async def find_similar_errors(
        self,
        error_type: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Find similar past errors with solutions.

        Args:
            error_type: Error type to search for.
            limit: Maximum results.

        Returns:
            List of similar errors with solutions.
        """
        query = """
        MATCH (e:Error)
        WHERE e.error_type = $error_type AND e.resolved = true
        RETURN e
        ORDER BY e.effectiveness DESC, e.resolved_at DESC
        LIMIT $limit
        """

        results = await self.client.execute_query(
            query,
            {"error_type": error_type, "limit": limit},
        )

        return [r["e"] for r in results]

    async def get_error_statistics(
        self,
        time_range_hours: int = 24,
    ) -> dict[str, Any]:
        """
        Get error statistics.

        Args:
            time_range_hours: Hours to look back.

        Returns:
            Error statistics.
        """
        query = """
        MATCH (e:Error)
        WHERE e.created_at >= datetime() - duration({hours: $hours})
        WITH e.error_type as error_type, count(*) as count
        RETURN error_type, count
        ORDER BY count DESC
        """

        results = await self.client.execute_query(
            query,
            {"hours": time_range_hours},
        )

        return {
            "by_type": {r["error_type"]: r["count"] for r in results},
            "total": sum(r["count"] for r in results),
        }


# =============================================================================
# Conversation History Store
# =============================================================================


class ConversationHistoryStore:
    """
    Store for conversation history and message persistence.

    Manages conversation sessions, messages, and
    context for multi-turn interactions.
    """

    def __init__(
        self,
        client: Neo4jClient | None = None,
    ) -> None:
        """
        Initialize conversation history store.

        Args:
            client: Neo4j client instance.
        """
        self.client = client or get_neo4j_client()

    async def create_session(
        self,
        session_id: str | None = None,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create a new conversation session.

        Args:
            session_id: Optional session ID (generated if not provided).
            user_id: Optional user identifier.
            metadata: Additional session metadata.

        Returns:
            Created session data.
        """
        session_id = session_id or str(uuid.uuid4())

        query = """
        CREATE (s:Session {
            session_id: $session_id,
            user_id: $user_id,
            metadata: $metadata,
            created_at: datetime(),
            message_count: 0
        })
        RETURN s
        """

        results = await self.client.execute_query(
            query,
            {
                "session_id": session_id,
                "user_id": user_id,
                "metadata": metadata or {},
            },
        )

        return results[0]["s"] if results else {}

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        agent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Add a message to a conversation session.

        Args:
            session_id: Session identifier.
            role: Message role (user, assistant, system).
            content: Message content.
            agent_id: Optional agent that produced the message.
            metadata: Additional message metadata.

        Returns:
            Created message data.
        """
        message_id = str(uuid.uuid4())

        query = """
        MATCH (s:Session {session_id: $session_id})
        CREATE (m:Message {
            message_id: $message_id,
            role: $role,
            content: $content,
            agent_id: $agent_id,
            metadata: $metadata,
            timestamp: datetime()
        })
        CREATE (s)-[:HAS_MESSAGE]->(m)
        SET s.message_count = s.message_count + 1,
            s.last_message_at = datetime()
        RETURN m
        """

        results = await self.client.execute_query(
            query,
            {
                "session_id": session_id,
                "message_id": message_id,
                "role": role,
                "content": content,
                "agent_id": agent_id,
                "metadata": metadata or {},
            },
        )

        return results[0]["m"] if results else {}

    async def get_session_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Get messages for a session.

        Args:
            session_id: Session identifier.
            limit: Maximum messages to return.
            offset: Pagination offset.

        Returns:
            List of messages in chronological order.
        """
        query = """
        MATCH (s:Session {session_id: $session_id})-[:HAS_MESSAGE]->(m:Message)
        RETURN m
        ORDER BY m.timestamp ASC
        SKIP $offset
        LIMIT $limit
        """

        results = await self.client.execute_query(
            query,
            {"session_id": session_id, "limit": limit, "offset": offset},
        )

        return [r["m"] for r in results]

    async def get_recent_context(
        self,
        session_id: str,
        max_messages: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Get recent conversation context.

        Args:
            session_id: Session identifier.
            max_messages: Maximum recent messages.

        Returns:
            Recent messages for context.
        """
        query = """
        MATCH (s:Session {session_id: $session_id})-[:HAS_MESSAGE]->(m:Message)
        RETURN m
        ORDER BY m.timestamp DESC
        LIMIT $max_messages
        """

        results = await self.client.execute_query(
            query,
            {"session_id": session_id, "max_messages": max_messages},
        )

        # Reverse to get chronological order
        return [r["m"] for r in reversed(results)]

    async def get_session(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:
        """
        Get session data.

        Args:
            session_id: Session identifier.

        Returns:
            Session data or None.
        """
        query = """
        MATCH (s:Session {session_id: $session_id})
        RETURN s
        """

        results = await self.client.execute_query(
            query,
            {"session_id": session_id},
        )

        return results[0]["s"] if results else None

    async def search_messages(
        self,
        session_id: str,
        query_text: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search messages within a session.

        Args:
            session_id: Session identifier.
            query_text: Search query.
            limit: Maximum results.

        Returns:
            Matching messages.
        """
        query = """
        CALL db.index.fulltext.queryNodes(
            'message_content', $query_text
        ) YIELD node, score
        MATCH (s:Session {session_id: $session_id})-[:HAS_MESSAGE]->(node)
        RETURN node, score
        ORDER BY score DESC
        LIMIT $limit
        """

        results = await self.client.execute_query(
            query,
            {"session_id": session_id, "query_text": query_text, "limit": limit},
        )

        return [
            {"message": r["node"], "score": r["score"]}
            for r in results
        ]


# =============================================================================
# Task Store
# =============================================================================


class TaskStore:
    """
    Store for task management and tracking.

    Manages tasks, subtasks, and their relationships
    to agents and sessions.
    """

    def __init__(
        self,
        client: Neo4jClient | None = None,
    ) -> None:
        """
        Initialize task store.

        Args:
            client: Neo4j client instance.
        """
        self.client = client or get_neo4j_client()

    async def create_task(
        self,
        title: str,
        description: str,
        session_id: str | None = None,
        parent_task_id: str | None = None,
        priority: int = 5,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create a new task.

        Args:
            title: Task title.
            description: Task description.
            session_id: Optional session ID.
            parent_task_id: Optional parent task for subtasks.
            priority: Task priority (1-10).
            metadata: Additional task metadata.

        Returns:
            Created task data.
        """
        task_id = str(uuid.uuid4())

        query = """
        CREATE (t:Task {
            task_id: $task_id,
            title: $title,
            description: $description,
            priority: $priority,
            status: 'pending',
            metadata: $metadata,
            created_at: datetime()
        })
        RETURN t
        """

        results = await self.client.execute_query(
            query,
            {
                "task_id": task_id,
                "title": title,
                "description": description,
                "priority": priority,
                "metadata": metadata or {},
            },
        )

        task_node = results[0]["t"] if results else {}

        # Link to session if provided
        if session_id:
            await self.client.execute_query(
                """
                MATCH (t:Task {task_id: $task_id})
                MATCH (s:Session {session_id: $session_id})
                MERGE (s)-[:HAS_TASK]->(t)
                """,
                {"task_id": task_id, "session_id": session_id},
            )

        # Link to parent task if provided
        if parent_task_id:
            await self.client.execute_query(
                """
                MATCH (t:Task {task_id: $task_id})
                MATCH (p:Task {task_id: $parent_task_id})
                MERGE (p)-[:HAS_SUBTASK]->(t)
                """,
                {"task_id": task_id, "parent_task_id": parent_task_id},
            )

        return task_node

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Update task status.

        Args:
            task_id: Task identifier.
            status: New status.
            result: Optional task result.

        Returns:
            Updated task data.
        """
        query = """
        MATCH (t:Task {task_id: $task_id})
        SET t.status = $status,
            t.result = $result,
            t.updated_at = datetime()
        RETURN t
        """

        results = await self.client.execute_query(
            query,
            {
                "task_id": task_id,
                "status": status,
                "result": result,
            },
        )

        return results[0]["t"] if results else {}

    async def get_task(
        self,
        task_id: str,
    ) -> dict[str, Any] | None:
        """
        Get task by ID.

        Args:
            task_id: Task identifier.

        Returns:
            Task data or None.
        """
        query = """
        MATCH (t:Task {task_id: $task_id})
        RETURN t
        """

        results = await self.client.execute_query(
            query,
            {"task_id": task_id},
        )

        return results[0]["t"] if results else None

    async def get_subtasks(
        self,
        task_id: str,
    ) -> list[dict[str, Any]]:
        """
        Get subtasks of a task.

        Args:
            task_id: Parent task identifier.

        Returns:
            List of subtask data.
        """
        query = """
        MATCH (t:Task {task_id: $task_id})-[:HAS_SUBTASK]->(st:Task)
        RETURN st
        ORDER BY st.priority DESC, st.created_at ASC
        """

        results = await self.client.execute_query(
            query,
            {"task_id": task_id},
        )

        return [r["st"] for r in results]


# =============================================================================
# Module-level store instances
# =============================================================================


_agent_store: AgentMemoryStore | None = None
_knowledge_store: ProjectKnowledgeStore | None = None
_error_store: ErrorPatternStore | None = None
_conversation_store: ConversationHistoryStore | None = None
_task_store: TaskStore | None = None


def get_agent_store() -> AgentMemoryStore:
    """Get agent memory store singleton."""
    global _agent_store
    if _agent_store is None:
        _agent_store = AgentMemoryStore()
    return _agent_store


def get_knowledge_store() -> ProjectKnowledgeStore:
    """Get project knowledge store singleton."""
    global _knowledge_store
    if _knowledge_store is None:
        _knowledge_store = ProjectKnowledgeStore()
    return _knowledge_store


def get_error_store() -> ErrorPatternStore:
    """Get error pattern store singleton."""
    global _error_store
    if _error_store is None:
        _error_store = ErrorPatternStore()
    return _error_store


def get_conversation_store() -> ConversationHistoryStore:
    """Get conversation history store singleton."""
    global _conversation_store
    if _conversation_store is None:
        _conversation_store = ConversationHistoryStore()
    return _conversation_store


def get_task_store() -> TaskStore:
    """Get task store singleton."""
    global _task_store
    if _task_store is None:
        _task_store = TaskStore()
    return _task_store
