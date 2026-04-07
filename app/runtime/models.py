"""
Runtime models for Langly v2.

These Pydantic models define the canonical workflow state, messages,
tasks, tool calls, and error records used by the v2 runtime.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Role of a message in the conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class AgentRole(str, Enum):
    """Agent roles for routing and attribution."""

    PM = "pm"
    CODER = "coder"
    ARCHITECT = "architect"
    TESTER = "tester"
    REVIEWER = "reviewer"
    DOCS = "docs"
    ROUTER = "router"
    GUARDIAN = "guardian"


class TaskStatus(str, Enum):
    """Status of a task in the workflow."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class RunStatus(str, Enum):
    """Status of a workflow run."""

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ToolCallStatus(str, Enum):
    """Status of a tool call."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Message(BaseModel):
    """A single message in the conversation."""

    id: UUID = Field(default_factory=uuid4)
    role: MessageRole
    content: str
    name: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    """A tool invocation request and result."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: ToolCallStatus = ToolCallStatus.PENDING
    result: Any | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class Task(BaseModel):
    """A task assigned to a specialist agent."""

    id: UUID = Field(default_factory=uuid4)
    description: str
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent: AgentRole | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    result: Any | None = None
    error: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)


class ErrorRecord(BaseModel):
    """Structured error record for workflow observability."""

    id: UUID = Field(default_factory=uuid4)
    kind: str
    message: str
    retryable: bool = False
    node: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class StateDelta(BaseModel):
    """Atomic state update emitted by a node."""

    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    node: str
    changes: dict[str, Any] = Field(default_factory=dict)
    errors: list[ErrorRecord] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WorkflowState(BaseModel):
    """Canonical workflow state for v2 runtime."""

    session_id: UUID = Field(default_factory=uuid4)
    status: TaskStatus = TaskStatus.PENDING
    current_agent: AgentRole | None = None
    messages: list[Message] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    summary: str | None = None
    scratchpad: dict[str, Any] = Field(default_factory=dict)
    errors: list[ErrorRecord] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class WorkflowRun(BaseModel):
    """Metadata for a workflow execution run."""

    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    status: RunStatus = RunStatus.CREATED
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    result: Any | None = None
    error: str | None = None
