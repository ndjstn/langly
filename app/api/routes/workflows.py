"""
Workflow Endpoints for Langly API.

This module provides endpoints for workflow management including
triggering, status monitoring, and cancellation.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.core.schemas import TaskPriority, TaskType
from app.graphs.workflows import WorkflowManager, get_workflow_manager


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflows", tags=["workflows"])


# =============================================================================
# Request/Response Models
# =============================================================================


class WorkflowStatus(str, Enum):
    """Workflow execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowTriggerRequest(BaseModel):
    """Request to trigger a new workflow."""

    request: str = Field(..., description="User request or task description")
    task_type: TaskType = Field(
        default=TaskType.GENERAL,
        description="Type of task",
    )
    priority: TaskPriority = Field(
        default=TaskPriority.MEDIUM,
        description="Task priority",
    )
    session_id: str | None = Field(
        default=None,
        description="Session ID for context continuity",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )


class WorkflowTriggerResponse(BaseModel):
    """Response after triggering a workflow."""

    workflow_id: str
    status: WorkflowStatus
    message: str
    created_at: str


class WorkflowStatusResponse(BaseModel):
    """Response with workflow status details."""

    workflow_id: str
    status: WorkflowStatus
    current_agent: str | None = None
    iteration: int = 0
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    result: dict[str, Any] | None = None


class WorkflowListResponse(BaseModel):
    """Response with list of workflows."""

    workflows: list[WorkflowStatusResponse]
    total: int
    page: int
    page_size: int


class WorkflowSessionRequest(BaseModel):
    """Request to create a workflow session."""

    name: str = Field(..., min_length=1)


class WorkflowSessionResponse(BaseModel):
    """Response for a workflow session."""

    session_id: str
    name: str


# =============================================================================
# In-memory workflow storage (replace with persistent storage in production)
# =============================================================================

# Temporary in-memory storage for workflow states
_workflow_states: dict[str, dict[str, Any]] = {}


# =============================================================================
# Background task for workflow execution
# =============================================================================


async def run_workflow_async(
    workflow_id: str,
    request: str,
    session_id: str | None,
    task_type: TaskType,
    priority: TaskPriority,
    metadata: dict[str, Any],
) -> None:
    """
    Execute a workflow asynchronously.

    Args:
        workflow_id: Unique workflow identifier.
        request: User request.
        session_id: Session ID for context.
        task_type: Type of task.
        priority: Task priority.
        metadata: Additional metadata.
    """
    try:
        _workflow_states[workflow_id]["status"] = WorkflowStatus.RUNNING
        _workflow_states[workflow_id]["started_at"] = (
            datetime.utcnow().isoformat()
        )

        manager = get_workflow_manager()

        # Execute the workflow
        result = await manager.execute_workflow(
            user_request=request,
            session_id=session_id or workflow_id,
        )

        _workflow_states[workflow_id]["status"] = WorkflowStatus.COMPLETED
        _workflow_states[workflow_id]["completed_at"] = (
            datetime.utcnow().isoformat()
        )
        _workflow_states[workflow_id]["result"] = result

        logger.info(f"Workflow {workflow_id} completed successfully")

    except Exception as e:
        logger.error(f"Workflow {workflow_id} failed: {e}")
        _workflow_states[workflow_id]["status"] = WorkflowStatus.FAILED
        _workflow_states[workflow_id]["error"] = str(e)
        _workflow_states[workflow_id]["completed_at"] = (
            datetime.utcnow().isoformat()
        )


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/", response_model=WorkflowTriggerResponse)
async def trigger_workflow(
    request: WorkflowTriggerRequest,
    background_tasks: BackgroundTasks,
) -> WorkflowTriggerResponse:
    """
    Trigger a new workflow execution.

    This endpoint creates a new workflow and starts it asynchronously.

    Args:
        request: Workflow trigger request.
        background_tasks: FastAPI background tasks handler.

    Returns:
        Workflow trigger response with workflow ID.
    """
    workflow_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()

    # Initialize workflow state
    _workflow_states[workflow_id] = {
        "status": WorkflowStatus.PENDING,
        "current_agent": None,
        "iteration": 0,
        "started_at": None,
        "completed_at": None,
        "error": None,
        "result": None,
        "request": request.request,
        "task_type": request.task_type,
        "priority": request.priority,
        "session_id": request.session_id,
        "metadata": request.metadata,
        "created_at": created_at,
    }

    # Add workflow execution to background tasks
    background_tasks.add_task(
        run_workflow_async,
        workflow_id=workflow_id,
        request=request.request,
        session_id=request.session_id,
        task_type=request.task_type,
        priority=request.priority,
        metadata=request.metadata,
    )

    logger.info(f"Triggered workflow {workflow_id}")

    return WorkflowTriggerResponse(
        workflow_id=workflow_id,
        status=WorkflowStatus.PENDING,
        message="Workflow triggered successfully",
        created_at=created_at,
    )


@router.post("/sessions", response_model=WorkflowSessionResponse)
async def create_session(
    payload: WorkflowSessionRequest,
) -> WorkflowSessionResponse:
    """Create a lightweight workflow session."""
    return WorkflowSessionResponse(
        session_id=str(uuid.uuid4()),
        name=payload.name,
    )


