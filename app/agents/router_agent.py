"""
Router Agent Implementation.

This module defines the Router Agent, which uses a lightweight MoE model
to analyze requests and route them to the appropriate specialist agent.
"""
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.core.schemas import AgentType, TaskStatus
from app.graphs.state import AgentState

logger = logging.getLogger(__name__)


# Routing keywords for quick classification
ROUTE_KEYWORDS: dict[str, list[str]] = {
    "coder": [
        "write", "code", "implement", "function", "class", "module",
        "create", "build", "develop", "program", "script", "fix",
        "bug", "error", "refactor", "optimize", "python", "javascript",
    ],
    "architect": [
        "design", "architecture", "system", "structure", "diagram",
        "component", "service", "api", "database", "schema", "pattern",
        "scalability", "microservice", "infrastructure",
    ],
    "tester": [
        "test", "testing", "unittest", "pytest", "coverage", "mock",
        "validate", "verify", "qa", "quality", "assertion", "fixture",
    ],
    "reviewer": [
        "review", "check", "audit", "inspect", "evaluate", "feedback",
        "improve", "suggest", "quality", "best practice",
    ],
    "docs": [
        "document", "documentation", "readme", "docstring", "comment",
        "explain", "describe", "guide", "tutorial", "api doc",
    ],
}


