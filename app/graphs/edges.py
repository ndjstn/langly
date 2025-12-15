"""
Graph Edges Module.

This module defines conditional edge functions for the LangGraph StateGraph
workflow. These functions determine transitions between nodes based on
the current state.
"""
from __future__ import annotations

import logging
from typing import Literal

from app.core.constants import DEFAULT_MAX_ITERATIONS
from app.core.schemas import AgentType, TaskStatus
from app.graphs.state import AgentState

logger = logging.getLogger(__name__)


# Type aliases for routing
RouteDecision = Literal[
    "pm_node",
    "coder_node",
    "architect_node",
    "tester_node",
    "reviewer_node",
    "docs_node",
    "router_node",
    "aggregation_node",
    "completion_node",
    "human_intervention_node",
    "error_handler_node",
    "END",
]


def should_continue(state: AgentState) -> bool:
    """
    Determine if the workflow should continue processing.

    Args:
        state: The current workflow state.

    Returns:
        True if workflow should continue, False otherwise.
    """
    # Check for workflow completion
    if state.get("workflow_completed"):
        return False

    # Check for terminal task status
    task_status = state.get("task_status")
    if task_status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
        if not state.get("pending_tasks"):
            return False

    # Check iteration limit
    iteration_count = state.get("iteration_count", 0)
    if iteration_count >= DEFAULT_MAX_ITERATIONS:
        logger.warning(f"Max iterations ({DEFAULT_MAX_ITERATIONS}) reached")
        return False

    # Check for human intervention requirement
    if state.get("requires_human_input"):
        return False

    return True


def route_after_entry(state: AgentState) -> RouteDecision:
    """
    Route after the entry node.

    Determines whether to go to PM or router based on state.

    Args:
        state: The current workflow state.

    Returns:
        The next node to execute.
    """
    # If there's an error, go to error handler
    if state.get("error"):
        return "error_handler_node"

    # Go to PM for initial request handling
    return "pm_node"


def route_after_pm(state: AgentState) -> RouteDecision:
    """
    Route after the PM node processes.

    Determines whether to:
    - Route to specialist agents
    - Complete the workflow
    - Go to aggregation

    Args:
        state: The current workflow state.

    Returns:
        The next node to execute.
    """
    # Check for errors
    if state.get("error"):
        return "error_handler_node"

    # Check for human intervention
    if state.get("requires_human_input"):
        return "human_intervention_node"

    # Check for pending tasks
    pending = state.get("pending_tasks", [])
    if pending:
        # Use router to determine which agent to invoke
        return "router_node"

    # Check if there are completed tasks to synthesize
    completed = state.get("completed_tasks", [])
    needs_synthesis = state.get("needs_pm_synthesis")
    if completed and needs_synthesis:
        # PM has synthesized, complete
        return "completion_node"

    # If we need aggregation
    if completed:
        return "aggregation_node"

    # Default to completion
    return "completion_node"


def route_to_specialist(state: AgentState) -> RouteDecision:
    """
    Route to the appropriate specialist agent based on routing decision.

    Args:
        state: The current workflow state.

    Returns:
        The next node to execute.
    """
    routing_decision = state.get("routing_decision") or "pm"

    # Map routing decision to node names
    route_map: dict[str, RouteDecision] = {
        "pm": "pm_node",
        "coder": "coder_node",
        "architect": "architect_node",
        "tester": "tester_node",
        "reviewer": "reviewer_node",
        "docs": "docs_node",
    }

    node: RouteDecision = route_map.get(routing_decision, "pm_node")
    logger.info(f"Routing to specialist: {node}")
    return node


def route_after_specialist(state: AgentState) -> RouteDecision:
    """
    Route after a specialist agent completes.

    Args:
        state: The current workflow state.

    Returns:
        The next node to execute.
    """
    # Check for errors
    if state.get("error"):
        return "error_handler_node"

    # Check for human intervention
    if state.get("requires_human_input"):
        return "human_intervention_node"

    # Check for more pending tasks
    pending = state.get("pending_tasks", [])
    if pending:
        # Route to next specialist
        return "router_node"

    # All tasks done, go to aggregation
    return "aggregation_node"


def route_after_aggregation(state: AgentState) -> RouteDecision:
    """
    Route after aggregation completes.

    Args:
        state: The current workflow state.

    Returns:
        The next node to execute.
    """
    # Check if there are still pending tasks
    pending = state.get("pending_tasks", [])
    if pending:
        return "router_node"

    # If PM needs to synthesize results
    if state.get("needs_pm_synthesis"):
        return "pm_node"

    return "completion_node"


def route_after_error(state: AgentState) -> RouteDecision:
    """
    Route after error handling.

    Args:
        state: The current workflow state.

    Returns:
        The next node to execute.
    """
    # If human intervention needed
    if state.get("requires_human_input"):
        return "human_intervention_node"

    # Check if we should retry
    if state.get("task_status") == TaskStatus.IN_PROGRESS:
        # Retry - determine where to go
        current_agent = state.get("current_agent")
        if current_agent:
            agent_to_node: dict[AgentType, RouteDecision] = {
                AgentType.PM: "pm_node",
                AgentType.CODER: "coder_node",
                AgentType.ARCHITECT: "architect_node",
                AgentType.TESTER: "tester_node",
                AgentType.REVIEWER: "reviewer_node",
                AgentType.DOCS: "docs_node",
                AgentType.ROUTER: "router_node",
            }
            return agent_to_node.get(current_agent, "pm_node")
        return "pm_node"

    # Failed, complete workflow
    return "completion_node"


def route_after_human(state: AgentState) -> RouteDecision:
    """
    Route after human intervention.

    Args:
        state: The current workflow state.

    Returns:
        The next node to execute.
    """
    # Human has provided input, check what to do next
    human_action = state.get("human_action", "continue")

    if human_action == "abort":
        return "completion_node"

    if human_action == "retry":
        # Retry current operation
        current_agent = state.get("current_agent")
        if current_agent:
            agent_to_node: dict[AgentType, RouteDecision] = {
                AgentType.PM: "pm_node",
                AgentType.CODER: "coder_node",
                AgentType.ARCHITECT: "architect_node",
                AgentType.TESTER: "tester_node",
                AgentType.REVIEWER: "reviewer_node",
                AgentType.DOCS: "docs_node",
            }
            return agent_to_node.get(current_agent, "pm_node")

    # Default: continue with normal flow
    pending = state.get("pending_tasks", [])
    if pending:
        return "router_node"

    return "pm_node"


def check_loop_detection(state: AgentState) -> bool:
    """
    Check for potential infinite loops in the workflow.

    Args:
        state: The current workflow state.

    Returns:
        True if a loop is detected, False otherwise.
    """
    iteration_count = state.get("iteration_count", 0)

    # Check if iteration count is suspiciously high
    if iteration_count > DEFAULT_MAX_ITERATIONS / 2:
        # Check for repeating patterns
        messages = state.get("messages", [])
        if len(messages) >= 10:
            # Simple pattern detection: check if last 5 messages repeat
            last_5 = [str(m)[:100] for m in messages[-5:]]
            prev_5 = [str(m)[:100] for m in messages[-10:-5]]
            if last_5 == prev_5:
                logger.warning("Loop detected: repeating message pattern")
                return True

    return False


def create_conditional_entry(
    state: AgentState,
) -> Literal["continue", "end"]:
    """
    Conditional entry point for the workflow.

    Args:
        state: The current workflow state.

    Returns:
        "continue" or "end".
    """
    if should_continue(state) and not check_loop_detection(state):
        return "continue"
    return "end"
