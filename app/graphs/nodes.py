"""
Graph Nodes Module.

This module defines the node functions for the LangGraph StateGraph workflow.
Each node wraps an agent's process() method and handles state transitions.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from app.core.schemas import AgentType, TaskStatus
from app.graphs.state import AgentState

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)


# Type alias for async node functions
AsyncNodeFunc = Callable[[AgentState], Awaitable[dict[str, Any]]]


class NodeFactory:
    """
    Factory for creating graph node functions.

    The NodeFactory creates node functions that wrap agent process() calls.
    It manages agent instances and provides consistent error handling.

    Attributes:
        llm_provider: Callable that returns an LLM instance for agents.
        agents: Dictionary of instantiated agents by type.

    Example:
        factory = NodeFactory(llm_provider=get_ollama_llm)
        pm_node = factory.create_pm_node()
    """

    def __init__(
        self,
        llm_provider: Callable[[], BaseChatModel],
        moe_llm_provider: Callable[[], BaseChatModel] | None = None,
    ) -> None:
        """
        Initialize the NodeFactory.

        Args:
            llm_provider: Callable that returns main LLM instance.
            moe_llm_provider: Optional callable for MoE model (router).
        """
        self._llm_provider = llm_provider
        self._moe_llm_provider = moe_llm_provider or llm_provider
        self._agents: dict[AgentType, Any] = {}

    def _get_agent(self, agent_type: AgentType) -> Any:
        """
        Get or create an agent instance.

        Args:
            agent_type: The type of agent to get.

        Returns:
            The agent instance.
        """
        if agent_type not in self._agents:
            self._agents[agent_type] = self._create_agent(agent_type)
        return self._agents[agent_type]

    def _create_agent(self, agent_type: AgentType) -> Any:
        """
        Create a new agent instance.

        Args:
            agent_type: The type of agent to create.

        Returns:
            New agent instance.

        Raises:
            ValueError: If agent type is unknown.
        """
        # Lazy imports to avoid circular dependencies
        from app.agents.coder_agent import CoderAgent
        from app.agents.pm_agent import PMAgent
        from app.agents.router_agent import RouterAgent
        from app.agents.specialist_agents import (
            ArchitectAgent,
            DocsAgent,
            ReviewerAgent,
            TesterAgent,
        )

        agent_map: dict[AgentType, Callable[[], Any]] = {
            AgentType.PM: lambda: PMAgent(llm=self._llm_provider()),
            AgentType.CODER: lambda: CoderAgent(llm=self._llm_provider()),
            AgentType.ARCHITECT: lambda: ArchitectAgent(
                llm=self._llm_provider()
            ),
            AgentType.TESTER: lambda: TesterAgent(llm=self._llm_provider()),
            AgentType.REVIEWER: lambda: ReviewerAgent(llm=self._llm_provider()),
            AgentType.DOCS: lambda: DocsAgent(llm=self._llm_provider()),
            AgentType.ROUTER: lambda: RouterAgent(llm=self._moe_llm_provider()),
        }

        creator = agent_map.get(agent_type)
        if not creator:
            raise ValueError(f"Unknown agent type: {agent_type}")

        return creator()

    def create_entry_node(self) -> AsyncNodeFunc:
        """
        Create the entry node function.

        The entry node initializes the workflow state and prepares
        for processing.

        Returns:
            Entry node function.
        """
        async def entry_node(state: AgentState) -> dict[str, Any]:
            """Initialize workflow state."""
            logger.info(f"Entry node: session {state.get('session_id')}")

            return {
                "task_status": TaskStatus.IN_PROGRESS,
                "iteration_count": state.get("iteration_count", 0) + 1,
            }

        return entry_node

    def create_pm_node(self) -> AsyncNodeFunc:
        """
        Create the PM agent node function.

        Returns:
            PM node function.
        """
        async def pm_node(state: AgentState) -> dict[str, Any]:
            """Execute PM agent processing."""
            logger.info(f"PM node: session {state.get('session_id')}")

            agent = self._get_agent(AgentType.PM)
            try:
                result: dict[str, Any] = await agent.process(state)
                return result
            except Exception as e:
                logger.error(f"PM node failed: {e}", exc_info=True)
                return {
                    "error": str(e),
                    "task_status": TaskStatus.FAILED,
                    "current_agent": AgentType.PM,
                }

        return pm_node

    def create_router_node(self) -> AsyncNodeFunc:
        """
        Create the router node function.

        Returns:
            Router node function.
        """
        async def router_node(state: AgentState) -> dict[str, Any]:
            """Execute router agent processing."""
            logger.info(f"Router node: session {state.get('session_id')}")

            agent = self._get_agent(AgentType.ROUTER)
            try:
                result: dict[str, Any] = await agent.process(state)
                return result
            except Exception as e:
                logger.error(f"Router node failed: {e}", exc_info=True)
                return {
                    "error": str(e),
                    "routing_decision": "pm",  # Default to PM on error
                    "current_agent": AgentType.ROUTER,
                }

        return router_node

    def create_coder_node(self) -> AsyncNodeFunc:
        """
        Create the coder agent node function.

        Returns:
            Coder node function.
        """
        async def coder_node(state: AgentState) -> dict[str, Any]:
            """Execute coder agent processing."""
            logger.info(f"Coder node: session {state.get('session_id')}")

            agent = self._get_agent(AgentType.CODER)
            try:
                result: dict[str, Any] = await agent.process(state)
                return result
            except Exception as e:
                logger.error(f"Coder node failed: {e}", exc_info=True)
                return {
                    "error": str(e),
                    "task_status": TaskStatus.FAILED,
                    "current_agent": AgentType.CODER,
                }

        return coder_node

    def create_architect_node(self) -> AsyncNodeFunc:
        """
        Create the architect agent node function.

        Returns:
            Architect node function.
        """
        async def architect_node(state: AgentState) -> dict[str, Any]:
            """Execute architect agent processing."""
            logger.info(f"Architect node: session {state.get('session_id')}")

            agent = self._get_agent(AgentType.ARCHITECT)
            try:
                result: dict[str, Any] = await agent.process(state)
                return result
            except Exception as e:
                logger.error(f"Architect node failed: {e}", exc_info=True)
                return {
                    "error": str(e),
                    "task_status": TaskStatus.FAILED,
                    "current_agent": AgentType.ARCHITECT,
                }

        return architect_node

    def create_tester_node(self) -> AsyncNodeFunc:
        """
        Create the tester agent node function.

        Returns:
            Tester node function.
        """
        async def tester_node(state: AgentState) -> dict[str, Any]:
            """Execute tester agent processing."""
            logger.info(f"Tester node: session {state.get('session_id')}")

            agent = self._get_agent(AgentType.TESTER)
            try:
                result: dict[str, Any] = await agent.process(state)
                return result
            except Exception as e:
                logger.error(f"Tester node failed: {e}", exc_info=True)
                return {
                    "error": str(e),
                    "task_status": TaskStatus.FAILED,
                    "current_agent": AgentType.TESTER,
                }

        return tester_node

    def create_reviewer_node(self) -> AsyncNodeFunc:
        """
        Create the reviewer agent node function.

        Returns:
            Reviewer node function.
        """
        async def reviewer_node(state: AgentState) -> dict[str, Any]:
            """Execute reviewer agent processing."""
            logger.info(f"Reviewer node: session {state.get('session_id')}")

            agent = self._get_agent(AgentType.REVIEWER)
            try:
                result: dict[str, Any] = await agent.process(state)
                return result
            except Exception as e:
                logger.error(f"Reviewer node failed: {e}", exc_info=True)
                return {
                    "error": str(e),
                    "task_status": TaskStatus.FAILED,
                    "current_agent": AgentType.REVIEWER,
                }

        return reviewer_node

    def create_docs_node(self) -> AsyncNodeFunc:
        """
        Create the docs agent node function.

        Returns:
            Docs node function.
        """
        async def docs_node(state: AgentState) -> dict[str, Any]:
            """Execute docs agent processing."""
            logger.info(f"Docs node: session {state.get('session_id')}")

            agent = self._get_agent(AgentType.DOCS)
            try:
                result: dict[str, Any] = await agent.process(state)
                return result
            except Exception as e:
                logger.error(f"Docs node failed: {e}", exc_info=True)
                return {
                    "error": str(e),
                    "task_status": TaskStatus.FAILED,
                    "current_agent": AgentType.DOCS,
                }

        return docs_node

    def create_aggregation_node(self) -> AsyncNodeFunc:
        """
        Create the aggregation node function.

        The aggregation node collects results from specialist agents
        and synthesizes them for the PM to review.

        Returns:
            Aggregation node function.
        """
        async def aggregation_node(state: AgentState) -> dict[str, Any]:
            """Aggregate results from specialist agents."""
            logger.info(
                f"Aggregation node: session {state.get('session_id')}"
            )

            completed = state.get("completed_tasks", [])
            pending = state.get("pending_tasks", [])

            # Check if all tasks are done
            if pending:
                # Still have pending tasks
                return {
                    "task_status": TaskStatus.IN_PROGRESS,
                }

            # All tasks completed
            if completed:
                # Prepare summary for PM
                results_summary: list[str] = []
                for task in completed:
                    agent = task.get("assigned_agent", "unknown")
                    status = task.get("status", TaskStatus.PENDING)
                    result_val = task.get("result")
                    result = (result_val or "No result")[:200]
                    results_summary.append(
                        f"- {agent}: {status.value} - {result}"
                    )

                return {
                    "task_status": TaskStatus.COMPLETED,
                    "aggregation_summary": "\n".join(results_summary),
                    "needs_pm_synthesis": True,
                }

            return {
                "task_status": TaskStatus.COMPLETED,
            }

        return aggregation_node

    def create_completion_node(self) -> AsyncNodeFunc:
        """
        Create the completion node function.

        The completion node finalizes the workflow and prepares
        the response for the user.

        Returns:
            Completion node function.
        """
        async def completion_node(state: AgentState) -> dict[str, Any]:
            """Finalize workflow and prepare response."""
            logger.info(
                f"Completion node: session {state.get('session_id')}"
            )

            # Mark workflow as completed
            return {
                "task_status": TaskStatus.COMPLETED,
                "workflow_completed": True,
            }

        return completion_node


def create_human_intervention_node() -> AsyncNodeFunc:
    """
    Create the human intervention node function.

    This node pauses the workflow for human review and approval.

    Returns:
        Human intervention node function.
    """
    async def human_intervention_node(state: AgentState) -> dict[str, Any]:
        """Pause for human intervention."""
        logger.info(
            f"Human intervention node: session {state.get('session_id')}"
        )

        return {
            "task_status": TaskStatus.BLOCKED,  # Using BLOCKED for human wait
            "requires_human_input": True,
            "intervention_reason": state.get(
                "intervention_reason",
                "Review required",
            ),
        }

    return human_intervention_node


def create_error_handler_node() -> AsyncNodeFunc:
    """
    Create the error handler node function.

    This node handles errors and attempts recovery.

    Returns:
        Error handler node function.
    """
    async def error_handler_node(state: AgentState) -> dict[str, Any]:
        """Handle errors and attempt recovery."""
        logger.error(
            f"Error handler node: session {state.get('session_id')}, "
            f"error: {state.get('error')}"
        )

        error = state.get("error", "Unknown error")
        retry_count_val = state.get("retry_count", 0)
        retry_count: int = int(retry_count_val) if retry_count_val else 0
        max_retries_val = state.get("max_retries", 3)
        max_retries: int = int(max_retries_val) if max_retries_val else 3

        if retry_count < max_retries:
            # Attempt retry
            logger.info(f"Retrying ({retry_count + 1}/{max_retries})")
            return {
                "retry_count": retry_count + 1,
                "error": None,
                "task_status": TaskStatus.IN_PROGRESS,
            }

        # Max retries exceeded
        logger.error(f"Max retries exceeded: {error}")
        return {
            "task_status": TaskStatus.FAILED,
            "final_error": error,
            "requires_human_input": True,
            "intervention_reason": (
                f"Failed after {max_retries} retries: {error}"
            ),
        }

    return error_handler_node
