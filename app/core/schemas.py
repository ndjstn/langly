"""
Core Pydantic schemas for the Langly multi-agent platform.

This module defines all shared data models used across the platform,
including message types, agent state, workflow models, and API schemas.
"""
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# =============================================================================
# Message Types
# =============================================================================


class MessageRole(str, Enum):
    """Role of a message in conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Message(BaseModel):
    """A message in the conversation history.

    Attributes:
        id: Unique message identifier.
        role: The role of the message sender.
        content: The message content.
        name: Optional name of the sender (for tool messages).
        timestamp: When the message was created.
        metadata: Optional additional metadata.
    """

    id: UUID = Field(default_factory=uuid4)
    role: MessageRole
    content: str
    name: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    """A tool call request from an agent.

    Attributes:
        id: Unique identifier for this tool call.
        name: Name of the tool to invoke.
        arguments: Arguments to pass to the tool.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Result of a tool execution.

    Attributes:
        tool_call_id: ID of the tool call this result corresponds to.
        result: The result data from the tool.
        error: Error message if the tool failed.
        success: Whether the tool execution succeeded.
    """

    tool_call_id: str
    result: Any = None
    error: str | None = None
    success: bool = True


# =============================================================================
# Task Classification Types
# =============================================================================


class TaskType(str, Enum):
    """Type of task for routing decisions."""

    CODE = "code"
    ARCHITECTURE = "architecture"
    TEST = "test"
    REVIEW = "review"
    DOCUMENTATION = "documentation"
    GENERAL = "general"
    PLANNING = "planning"


class TaskPriority(str, Enum):
    """Priority level for task execution."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# =============================================================================
# Agent State Types
# =============================================================================


