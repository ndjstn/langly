"""
Workflow Graph Module.

This module defines and compiles the LangGraph StateGraph workflow,
connecting all agent nodes with appropriate edges and conditional routing.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graphs.edges import (
    route_after_aggregation,
    route_after_entry,
    route_after_error,
    route_after_human,
    route_after_pm,
    route_after_specialist,
    route_to_specialist,
)
from app.graphs.state import AgentState

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver

    from app.graphs.nodes import NodeFactory


logger = logging.getLogger(__name__)


# Type alias for async node functions
AsyncNodeFunc = Callable[[AgentState], Awaitable[dict[str, Any]]]


class WorkflowBuilder:
    """
    Builder class for constructing the multi-agent workflow graph.

    This class encapsulates the logic for building a LangGraph StateGraph
    with all necessary nodes, edges, and conditional routing.
    """

    def __init__(
        self,
        node_factory: NodeFactory,
        checkpointer: BaseCheckpointSaver[Any] | None = None,
    ) -> None:
        """
        Initialize the workflow builder.

        Args:
            node_factory: Factory for creating agent nodes.
            checkpointer: Optional checkpointer for state persistence.
        """
        self._node_factory = node_factory
        self._checkpointer = checkpointer
        self._graph: StateGraph[AgentState] | None = None

    def build(self) -> CompiledStateGraph[AgentState]:
        """
        Build and compile the complete workflow graph.

        Returns:
            The compiled LangGraph workflow.
        """
        logger.info("Building workflow graph...")

        # Create the StateGraph
        self._graph = StateGraph(AgentState)

        # Add all nodes
        self._add_nodes()

        # Add all edges
        self._add_edges()

        # Set entry point
        self._graph.set_entry_point("entry_node")

        # Compile with optional checkpointer
        compiled: CompiledStateGraph[AgentState] = self._graph.compile(
            checkpointer=self._checkpointer
        )

        logger.info("Workflow graph compiled successfully")
        return compiled

    def _add_nodes(self) -> None:
        """Add all agent nodes to the graph."""
        if self._graph is None:
            raise RuntimeError("Graph not initialized")

        # Entry node - initial request processing
        self._graph.add_node(
            "entry_node",
            self._node_factory.create_entry_node(),
        )

        # PM Agent node - project management and task delegation
        self._graph.add_node(
            "pm_node",
            self._node_factory.create_pm_node(),
        )

        # Router node - determines which specialist to invoke
        self._graph.add_node(
            "router_node",
            self._node_factory.create_router_node(),
        )

        # Specialist agent nodes
        self._graph.add_node(
            "coder_node",
            self._node_factory.create_coder_node(),
        )

        self._graph.add_node(
            "architect_node",
            self._node_factory.create_architect_node(),
        )

        self._graph.add_node(
            "tester_node",
            self._node_factory.create_tester_node(),
        )

        self._graph.add_node(
            "reviewer_node",
            self._node_factory.create_reviewer_node(),
        )

        self._graph.add_node(
            "docs_node",
            self._node_factory.create_docs_node(),
        )

        # Aggregation node - collects and processes results
        self._graph.add_node(
            "aggregation_node",
            self._create_aggregation_node(),
        )

        # Completion node - finalizes the workflow
        self._graph.add_node(
            "completion_node",
            self._create_completion_node(),
        )

        # Error handler node
        self._graph.add_node(
            "error_handler_node",
            self._create_error_handler_node(),
        )

        # Human intervention node
        self._graph.add_node(
            "human_intervention_node",
            self._create_human_intervention_node(),
        )

        logger.debug("Added all nodes to workflow graph")

    def _add_edges(self) -> None:
        """Add all edges and conditional routing to the graph."""
        if self._graph is None:
            raise RuntimeError("Graph not initialized")

        # Entry node routing
        self._graph.add_conditional_edges(
            "entry_node",
            route_after_entry,
            {
                "pm_node": "pm_node",
                "error_handler_node": "error_handler_node",
            },
        )

        # PM node routing
        self._graph.add_conditional_edges(
            "pm_node",
            route_after_pm,
            {
                "router_node": "router_node",
                "aggregation_node": "aggregation_node",
                "completion_node": "completion_node",
                "human_intervention_node": "human_intervention_node",
                "error_handler_node": "error_handler_node",
            },
        )

        # Router node routing to specialists
        self._graph.add_conditional_edges(
            "router_node",
            route_to_specialist,
            {
                "pm_node": "pm_node",
                "coder_node": "coder_node",
                "architect_node": "architect_node",
                "tester_node": "tester_node",
                "reviewer_node": "reviewer_node",
                "docs_node": "docs_node",
            },
        )

        # Specialist nodes routing (all follow same pattern)
        for specialist in [
            "coder_node",
            "architect_node",
            "tester_node",
            "reviewer_node",
            "docs_node",
        ]:
            self._graph.add_conditional_edges(
                specialist,
                route_after_specialist,
                {
                    "router_node": "router_node",
                    "aggregation_node": "aggregation_node",
                    "human_intervention_node": "human_intervention_node",
                    "error_handler_node": "error_handler_node",
                },
            )

        # Aggregation node routing
        self._graph.add_conditional_edges(
            "aggregation_node",
            route_after_aggregation,
            {
                "router_node": "router_node",
                "pm_node": "pm_node",
                "completion_node": "completion_node",
            },
        )

        # Error handler routing
        self._graph.add_conditional_edges(
            "error_handler_node",
            route_after_error,
            {
                "pm_node": "pm_node",
                "coder_node": "coder_node",
                "architect_node": "architect_node",
                "tester_node": "tester_node",
                "reviewer_node": "reviewer_node",
                "docs_node": "docs_node",
                "router_node": "router_node",
                "human_intervention_node": "human_intervention_node",
                "completion_node": "completion_node",
            },
        )

        # Human intervention routing
        self._graph.add_conditional_edges(
            "human_intervention_node",
            route_after_human,
            {
                "pm_node": "pm_node",
                "coder_node": "coder_node",
                "architect_node": "architect_node",
                "tester_node": "tester_node",
                "reviewer_node": "reviewer_node",
                "docs_node": "docs_node",
                "router_node": "router_node",
                "completion_node": "completion_node",
            },
        )

        # Completion node goes to END
        self._graph.add_edge("completion_node", END)

        logger.debug("Added all edges to workflow graph")

    def _create_aggregation_node(self) -> AsyncNodeFunc:
        """
        Create the aggregation node function.

        Returns:
            Node function for aggregating specialist results.
        """

        async def aggregation_node(state: AgentState) -> dict[str, Any]:
            """Aggregate results from specialist agents."""
            logger.info("Aggregation node processing...")

            completed_tasks = state.get("completed_tasks", [])
            specialist_outputs = state.get("specialist_outputs", {})

            # Combine all specialist outputs
            aggregated_result = {
                "completed_count": len(completed_tasks)
                if completed_tasks
                else 0,
                "outputs": specialist_outputs if specialist_outputs else {},
            }

            # Check if PM needs to synthesize
            needs_synthesis = (
                len(completed_tasks) > 1 if completed_tasks else False
            )

            return {
                "aggregated_result": aggregated_result,
                "needs_pm_synthesis": needs_synthesis,
                "iteration_count": (state.get("iteration_count") or 0) + 1,
            }

        return aggregation_node

    def _create_completion_node(self) -> AsyncNodeFunc:
        """
        Create the completion node function.

        Returns:
            Node function for finalizing the workflow.
        """

        async def completion_node(state: AgentState) -> dict[str, Any]:
            """Finalize the workflow and prepare the response."""
            logger.info("Completion node finalizing workflow...")

            # Mark workflow as completed
            return {
                "workflow_completed": True,
            }

        return completion_node

    def _create_error_handler_node(self) -> AsyncNodeFunc:
        """
        Create the error handler node function.

        Returns:
            Node function for handling errors.
        """

        async def error_handler_node(state: AgentState) -> dict[str, Any]:
            """Handle errors and determine recovery strategy."""
            logger.info("Error handler node processing...")

            error = state.get("error")
            error_count = (state.get("error_count") or 0) + 1
            retry_count = state.get("retry_count") or 0
            error_log: list[dict[str, Any]] = list(
                state.get("error_log") or []
            )

            # Log the error
            if error:
                error_log.append({
                    "error": str(error),
                    "count": error_count,
                })

            # Determine if we should retry or escalate
            max_retries = 3
            if isinstance(retry_count, int) and retry_count < max_retries:
                logger.warning(
                    f"Error occurred, retry {retry_count + 1}/{max_retries}"
                )
                return {
                    "error": None,
                    "error_count": error_count,
                    "retry_count": retry_count + 1,
                    "error_log": error_log,
                }
            else:
                # Escalate to human
                logger.error(
                    "Max retries exceeded, escalating to human intervention"
                )
                return {
                    "error": None,
                    "error_count": error_count,
                    "requires_human_input": True,
                    "error_log": error_log,
                }

        return error_handler_node

    def _create_human_intervention_node(self) -> AsyncNodeFunc:
        """
        Create the human intervention node function.

        Returns:
            Node function for human-in-the-loop processing.
        """

        async def human_intervention_node(state: AgentState) -> dict[str, Any]:
            """
            Handle human intervention requests.

            This node pauses execution and waits for human input.
            The actual human input handling is done externally via
            the checkpoint/interrupt mechanism.
            """
            logger.info("Human intervention node - awaiting input...")

            # This node primarily marks the state for human review
            # The actual input is provided via graph.update_state()
            return {
                "requires_human_input": False,
                "human_action": state.get("human_action") or "continue",
            }

        return human_intervention_node


def build_workflow(
    node_factory: NodeFactory,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledStateGraph[AgentState]:
    """
    Build the complete multi-agent workflow.

    This is a convenience function that creates a WorkflowBuilder
    and builds the workflow graph.

    Args:
        node_factory: Factory for creating agent nodes.
        checkpointer: Optional checkpointer for state persistence.

    Returns:
        The compiled LangGraph workflow.
    """
    builder = WorkflowBuilder(
        node_factory=node_factory,
        checkpointer=checkpointer,
    )
    return builder.build()


def create_simple_workflow(
    node_factory: NodeFactory,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledStateGraph[AgentState]:
    """
    Create a simplified workflow for testing.

    This creates a minimal workflow with just PM and one specialist
    for easier testing and debugging.

    Args:
        node_factory: Factory for creating agent nodes.
        checkpointer: Optional checkpointer for state persistence.

    Returns:
        The compiled simplified workflow.
    """
    logger.info("Building simplified workflow graph...")

    graph: StateGraph[AgentState] = StateGraph(AgentState)

    # Add minimal nodes
    graph.add_node("entry_node", node_factory.create_entry_node())
    graph.add_node("pm_node", node_factory.create_pm_node())
    graph.add_node("coder_node", node_factory.create_coder_node())

    # Simple linear flow for testing
    graph.set_entry_point("entry_node")
    graph.add_edge("entry_node", "pm_node")
    graph.add_edge("pm_node", "coder_node")
    graph.add_edge("coder_node", END)

    compiled: CompiledStateGraph[AgentState] = graph.compile(
        checkpointer=checkpointer
    )
    logger.info("Simplified workflow compiled successfully")

    return compiled


# =============================================================================
# Workflow Manager for API Integration
# =============================================================================


class WorkflowManager:
    """
    High-level manager for workflow execution.

    This class provides a simplified interface for executing workflows
    from the API layer, handling initialization, execution, and cleanup.
    """

    _instance: WorkflowManager | None = None
    _workflow: CompiledStateGraph[AgentState] | None = None

    def __init__(self) -> None:
        """Initialize the workflow manager."""
        self._initialized = False

    @classmethod
    def get_instance(cls) -> WorkflowManager:
        """
        Get the singleton instance of WorkflowManager.

        Returns:
            The WorkflowManager singleton instance.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize(self) -> None:
        """
        Initialize the workflow manager and compile the workflow graph.

        This should be called during application startup.
        """
        if self._initialized:
            return

        logger.info("Initializing WorkflowManager...")

        # Import here to avoid circular imports
        from app.graphs.checkpointer import create_checkpointer
        from app.graphs.nodes import NodeFactory
        from app.llm.provider import get_llm_for_agent
        from app.core.schemas import AgentType

        try:
            # Create node factory with per-agent model selection
            def llm_provider(agent_type: AgentType) -> Any:
                return get_llm_for_agent(agent_type.value)

            node_factory = NodeFactory(
                llm_provider=llm_provider,
                moe_llm_provider=llm_provider,
            )

            # Create checkpointer
            checkpointer = create_checkpointer()

            # Build the workflow
            self._workflow = build_workflow(
                node_factory=node_factory,
                checkpointer=checkpointer,
            )

            self._initialized = True
            logger.info("WorkflowManager initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize WorkflowManager: {e}")
            raise

    async def execute_workflow(
        self,
        user_request: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute a workflow with the given user request.

        Args:
            user_request: The user's request/message.
            session_id: Optional session ID for continuity.

        Returns:
            The workflow result as a dictionary.

        Raises:
            RuntimeError: If the workflow manager is not initialized.
        """
        if not self._initialized or self._workflow is None:
            await self.initialize()

        if self._workflow is None:
            raise RuntimeError("Workflow not initialized")

        logger.info(f"Executing workflow for session: {session_id}")

        # Build initial state
        from langchain_core.messages import HumanMessage

        initial_state: AgentState = {
            "messages": [HumanMessage(content=user_request)],
            "session_id": session_id or "",
            "current_agent": None,
            "pending_tasks": [],
            "completed_tasks": [],
            "specialist_outputs": {},
            "aggregated_result": None,
            "iteration_count": 0,
            "error": None,
            "error_count": 0,
            "retry_count": 0,
            "error_log": [],
            "requires_human_input": False,
            "human_action": None,
            "workflow_completed": False,
            "needs_pm_synthesis": False,
        }

        # Execute the workflow
        config = {"configurable": {"thread_id": session_id or "default"}}

        try:
            result = await self._workflow.ainvoke(initial_state, config)
            logger.info(f"Workflow completed for session: {session_id}")
            return dict(result) if result else {}

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            raise

    def is_initialized(self) -> bool:
        """Check if the workflow manager is initialized."""
        return self._initialized


def get_workflow_manager() -> WorkflowManager:
    """
    Get the singleton WorkflowManager instance.

    Returns:
        The WorkflowManager singleton instance.
    """
    return WorkflowManager.get_instance()
