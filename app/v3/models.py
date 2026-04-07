"""V3 runtime data contracts."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ToolCallStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    APPROVAL_REQUIRED = "approval_required"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class DeltaKind(str, Enum):
    USER_INPUT = "user_input"
    NODE_START = "node_start"
    NODE_END = "node_end"
    TOOL_CALL = "tool_call"
    APPROVAL = "approval"
    ERROR = "error"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ErrorRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    kind: str
    message: str
    retryable: bool = False
    node_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Message(BaseModel):
    role: MessageRole
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ToolCall(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: ToolCallStatus = ToolCallStatus.PENDING
    result: Any | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Task(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    description: str
    assigned_agent: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    result: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Approval(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    prompt: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: datetime | None = None


class StateDelta(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    node_id: str
    kind: DeltaKind
    changes: dict[str, Any] = Field(default_factory=dict)
    errors: list[ErrorRecord] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Run(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    status: RunStatus = RunStatus.CREATED
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    result: dict[str, Any] | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
