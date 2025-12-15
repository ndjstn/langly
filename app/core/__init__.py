"""
Core module for Pydantic schemas, exceptions, and constants.

This module contains the foundational data models and types used
throughout the multi-agent coding platform.

Components:
    schemas: Pydantic models for messages, agents, workflows
    exceptions: Custom exception classes
    constants: Application constants and IBM Granite model mappings
"""
from typing import Any

# Lazy imports to avoid circular dependencies


def __getattr__(name: str) -> Any:
    """Lazy import attributes to avoid circular imports."""
    # Schema imports
    schema_names = {
        "AgentStateSchema",
        "AgentType",
        "Message",
        "MessageRole",
        "ScratchpadEntry",
        "Task",
        "TaskStatus",
        "ToolCall",
        "ToolResult",
        "WorkflowConfig",
        "WorkflowRun",
        "WorkflowStatus",
        "ChatRequest",
        "ChatResponse",
        "HealthStatus",
        "AgentInfo",
        "InterventionType",
        "InterventionRequest",
        "InterventionResponse",
    }

    exception_names = {
        "LanglyError",
        "AgentError",
        "AgentNotFoundError",
        "AgentBusyError",
        "OllamaConnectionError",
        "Neo4jConnectionError",
        "ModelNotAvailableError",
        "WorkflowError",
        "WorkflowTimeoutError",
        "WorkflowNotFoundError",
        "WorkflowStateError",
        "LoopDetectedError",
        "HumanInterventionRequired",
        "InterventionTimeoutError",
        "ToolError",
        "ToolNotFoundError",
        "ToolExecutionError",
        "ToolValidationError",
        "SafetyError",
        "MemoryStoreError",
        "MemoryRetrievalError",
        "ConfigurationError",
    }

    constant_names = {
        "AGENT_MODEL_MAPPING",
        "AGENT_SYSTEM_PROMPTS",
        "DEFAULT_MAX_ITERATIONS",
        "DEFAULT_TIMEOUT_SECONDS",
        "DEFAULT_CHECKPOINT_INTERVAL",
        "GRANITE_MODELS",
        "MODEL_FALLBACKS",
        "NODE_NAMES",
        "API_RATE_LIMITS",
        "MAX_MESSAGE_LENGTH",
        "MAX_CONVERSATION_HISTORY",
        "SAFETY_CHECK_TRIGGERS",
        "BLOCKED_OPERATIONS",
        "MEMORY_RETENTION_DAYS",
        "MAX_MEMORY_ENTRIES",
        "EMBEDDING_DIMENSIONS",
        "SIMILARITY_THRESHOLD",
        "CIRCUIT_BREAKER_THRESHOLD",
        "CIRCUIT_BREAKER_TIMEOUT",
        "MAX_RETRY_ATTEMPTS",
        "RETRY_BACKOFF_BASE",
        "HEALTH_CHECK_INTERVAL",
        "WS_HEARTBEAT_INTERVAL",
        "WS_MAX_CONNECTIONS",
        "WS_MESSAGE_QUEUE_SIZE",
    }

    if name in schema_names:
        from app.core import schemas
        return getattr(schemas, name)

    if name in exception_names:
        from app.core import exceptions
        return getattr(exceptions, name)

    if name in constant_names:
        from app.core import constants
        return getattr(constants, name)

    raise AttributeError(f"module 'app.core' has no attribute '{name}'")


__all__ = [
    # Schemas - Message Types
    "MessageRole",
    "Message",
    "ToolCall",
    "ToolResult",
    # Schemas - Agent State
    "TaskStatus",
    "AgentType",
    "ScratchpadEntry",
    "Task",
    "AgentStateSchema",
    # Schemas - Workflow
    "WorkflowStatus",
    "WorkflowConfig",
    "WorkflowRun",
    # Schemas - API
    "ChatRequest",
    "ChatResponse",
    "HealthStatus",
    "AgentInfo",
    # Schemas - HITL
    "InterventionType",
    "InterventionRequest",
    "InterventionResponse",
    # Exceptions - Base
    "LanglyError",
    # Exceptions - Agent
    "AgentError",
    "AgentNotFoundError",
    "AgentBusyError",
    # Exceptions - Connection
    "OllamaConnectionError",
    "Neo4jConnectionError",
    "ModelNotAvailableError",
    # Exceptions - Workflow
    "WorkflowError",
    "WorkflowTimeoutError",
    "WorkflowNotFoundError",
    "WorkflowStateError",
    "LoopDetectedError",
    # Exceptions - HITL
    "HumanInterventionRequired",
    "InterventionTimeoutError",
    # Exceptions - Tools
    "ToolError",
    "ToolNotFoundError",
    "ToolExecutionError",
    "ToolValidationError",
    # Exceptions - Safety
    "SafetyError",
    # Exceptions - Memory
    "MemoryStoreError",
    "MemoryRetrievalError",
    # Exceptions - Config
    "ConfigurationError",
    # Constants - Workflow
    "DEFAULT_MAX_ITERATIONS",
    "DEFAULT_TIMEOUT_SECONDS",
    "DEFAULT_CHECKPOINT_INTERVAL",
    # Constants - Models
    "GRANITE_MODELS",
    "AGENT_MODEL_MAPPING",
    "MODEL_FALLBACKS",
    # Constants - Agents
    "AGENT_SYSTEM_PROMPTS",
    "NODE_NAMES",
    # Constants - API
    "API_RATE_LIMITS",
    "MAX_MESSAGE_LENGTH",
    "MAX_CONVERSATION_HISTORY",
    # Constants - Safety
    "SAFETY_CHECK_TRIGGERS",
    "BLOCKED_OPERATIONS",
    # Constants - Memory
    "MEMORY_RETENTION_DAYS",
    "MAX_MEMORY_ENTRIES",
    "EMBEDDING_DIMENSIONS",
    "SIMILARITY_THRESHOLD",
    # Constants - Reliability
    "CIRCUIT_BREAKER_THRESHOLD",
    "CIRCUIT_BREAKER_TIMEOUT",
    "MAX_RETRY_ATTEMPTS",
    "RETRY_BACKOFF_BASE",
    "HEALTH_CHECK_INTERVAL",
    # Constants - WebSocket
    "WS_HEARTBEAT_INTERVAL",
    "WS_MAX_CONNECTIONS",
    "WS_MESSAGE_QUEUE_SIZE",
]