class RouterAgent(BaseAgent):
    """
    Router Agent for intelligent task routing.

    The Router Agent uses a lightweight model (Granite MoE 1B/3B) to
    quickly analyze incoming requests and determine which specialist
    agent should handle them. It supports both keyword-based fast
    routing and LLM-based semantic routing for complex cases.

    Responsibilities:
        - Analyze task content and intent
        - Route to appropriate specialist agent
        - Handle ambiguous or multi-domain requests
        - Support parallel routing for multi-part tasks

    Example:
        llm = get_granite_moe_1b()
        router = RouterAgent(llm=llm)
        routing_decision = await router.process(state)
    """

    @property
    def agent_type(self) -> AgentType:
        """Return the Router agent type."""
        return AgentType.ROUTER

    async def process(self, state: AgentState) -> dict[str, Any]:
        """
        Analyze request and determine routing destination.

        This method examines the current state and pending tasks to
        determine which agent should handle the next action.

        Args:
            state: The current workflow state.

        Returns:
            Dictionary of state updates including routing decision.
        """
        logger.info(
            f"Router Agent processing for session {state['session_id']}"
        )

        # Check if there are pending tasks to route
        pending = state.get("pending_tasks", [])

        if pending:
            # Route first pending task
            task = pending[0]
            if task["assigned_agent"]:
                # Already assigned, return the routing
                return {
                    "routing_decision": task["assigned_agent"].value,
                    "current_agent": self.agent_type,
                }

        # Extract the content to route
        content = self._get_routing_content(state)

        if not content:
            # Default to PM for general inquiries
            return {
                "routing_decision": "pm",
                "current_agent": self.agent_type,
            }

        # Try fast keyword-based routing first
        fast_route = self._keyword_route(content)

        if fast_route:
            logger.info(f"Router: Fast routing to {fast_route}")
            return {
                "routing_decision": fast_route,
                "current_agent": self.agent_type,
            }

        # Fall back to LLM-based routing
        return await self._llm_route(state, content)

    def _get_routing_content(self, state: AgentState) -> str:
        """
        Extract content to analyze for routing.

        Args:
            state: Current workflow state.

        Returns:
            Content string to analyze.
        """
        # Check pending tasks first
        pending = state.get("pending_tasks", [])
        if pending:
            return pending[0].get("description", "")

        # Fall back to last human message
        last_msg = self.extract_last_human_message(state)
        if last_msg:
            return self.extract_content(last_msg.content)

        return ""

    def _keyword_route(self, content: str) -> str | None:
        """
        Perform fast keyword-based routing.

        Args:
            content: The content to analyze.

        Returns:
            Target agent name or None if no clear match.
        """
        content_lower = content.lower()
        scores: dict[str, int] = {agent: 0 for agent in ROUTE_KEYWORDS}

        for agent, keywords in ROUTE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in content_lower:
                    scores[agent] += 1

        # Get the agent with highest score
        if not scores:
            return None

        max_score = max(scores.values())

        if max_score == 0:
            return None

        # Check for clear winner (at least 2 points ahead)
        agents_with_max = [
            agent for agent, score in scores.items()
            if score == max_score
        ]

        if len(agents_with_max) == 1 and max_score >= 2:
            return agents_with_max[0]

        # No clear winner, use LLM
        return None

    async def _llm_route(
        self,
        state: AgentState,
        content: str,
    ) -> dict[str, Any]:
        """
        Use LLM for semantic routing.

        Args:
            state: Current workflow state.
            content: Content to route.

        Returns:
            State updates with routing decision.
        """
        messages: list[SystemMessage | HumanMessage | AIMessage] = [
            SystemMessage(content=self._get_routing_prompt()),
            HumanMessage(content=f"Route this request:\n\n{content}"),
        ]

        try:
            response = await self.invoke_llm(messages)
            response_text = self.extract_content(response.content).lower()

            # Parse the response to extract routing
            route = self._parse_routing_response(response_text)

            logger.info(f"Router: LLM routing to {route}")

            return {
                "routing_decision": route,
                "current_agent": self.agent_type,
            }

        except Exception as e:
            logger.error(f"Router LLM failed, defaulting to PM: {e}")
            return {
                "routing_decision": "pm",
                "current_agent": self.agent_type,
                "error": str(e),
            }

    def _get_routing_prompt(self) -> str:
        """
        Get the system prompt for routing decisions.

        Returns:
            Routing system prompt.
        """
        return """You are a routing agent that decides which specialist 
agent should handle a request.

Available agents:
- pm: Project Manager - handles user interaction, task coordination
- coder: Coder - writes and modifies code
- architect: Architect - designs systems and architecture
- tester: Tester - writes tests and validates code
- reviewer: Reviewer - reviews code for quality
- docs: Documentation - writes documentation

Respond with ONLY the agent name (e.g., "coder" or "architect").
Choose the single most appropriate agent for the primary task.

Rules:
1. If the request involves writing new code -> coder
2. If the request is about system design -> architect
3. If the request is about testing -> tester
4. If the request is about reviewing existing code -> reviewer
5. If the request is about documentation -> docs
6. If unclear or general conversation -> pm
"""

    def _parse_routing_response(self, response: str) -> str:
        """
        Parse the LLM response to extract routing target.

        Args:
            response: The LLM response text.

        Returns:
            The target agent name.
        """
        # Clean the response
        response = response.strip().lower()

        # Check for known agents
        known_agents = ["pm", "coder", "architect", "tester", "reviewer", "docs"]

        for agent in known_agents:
            if agent in response:
                return agent

        # Default to PM
        return "pm"

    def route_to_agent_type(self, route: str) -> AgentType | None:
        """
        Convert route string to AgentType enum.

        Args:
            route: Route string (e.g., "coder").

        Returns:
            Corresponding AgentType or None.
        """
        mapping = {
            "pm": AgentType.PM,
            "coder": AgentType.CODER,
            "architect": AgentType.ARCHITECT,
            "tester": AgentType.TESTER,
            "reviewer": AgentType.REVIEWER,
            "docs": AgentType.DOCS,
            "router": AgentType.ROUTER,
        }
        return mapping.get(route.lower())


def should_route(state: AgentState) -> bool:
    """
    Determine if routing is needed based on current state.

    This is used as a conditional function in the workflow graph.

    Args:
        state: The current workflow state.

    Returns:
        True if routing should occur, False otherwise.
    """
    # Route if there's no routing decision yet
    if not state.get("routing_decision"):
        return True

    # Route if there are unassigned pending tasks
    for task in state.get("pending_tasks", []):
        if not task.get("assigned_agent"):
            return True

    return False


def get_route_destination(state: AgentState) -> str:
    """
    Get the destination agent from routing decision.

    This is used as an edge function in the workflow graph.

    Args:
        state: The current workflow state.

    Returns:
        The target agent node name.
    """
    decision = state.get("routing_decision")

    if decision:
        return f"{decision}_node"

    # Default to PM
    return "pm_node"
