e """
Constants and configuration values for the Langly platform.

This module defines all constant values used throughout the application,
including default configurations, model mappings, and agent prompts.
"""
from typing import Any

# =============================================================================
# Workflow Defaults
# =============================================================================

DEFAULT_MAX_ITERATIONS: int = 50
"""Maximum number of workflow iterations before timeout."""

DEFAULT_TIMEOUT_SECONDS: int = 300
"""Default operation timeout in seconds (5 minutes)."""

DEFAULT_CHECKPOINT_INTERVAL: int = 5
"""Number of iterations between automatic checkpoints."""

# =============================================================================
# IBM Granite Model Mappings
# =============================================================================

GRANITE_MODELS: dict[str, str] = {
    # Dense models - Strong function calling and code generation
    "dense_8b": "granite3.1-dense:8b",
    "dense_2b": "granite3.1-dense:2b",

    # MoE models - Low-latency routing decisions
    "moe_3b": "granite3.1-moe:3b",
    "moe_1b": "granite3.1-moe:1b",

    # Code models - Specialized code tasks
    "code_8b": "granite-code:8b",
    "code_3b": "granite-code:3b",

    # Embedding model - Semantic memory and retrieval
    "embedding": "granite-embedding:278m",

    # Guardian model - Safety validation
    "guardian": "granite-guardian:8b",
}
"""Mapping of model keys to Ollama model names."""

# Default model for each role
AGENT_MODEL_MAPPING: dict[str, str] = {
    "pm": "dense_8b",
    "coder": "code_8b",
    "architect": "dense_8b",
    "tester": "code_3b",
    "reviewer": "dense_8b",
    "docs": "dense_2b",
    "router": "moe_1b",
    "guardian": "guardian",
}
"""Mapping of agent types to their preferred model keys."""

# Fallback model chain for each primary model
MODEL_FALLBACKS: dict[str, list[str]] = {
    "dense_8b": ["dense_2b", "moe_3b"],
    "dense_2b": ["moe_3b", "moe_1b"],
    "moe_3b": ["moe_1b", "dense_2b"],
    "moe_1b": ["moe_3b", "dense_2b"],
    "code_8b": ["code_3b", "dense_8b"],
    "code_3b": ["dense_2b", "moe_3b"],
    "guardian": ["dense_8b", "dense_2b"],
    "embedding": [],  # No fallback for embeddings
}
"""Fallback chain for each model when primary is unavailable."""

# =============================================================================
# Agent System Prompts
# =============================================================================

AGENT_SYSTEM_PROMPTS: dict[str, str] = {
    "pm": """You are the Project Manager agent in a multi-agent coding system.
Your role is to:
1. Understand the user's high-level requirements and goals
2. Break down complex requests into actionable subtasks
3. Delegate tasks to appropriate specialist agents
4. Coordinate work between agents and track progress
5. Aggregate results and present coherent responses to the user

You communicate with the user as a business-focused PM, not as a developer.
When you need code written, testing done, or documentation created,
delegate to the appropriate specialist agent.

Always be clear about what work is being done and by whom.""",

    "coder": """You are the Coder agent in a multi-agent coding system.
Your role is to:
1. Write clean, production-ready code following best practices
2. Implement features based on specifications from the PM
3. Fix bugs and refactor code when requested
4. Follow project coding standards and conventions
5. Provide clear comments and documentation in code

You produce high-quality Python code that follows PEP 8, uses type hints,
includes docstrings, and handles errors appropriately. When unsure about
requirements, ask clarifying questions through the PM.""",

    "architect": """You are the Architect agent in a multi-agent coding system.
Your role is to:
1. Design system architecture and component relationships
2. Make technology and framework decisions
3. Define data models and API contracts
4. Ensure scalability, maintainability, and security
5. Review designs for potential issues before implementation

You think strategically about the big picture while ensuring
technical decisions support long-term project health.""",

    "tester": """You are the Tester agent in a multi-agent coding system.
Your role is to:
1. Write comprehensive unit and integration tests
2. Identify edge cases and potential failure modes
3. Verify code correctness and behavior
4. Report bugs with clear reproduction steps
5. Suggest improvements based on testing findings

You use pytest and follow testing best practices. Aim for high coverage
and focus on testing behavior, not implementation details.""",

    "reviewer": """You are the Code Reviewer agent in a multi-agent coding system.
Your role is to:
1. Review code for quality, correctness, and best practices
2. Identify potential bugs, security issues, and performance problems
3. Ensure code follows project standards and conventions
4. Provide constructive feedback with specific suggestions
5. Approve or request changes based on review findings

You review code thoroughly but constructively, focusing on
improvements rather than criticism.""",

    "docs": """You are the Documentation agent in a multi-agent coding system.
Your role is to:
1. Write clear, comprehensive documentation
2. Create API references and usage guides
3. Document design decisions and architecture
4. Maintain README files and contribution guides
5. Ensure documentation stays in sync with code

You write documentation that is helpful for both users and developers,
with clear examples and well-organized structure.""",

    "router": """You are the Router agent in a multi-agent coding system.
Your role is to:
1. Analyze incoming requests to determine the appropriate handling
2. Route tasks to the correct specialist agent
3. Identify when multiple agents are needed
4. Recognize when human intervention is required
5. Handle meta-queries about the system itself

You make quick, accurate routing decisions based on the content
and context of each request.""",
}
"""System prompts for each agent type."""

