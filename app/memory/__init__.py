"""
Memory Module for Langly Multi-Agent System.

This module provides persistent memory and state management
using Neo4j as the graph database backend.
"""
from app.memory.neo4j_client import (
    Neo4jClient,
    close_database,
    get_neo4j_client,
    get_session,
    initialize_database,
)
from app.memory.stores import (
    AgentMemoryStore,
    ConversationHistoryStore,
    ErrorPatternStore,
    ProjectKnowledgeStore,
    TaskStore,
    get_agent_store,
    get_conversation_store,
    get_error_store,
    get_knowledge_store,
    get_task_store,
)


__all__ = [
    # Neo4j Client
    "Neo4jClient",
    "get_neo4j_client",
    "initialize_database",
    "close_database",
    "get_session",
    # Memory Stores
    "AgentMemoryStore",
    "ProjectKnowledgeStore",
    "ErrorPatternStore",
    "ConversationHistoryStore",
    "TaskStore",
    # Store getters
    "get_agent_store",
    "get_knowledge_store",
    "get_error_store",
    "get_conversation_store",
    "get_task_store",
]
