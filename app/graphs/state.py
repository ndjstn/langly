"""
LangGraph AgentState TypedDict definition.

This module defines the state schema used throughout the LangGraph
workflow, including message handling, task tracking, and agent
coordination fields.
"""
import operator
from datetime import datetime
from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from app.core.schemas import AgentType, TaskStatus


class TaskState(TypedDict):
    """Individual task state within the workflow."""

    task_id: str
    description: str
    status: TaskStatus
    assigned_agent: AgentType | None
    created_at: datetime
    completed_at: datetime | None
    result: str | None
    error: str | None


class ScratchpadState(TypedDict, total=False):
    """Agent scratchpad for intermediate reasoning."""

    key: str
    value: Any
    timestamp: datetime


class AgentState(TypedDict):
    """
    Main state schema for the LangGraph workflow.

    This TypedDict defines all fields that flow through the graph,
    including messages, task tracking, iteration control, and
    agent coordination.

    Attributes:
        messages: Conversation history with automatic message merging.
        current_agent: The agent currently processing the request.
        task_status: Overall workflow status.
        scratchpad: Agent working memory for intermediate results.
        pending_tasks: Tasks waiting to be processed.
        completed_tasks: Tasks that have been completed.
        iteration_count: Number of workflow iterations for loop detection.
        error: Current error message if any.
        session_id: Unique identifier for this conversation session.
        thread_id: LangGraph thread identifier for checkpointing.
        requires_human_input: Flag indicating HITL intervention needed.
        human_feedback: Feedback received from human intervention.
        parallel_branches: Active parallel execution branches.
        last_agent_output: Most recent agent response for routing.
        routing_decision: Decision from router agent.
        metadata: Additional context and configuration.
    """

    # Core message handling - uses LangGraph's add_messages reducer
    messages: Annotated[list[BaseMessage], add_messages]

    # Agent coordination
    current_agent: AgentType | None
    task_status: TaskStatus

    # Working memory
    scratchpad: dict[str, Any]

    # Task tracking
    pending_tasks: list[TaskState]
    completed_tasks: list[TaskState]

    # Iteration control for loop detection
    iteration_count: int

    # Error handling
    error: str | None

    # Session management
    session_id: str
    thread_id: str

    # Human-in-the-loop
    requires_human_input: bool
    human_feedback: str | None

    # Parallel execution
    parallel_branches: list[str]

    # Routing and output
    last_agent_output: str | None
    routing_decision: str | None

    # Extensible metadata
    metadata: dict[str, Any]


def create_initial_state(
    session_id: str,
    thread_id: str,
    initial_message: BaseMessage | None = None,
) -> AgentState:
    """
    Create a new initial state for a workflow.

    Args:
        session_id: Unique session identifier.
        thread_id: LangGraph thread identifier.
        initial_message: Optional first message to include.

    Returns:
        AgentState: Initialized state dictionary.
    """
    messages: list[BaseMessage] = []
    if initial_message:
        messages.append(initial_message)

    return AgentState(
        messages=messages,
        current_agent=None,
        task_status=TaskStatus.PENDING,
        scratchpad={},
        pending_tasks=[],
        completed_tasks=[],
        iteration_count=0,
        error=None,
        session_id=session_id,
        thread_id=thread_id,
        requires_human_input=False,
        human_feedback=None,
        parallel_branches=[],
        last_agent_output=None,
        routing_decision=None,
        metadata={},
    )


def increment_iteration(state: AgentState) -> dict[str, int]:
    """
    Return state update to increment iteration count.

    Args:
        state: Current agent state.

    Returns:
        Dict with incremented iteration_count.
    """
    return {"iteration_count": state["iteration_count"] + 1}


def add_pending_task(
    state: AgentState,
    task_id: str,
    description: str,
    assigned_agent: AgentType | None = None,
) -> dict[str, list[TaskState]]:
    """
    Return state update to add a new pending task.

    Args:
        state: Current agent state.
        task_id: Unique task identifier.
        description: Task description.
        assigned_agent: Optional agent to assign.

    Returns:
        Dict with updated pending_tasks list.
    """
    new_task: TaskState = {
        "task_id": task_id,
        "description": description,
        "status": TaskStatus.PENDING,
        "assigned_agent": assigned_agent,
        "created_at": datetime.now(),
        "completed_at": None,
        "result": None,
        "error": None,
    }

    return {"pending_tasks": state["pending_tasks"] + [new_task]}


def complete_task(
    state: AgentState,
    task_id: str,
    result: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """
    Return state update to mark a task as completed.

    Args:
        state: Current agent state.
        task_id: Task identifier to complete.
        result: Optional result of the task.
        error: Optional error if task failed.

    Returns:
        Dict with updated pending and completed task lists.
    """
    completed: list[TaskState] = []
    remaining: list[TaskState] = []

    for task in state["pending_tasks"]:
        if task["task_id"] == task_id:
            completed_task: TaskState = {
                **task,
                "status": TaskStatus.FAILED if error else TaskStatus.COMPLETED,
                "completed_at": datetime.now(),
                "result": result,
                "error": error,
            }
            completed.append(completed_task)
        else:
            remaining.append(task)

    return {
        "pending_tasks": remaining,
        "completed_tasks": state["completed_tasks"] + completed,
    }


def set_requires_human_input(reason: str) -> dict[str, Any]:
    """
    Return state update to flag for human review.

    Args:
        reason: Explanation of why human review is needed.

    Returns:
        Dict with human review flags set.
    """
    return {
        "requires_human_input": True,
        "task_status": TaskStatus.NEEDS_REVIEW,
        "metadata": {"human_review_reason": reason},
    }


def clear_human_input(feedback: str | None = None) -> dict[str, Any]:
    """
    Return state update to clear human review flag.

    Args:
        feedback: Optional feedback from human reviewer.

    Returns:
        Dict clearing human review flags.
    """
    return {
        "requires_human_input": False,
        "human_feedback": feedback,
        "task_status": TaskStatus.IN_PROGRESS,
    }


def set_requires_human_review(reason: str) -> dict[str, Any]:
    """Backward-compatible wrapper for set_requires_human_input."""
    return set_requires_human_input(reason)


def clear_human_review(feedback: str | None = None) -> dict[str, Any]:
    """Backward-compatible wrapper for clear_human_input."""
    return clear_human_input(feedback)