# =============================================================================
# Node Names
# =============================================================================

NODE_NAMES: dict[str, str] = {
    "router": "router_node",
    "pm": "pm_node",
    "coder": "coder_node",
    "architect": "architect_node",
    "tester": "tester_node",
    "reviewer": "reviewer_node",
    "docs": "docs_node",
    "supervisor": "supervisor_node",
    "human": "human_node",
}
"""Mapping of agent types to graph node names."""

# =============================================================================
# API Configuration
# =============================================================================

API_RATE_LIMITS: dict[str, str] = {
    "default": "100/minute",
    "chat": "30/minute",
    "workflow": "10/minute",
    "search": "50/minute",
}
"""Rate limits for different API endpoint categories."""

MAX_MESSAGE_LENGTH: int = 50000
"""Maximum length of a single message in characters."""

MAX_CONVERSATION_HISTORY: int = 100
"""Maximum number of messages to keep in active conversation context."""

# =============================================================================
# Safety Configuration
# =============================================================================

SAFETY_CHECK_TRIGGERS: list[str] = [
    "execute",
    "delete",
    "remove",
    "drop",
    "shell",
    "system",
    "sudo",
    "admin",
]
"""Keywords that trigger additional safety validation."""

BLOCKED_OPERATIONS: list[str] = [
    "rm -rf /",
    "format c:",
    "drop database",
    "; DROP TABLE",
]
"""Operations that should never be executed."""

# =============================================================================
# Memory Configuration
# =============================================================================

MEMORY_RETENTION_DAYS: int = 30
"""Number of days to retain conversation history."""

MAX_MEMORY_ENTRIES: int = 10000
"""Maximum number of entries in the project knowledge base."""

EMBEDDING_DIMENSIONS: int = 768
"""Dimensionality of Granite embedding vectors."""

SIMILARITY_THRESHOLD: float = 0.7
"""Minimum similarity score for memory retrieval."""

# =============================================================================
# Reliability Configuration
# =============================================================================

CIRCUIT_BREAKER_THRESHOLD: int = 5
"""Number of failures before circuit breaker opens."""

CIRCUIT_BREAKER_TIMEOUT: int = 60
"""Seconds before circuit breaker allows retry."""

MAX_RETRY_ATTEMPTS: int = 3
"""Maximum number of retry attempts for transient failures."""

# Alias for compatibility
DEFAULT_RETRY_ATTEMPTS: int = MAX_RETRY_ATTEMPTS
"""Alias for MAX_RETRY_ATTEMPTS for backward compatibility."""

RETRY_BACKOFF_BASE: float = 2.0
"""Base for exponential backoff between retries."""

DEFAULT_RETRY_MIN_WAIT: float = 1.0
"""Minimum wait time in seconds between retries."""

DEFAULT_RETRY_MAX_WAIT: float = 10.0
"""Maximum wait time in seconds between retries."""

HEALTH_CHECK_INTERVAL: int = 30
"""Seconds between health check runs."""

# =============================================================================
# WebSocket Configuration
# =============================================================================

WS_HEARTBEAT_INTERVAL: int = 30
"""Seconds between WebSocket heartbeat messages."""

WS_MAX_CONNECTIONS: int = 100
"""Maximum concurrent WebSocket connections."""

WS_MESSAGE_QUEUE_SIZE: int = 1000
"""Maximum messages in WebSocket broadcast queue."""
