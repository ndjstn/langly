"""
Base Agent Abstract Class for the multi-agent system.

This module defines the abstract base class that all specialized agents
inherit from, providing common functionality and interface contracts.
"""
import logging
import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.core.constants import AGENT_SYSTEM_PROMPTS
from app.core.schemas import AgentType, TaskStatus
from app.graphs.state import AgentState

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the multi-agent system.

    This class provides the common interface and shared functionality
    that all specialized agents must implement. Each agent operates
    as an independent node in the LangGraph workflow.

    Attributes:
        agent_id: Unique identifier for this agent instance.
        agent_type: The type/role of this agent.
        llm: The language model used by this agent.
        tools: List of tools available to this agent.
        system_prompt: The system prompt that defines agent behavior.
        max_retries: Maximum retry attempts for LLM calls.

    Example:
        class CoderAgent(BaseAgent):
            @property
            def agent_type(self) -> AgentType:
                return AgentType.CODER

            async def process(self, state: AgentState) -> dict:
                # Implementation
                pass
    """

    def __init__(
        self,
        llm: BaseChatModel,
        tools: list[Any] | None = None,
        agent_id: str | None = None,
        max_retries: int = 3,
    ) -> None:
        """
        Initialize the base agent.

        Args:
            llm: The language model to use for this agent.
            tools: Optional list of tools available to this agent.
            agent_id: Optional unique identifier; generated if not provided.
            max_retries: Maximum number of retry attempts for LLM calls.
        """
        self._agent_id = agent_id or str(uuid.uuid4())
        self._llm = llm
        self._tools = tools or []
        self._max_retries = max_retries
        self._created_at = datetime.now()

        logger.info(
            f"Initialized {self.agent_type.value} agent with id {self._agent_id}"
        )

    @property
    def agent_id(self) -> str:
        """Get the unique agent identifier."""
        return self._agent_id

    @property
    @abstractmethod
    def agent_type(self) -> AgentType:
        """Get the type of this agent."""
        ...

    @property
    def llm(self) -> BaseChatModel:
        """Get the language model used by this agent."""
        return self._llm

    @property
    def tools(self) -> list[Any]:
        """Get the list of tools available to this agent."""
        return self._tools

    @property
    def system_prompt(self) -> str:
        """Get the system prompt for this agent."""
        return AGENT_SYSTEM_PROMPTS.get(
            self.agent_type.value,
            "You are a helpful assistant."
        )

    @property
    def max_retries(self) -> int:
        """Get the maximum retry attempts for LLM calls."""
        return self._max_retries

    @property
    def created_at(self) -> datetime:
        """Get the creation timestamp of this agent."""
        return self._created_at

    @abstractmethod
    async def process(self, state: AgentState) -> dict[str, Any]:
        """
        Process the current state and return state updates.

        This is the main entry point for agent logic. Each agent
        implements this method to handle its specific responsibilities.

        Args:
            state: The current workflow state.

        Returns:
            Dictionary of state updates to be merged with current state.

        Raises:
            AgentError: If processing fails after retries.
        """
        ...

    def format_response(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> AIMessage:
        """
        Format agent output as an AIMessage.

        Args:
            content: The response content.
            metadata: Optional additional metadata.

        Returns:
            Formatted AIMessage with agent attribution.
        """
        message_metadata = {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type.value,
            "timestamp": datetime.now().isoformat(),
        }

        if metadata:
            message_metadata.update(metadata)

        return AIMessage(
            content=content,
            additional_kwargs=message_metadata,
        )

    def extract_last_human_message(
        self,
        state: AgentState,
    ) -> HumanMessage | None:
        """
        Extract the most recent human message from state.

        Args:
            state: The current workflow state.

        Returns:
            The last HumanMessage, or None if not found.
        """
        for message in reversed(state["messages"]):
            if isinstance(message, HumanMessage):
                return message
        return None

    def extract_last_ai_message(
        self,
        state: AgentState,
    ) -> AIMessage | None:
        """
        Extract the most recent AI message from state.

        Args:
            state: The current workflow state.

        Returns:
            The last AIMessage, or None if not found.
        """
        for message in reversed(state["messages"]):
            if isinstance(message, AIMessage):
                return message
        return None

    def get_conversation_context(
        self,
        state: AgentState,
        max_messages: int = 10,
    ) -> list[BaseMessage]:
        """
        Get recent conversation context for the LLM.

        Args:
            state: The current workflow state.
            max_messages: Maximum number of messages to include.

        Returns:
            List of recent messages for context.
        """
        messages = state["messages"]
        if len(messages) <= max_messages:
            return list(messages)
        return list(messages[-max_messages:])

    def update_scratchpad(
        self,
        state: AgentState,
        key: str,
        value: Any,
    ) -> dict[str, dict[str, Any]]:
        """
        Return state update to add entry to agent scratchpad.

        Args:
            state: The current workflow state.
            key: The scratchpad entry key.
            value: The value to store.

        Returns:
            Dictionary with updated scratchpad.
        """
        scratchpad = dict(state["scratchpad"])
        scratchpad[key] = {
            "value": value,
            "timestamp": datetime.now().isoformat(),
            "agent": self.agent_type.value,
        }
        return {"scratchpad": scratchpad}

    def set_error(
        self,
        error_message: str,
    ) -> dict[str, Any]:
        """
        Return state update to set an error condition.

        Args:
            error_message: Description of the error.

        Returns:
            Dictionary with error state updates.
        """
        return {
            "error": error_message,
            "task_status": TaskStatus.FAILED,
        }

    def clear_error(self) -> dict[str, Any]:
        """
        Return state update to clear any error condition.

        Returns:
            Dictionary clearing error state.
        """
        return {
            "error": None,
            "task_status": TaskStatus.IN_PROGRESS,
        }

    def set_current_agent(self) -> dict[str, AgentType]:
        """
        Return state update to set this agent as current.

        Returns:
            Dictionary setting current_agent to this agent's type.
        """
        return {"current_agent": self.agent_type}

    async def invoke_llm(
        self,
        messages: Sequence[BaseMessage],
    ) -> AIMessage:
        """
        Invoke the LLM with the given messages.

        This method handles retries and error logging.

        Args:
            messages: Sequence of messages to send to the LLM.

        Returns:
            The LLM response as an AIMessage.

        Raises:
            Exception: If LLM invocation fails after all retries.
        """
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = await self.llm.ainvoke(list(messages))

                if isinstance(response, AIMessage):
                    return response

                return AIMessage(content=str(response.content))

            except Exception as e:
                last_error = e
                logger.warning(
                    f"LLM invocation attempt {attempt + 1} failed for "
                    f"{self.agent_type.value}: {e}"
                )

                if attempt < self.max_retries - 1:
                    continue

        logger.error(
            f"LLM invocation failed after {self.max_retries} attempts "
            f"for {self.agent_type.value}: {last_error}"
        )
        raise last_error  # type: ignore[misc]

    @staticmethod
    def extract_content(content: str | list[Any]) -> str:
        """
        Extract string content from LLM response content.

        LangChain messages can have content as string or list of
        content blocks. This method normalizes to string.

        Args:
            content: The content from an LLM message.

        Returns:
            The content as a plain string.
        """
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, str):
                    text_parts.append(item)
                elif isinstance(item, dict) and "text" in item:
                    text_parts.append(str(item["text"]))
            return " ".join(text_parts)
        return str(content)

    def __repr__(self) -> str:
        """Return string representation of the agent."""
        return (
            f"<{self.__class__.__name__} "
            f"id={self.agent_id[:8]}... "
            f"type={self.agent_type.value}>"
        )