class TaskStatus(str, Enum):
    """Status of a task in the workflow."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"
    BLOCKED = "blocked"


class AgentType(str, Enum):
    """Types of agents in the system."""

    PM = "pm"
    CODER = "coder"
    ARCHITECT = "architect"
    TESTER = "tester"
    REVIEWER = "reviewer"
    DOCS = "docs"
    ROUTER = "router"
    GUARDIAN = "guardian"


class ScratchpadEntry(BaseModel):
    """An entry in an agent's scratchpad.

    Attributes:
        key: The key/identifier for this entry.
        value: The stored value.
        timestamp: When this entry was created/updated.
        agent_type: Which agent created this entry.
    """

    key: str
    value: Any
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agent_type: AgentType | None = None


class Task(BaseModel):
    """A task to be processed by an agent.

    Attributes:
        id: Unique task identifier.
        content: Description of the task.
        status: Current status of the task.
        assigned_to: Which agent type is assigned.
        parent_id: ID of parent task if this is a subtask.
        created_at: When the task was created.
        completed_at: When the task was completed.
        result: The result of the task.
        error: Error message if task failed.
    """

    id: UUID = Field(default_factory=uuid4)
    content: str
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: AgentType | None = None
    parent_id: UUID | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    result: Any = None
    error: str | None = None


class AgentStateSchema(BaseModel):
    """Schema for the complete agent workflow state.

    This mirrors the LangGraph AgentState TypedDict but as a
    Pydantic model for validation and serialization.

    Attributes:
        session_id: Unique identifier for this workflow session.
        messages: Conversation history.
        current_agent: Which agent is currently active.
        task_status: Overall workflow status.
        scratchpad: Agent working memory.
        pending_tasks: Tasks waiting to be processed.
        completed_tasks: Tasks that have been processed.
        iteration_count: Number of workflow iterations.
        error: Current error state if any.
        needs_human_input: Whether human intervention is needed.
        human_input_request: Details of what input is needed.
    """

    session_id: UUID = Field(default_factory=uuid4)
    messages: list[Message] = Field(default_factory=list)
    current_agent: AgentType | None = None
    task_status: TaskStatus = TaskStatus.PENDING
    scratchpad: dict[str, ScratchpadEntry] = Field(default_factory=dict)
    pending_tasks: list[Task] = Field(default_factory=list)
    completed_tasks: list[Task] = Field(default_factory=list)
    iteration_count: int = 0
    error: str | None = None
    needs_human_input: bool = False
    human_input_request: str | None = None


# =============================================================================
# Workflow Models
# =============================================================================


class WorkflowStatus(str, Enum):
    """Status of a workflow execution."""

    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_FOR_HUMAN = "waiting_for_human"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowConfig(BaseModel):
    """Configuration for a workflow execution.

    Attributes:
        id: Unique workflow configuration ID.
        max_iterations: Maximum iterations before timeout.
        timeout_seconds: Maximum execution time in seconds.
        enable_human_in_loop: Whether to allow human intervention.
        enable_checkpointing: Whether to checkpoint state.
        parallel_execution: Whether to allow parallel agent execution.
    """

    id: UUID = Field(default_factory=uuid4)
    max_iterations: int = Field(default=50, ge=1, le=500)
    timeout_seconds: int = Field(default=300, ge=10, le=3600)
    enable_human_in_loop: bool = True
    enable_checkpointing: bool = True
    parallel_execution: bool = False


class WorkflowRun(BaseModel):
    """A workflow execution run.

    Attributes:
        id: Unique run identifier.
        config_id: ID of the workflow configuration used.
        status: Current status of the run.
        current_node: The current graph node being executed.
        thread_id: LangGraph thread ID for checkpointing.
        created_at: When the run was started.
        updated_at: When the run was last updated.
        completed_at: When the run completed.
        error: Error message if run failed.
        result: Final result of the run.
    """

    id: UUID = Field(default_factory=uuid4)
    config_id: UUID | None = None
    status: WorkflowStatus = WorkflowStatus.CREATED
    current_node: str | None = None
    thread_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    error: str | None = None
    result: Any = None


# =============================================================================
# API Request/Response Models
# =============================================================================


class ChatRequest(BaseModel):
    """Request to send a chat message.

    Attributes:
        message: The user's message content.
        session_id: Optional existing session to continue.
    """

    message: str = Field(..., min_length=1)
    session_id: UUID | None = None


class ChatResponse(BaseModel):
    """Response from a chat interaction.

    Attributes:
        session_id: The session ID for this conversation.
        message: The agent's response message.
        agent_type: Which agent responded.
        status: Current workflow status.
        tasks: List of tasks created/updated.
    """

    session_id: UUID
    message: str
    agent_type: AgentType
    status: WorkflowStatus
    tasks: list[Task] = Field(default_factory=list)


class HealthStatus(BaseModel):
    """Health check status response.

    Attributes:
        status: Overall health status.
        ollama: Ollama service status.
        neo4j: Neo4j service status.
        version: Application version.
        timestamp: When the check was performed.
    """

    status: str = "healthy"
    ollama: str = "unknown"
    neo4j: str = "unknown"
    version: str = "0.1.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentInfo(BaseModel):
    """Information about an agent.

    Attributes:
        agent_type: The type of agent.
        name: Display name of the agent.
        description: Description of the agent's role.
        model: The LLM model used by this agent.
        status: Current status of the agent.
    """

    agent_type: AgentType
    name: str
    description: str
    model: str
    status: str = "ready"


# =============================================================================
# Intervention Models
# =============================================================================


class InterventionType(str, Enum):
    """Types of human intervention."""

    APPROVAL = "approval"
    CLARIFICATION = "clarification"
    OVERRIDE = "override"
    REDIRECT = "redirect"


class InterventionRequest(BaseModel):
    """A request for human intervention.

    Attributes:
        id: Unique intervention request ID.
        workflow_id: ID of the workflow requesting intervention.
        intervention_type: Type of intervention needed.
        prompt: Message to display to the human.
        options: Available options for the human to choose.
        context: Additional context for the decision.
        created_at: When the request was created.
        timeout_seconds: How long to wait for response.
    """

    id: UUID = Field(default_factory=uuid4)
    workflow_id: UUID
    intervention_type: InterventionType
    prompt: str
    options: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    timeout_seconds: int = Field(default=300, ge=10, le=3600)


class InterventionResponse(BaseModel):
    """A response to an intervention request.

    Attributes:
        request_id: ID of the intervention request.
        response: The human's response.
        selected_option: Which option was selected (if applicable).
        notes: Additional notes from the human.
        responded_at: When the response was provided.
    """

    request_id: UUID
    response: str
    selected_option: str | None = None
    notes: str | None = None
    responded_at: datetime = Field(default_factory=datetime.utcnow)