@router.get("/{workflow_id}", response_model=WorkflowStatusResponse)
async def get_workflow_status(workflow_id: str) -> WorkflowStatusResponse:
    """
    Get the status of a specific workflow.

    Args:
        workflow_id: Unique workflow identifier.

    Returns:
        Workflow status details.

    Raises:
        HTTPException: If workflow not found.
    """
    if workflow_id not in _workflow_states:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow {workflow_id} not found",
        )

    state = _workflow_states[workflow_id]

    return WorkflowStatusResponse(
        workflow_id=workflow_id,
        status=state["status"],
        current_agent=state.get("current_agent"),
        iteration=state.get("iteration", 0),
        started_at=state.get("started_at"),
        completed_at=state.get("completed_at"),
        error=state.get("error"),
        result=state.get("result"),
    )


@router.get("/", response_model=WorkflowListResponse)
async def list_workflows(
    page: int = 1,
    page_size: int = 20,
    status: WorkflowStatus | None = None,
) -> WorkflowListResponse:
    """
    List all workflows with optional filtering.

    Args:
        page: Page number (1-indexed).
        page_size: Number of items per page.
        status: Filter by status.

    Returns:
        Paginated list of workflows.
    """
    # Filter workflows by status if provided
    workflows = []
    for wf_id, state in _workflow_states.items():
        if status is None or state["status"] == status:
            workflows.append(
                WorkflowStatusResponse(
                    workflow_id=wf_id,
                    status=state["status"],
                    current_agent=state.get("current_agent"),
                    iteration=state.get("iteration", 0),
                    started_at=state.get("started_at"),
                    completed_at=state.get("completed_at"),
                    error=state.get("error"),
                    result=state.get("result"),
                )
            )

    # Sort by creation time (most recent first)
    workflows.sort(
        key=lambda w: _workflow_states.get(w.workflow_id, {}).get(
            "created_at", ""
        ),
        reverse=True,
    )

    # Paginate
    total = len(workflows)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated = workflows[start_idx:end_idx]

    return WorkflowListResponse(
        workflows=paginated,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str) -> dict[str, str]:
    """
    Cancel a running workflow.

    Args:
        workflow_id: Unique workflow identifier.

    Returns:
        Cancellation confirmation.

    Raises:
        HTTPException: If workflow not found or cannot be cancelled.
    """
    if workflow_id not in _workflow_states:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow {workflow_id} not found",
        )

    state = _workflow_states[workflow_id]

    if state["status"] in [
        WorkflowStatus.COMPLETED,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
    ]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel workflow in {state['status']} state",
        )

    # Mark as cancelled
    _workflow_states[workflow_id]["status"] = WorkflowStatus.CANCELLED
    _workflow_states[workflow_id]["completed_at"] = (
        datetime.utcnow().isoformat()
    )

    logger.info(f"Cancelled workflow {workflow_id}")

    return {
        "workflow_id": workflow_id,
        "status": "cancelled",
        "message": "Workflow cancelled successfully",
    }


@router.get("/{workflow_id}/history")
async def get_workflow_history(
    workflow_id: str,
) -> dict[str, Any]:
    """
    Get the execution history of a workflow.

    Args:
        workflow_id: Unique workflow identifier.

    Returns:
        Workflow execution history.

    Raises:
        HTTPException: If workflow not found.
    """
    if workflow_id not in _workflow_states:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow {workflow_id} not found",
        )

    state = _workflow_states[workflow_id]

    # Return complete state history
    return {
        "workflow_id": workflow_id,
        "request": state.get("request"),
        "task_type": state.get("task_type"),
        "priority": state.get("priority"),
        "status": state["status"],
        "created_at": state.get("created_at"),
        "started_at": state.get("started_at"),
        "completed_at": state.get("completed_at"),
        "iterations": state.get("iteration", 0),
        "result": state.get("result"),
        "error": state.get("error"),
        "metadata": state.get("metadata", {}),
    }


@router.post("/{workflow_id}/retry")
async def retry_workflow(
    workflow_id: str,
    background_tasks: BackgroundTasks,
) -> WorkflowTriggerResponse:
    """
    Retry a failed workflow.

    Args:
        workflow_id: Unique workflow identifier.
        background_tasks: FastAPI background tasks handler.

    Returns:
        New workflow trigger response.

    Raises:
        HTTPException: If workflow not found or not in failed state.
    """
    if workflow_id not in _workflow_states:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow {workflow_id} not found",
        )

    state = _workflow_states[workflow_id]

    if state["status"] != WorkflowStatus.FAILED:
        raise HTTPException(
            status_code=400,
            detail="Can only retry failed workflows",
        )

    # Create a new workflow with same parameters
    new_workflow_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()

    _workflow_states[new_workflow_id] = {
        "status": WorkflowStatus.PENDING,
        "current_agent": None,
        "iteration": 0,
        "started_at": None,
        "completed_at": None,
        "error": None,
        "result": None,
        "request": state["request"],
        "task_type": state["task_type"],
        "priority": state["priority"],
        "session_id": state.get("session_id"),
        "metadata": {
            **state.get("metadata", {}),
            "retry_of": workflow_id,
        },
        "created_at": created_at,
    }

    background_tasks.add_task(
        run_workflow_async,
        workflow_id=new_workflow_id,
        request=state["request"],
        session_id=state.get("session_id"),
        task_type=state["task_type"],
        priority=state["priority"],
        metadata=state.get("metadata", {}),
    )

    logger.info(f"Retrying workflow {workflow_id} as {new_workflow_id}")

    return WorkflowTriggerResponse(
        workflow_id=new_workflow_id,
        status=WorkflowStatus.PENDING,
        message=f"Workflow retry triggered (original: {workflow_id})",
        created_at=created_at,
    )
