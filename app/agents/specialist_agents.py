"""
Specialist Agent Implementations.

This module defines the specialized worker agents that handle specific
types of tasks: Architect, Tester, Reviewer, and Documentation agents.
"""
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.core.schemas import AgentType, TaskStatus
from app.graphs.state import AgentState, TaskState

logger = logging.getLogger(__name__)


class ArchitectAgent(BaseAgent):
    """
    Architect Agent for system design and architecture decisions.

    Responsibilities:
        - Design system architecture and component structures
        - Make technology recommendations
        - Define API contracts and interfaces
        - Create architectural diagrams and documentation
    """

    @property
    def agent_type(self) -> AgentType:
        """Return the Architect agent type."""
        return AgentType.ARCHITECT

    async def process(self, state: AgentState) -> dict[str, Any]:
        """
        Process an architecture or design task.

        Args:
            state: The current workflow state.

        Returns:
            Dictionary of state updates.
        """
        logger.info(
            f"Architect Agent processing for session {state['session_id']}"
        )

        task = self._get_assigned_task(state)

        if not task:
            return self._handle_no_task()

        messages = self._build_messages(state, task)

        try:
            response = await self.invoke_llm(messages)
            content = self.extract_content(response.content)
        except Exception as e:
            logger.error(f"Architect Agent failed: {e}")
            return self._mark_task_failed(state, task, str(e))

        return self._complete_task_update(state, task, content)

    def _build_messages(
        self,
        state: AgentState,
        task: TaskState,
    ) -> list[SystemMessage | HumanMessage | AIMessage]:
        """Build messages for architecture task."""
        messages: list[SystemMessage | HumanMessage | AIMessage] = [
            SystemMessage(content=self._get_enhanced_prompt()),
        ]

        context = self.get_conversation_context(state, max_messages=3)
        for msg in context:
            if isinstance(msg, (SystemMessage, HumanMessage, AIMessage)):
                messages.append(msg)

        task_prompt = f"""
Please provide architectural guidance for the following:

**Task:** {task['description']}

Consider:
1. System components and their interactions
2. Data flow and storage requirements
3. Scalability and performance implications
4. Security considerations
5. Technology recommendations
"""
        messages.append(HumanMessage(content=task_prompt))
        return messages

    def _get_enhanced_prompt(self) -> str:
        """Get enhanced system prompt for architecture tasks."""
        return self.system_prompt + """

When providing architectural guidance:
1. Use clear diagrams descriptions (Mermaid/ASCII when appropriate)
2. Consider maintainability and extensibility
3. Identify potential bottlenecks
4. Suggest design patterns where applicable
5. Consider deployment and infrastructure needs
"""

    def _get_assigned_task(self, state: AgentState) -> TaskState | None:
        """Get task assigned to this agent."""
        for task in state["pending_tasks"]:
            if task["assigned_agent"] == self.agent_type:
                return task
        return None

    def _complete_task_update(
        self,
        state: AgentState,
        task: TaskState,
        content: str,
    ) -> dict[str, Any]:
        """Build state update for completed task."""
        from datetime import datetime
        completed_task = TaskState(
            task_id=task["task_id"],
            description=task["description"],
            status=TaskStatus.COMPLETED,
            assigned_agent=task["assigned_agent"],
            created_at=task["created_at"],
            completed_at=datetime.now(),
            result=content[:500] if len(content) > 500 else content,
            error=None,
        )

        return {
            "messages": [self.format_response(
                content=content,
                metadata={"task_id": task["task_id"]},
            )],
            "current_agent": self.agent_type,
            "last_agent_output": content,
            "pending_tasks": [
                t for t in state["pending_tasks"]
                if t["task_id"] != task["task_id"]
            ],
            "completed_tasks": state["completed_tasks"] + [completed_task],
        }

    def _mark_task_failed(
        self,
        state: AgentState,
        task: TaskState,
        error: str,
    ) -> dict[str, Any]:
        """Mark task as failed."""
        from datetime import datetime
        failed_task = TaskState(
            task_id=task["task_id"],
            description=task["description"],
            status=TaskStatus.FAILED,
            assigned_agent=task["assigned_agent"],
            created_at=task["created_at"],
            completed_at=datetime.now(),
            result=None,
            error=error,
        )

        return {
            "pending_tasks": [
                t for t in state["pending_tasks"]
                if t["task_id"] != task["task_id"]
            ],
            "completed_tasks": state["completed_tasks"] + [failed_task],
            "error": error,
            "task_status": TaskStatus.FAILED,
        }

    def _handle_no_task(self) -> dict[str, Any]:
        """Handle no assigned task."""
        return {
            "messages": [self.format_response(
                content=(
                    "I'm the Architect agent, ready to help with system "
                    "design and architecture decisions."
                ),
            )],
            "current_agent": self.agent_type,
            "task_status": TaskStatus.PENDING,
        }


class TesterAgent(BaseAgent):
    """
    Tester Agent for writing tests and verification.

    Responsibilities:
        - Write unit and integration tests
        - Design test strategies
        - Identify edge cases
        - Validate implementations
    """

    @property
    def agent_type(self) -> AgentType:
        """Return the Tester agent type."""
        return AgentType.TESTER

    async def process(self, state: AgentState) -> dict[str, Any]:
        """
        Process a testing task.

        Args:
            state: The current workflow state.

        Returns:
            Dictionary of state updates.
        """
        logger.info(
            f"Tester Agent processing for session {state['session_id']}"
        )

        task = self._get_assigned_task(state)

        if not task:
            return self._handle_no_task()

        messages = self._build_messages(state, task)

        try:
            response = await self.invoke_llm(messages)
            content = self.extract_content(response.content)
        except Exception as e:
            logger.error(f"Tester Agent failed: {e}")
            return self._mark_task_failed(state, task, str(e))

        return self._complete_task_update(state, task, content)

    def _build_messages(
        self,
        state: AgentState,
        task: TaskState,
    ) -> list[SystemMessage | HumanMessage | AIMessage]:
        """Build messages for testing task."""
        messages: list[SystemMessage | HumanMessage | AIMessage] = [
            SystemMessage(content=self._get_enhanced_prompt()),
        ]

        context = self.get_conversation_context(state, max_messages=4)
        for msg in context:
            if isinstance(msg, (SystemMessage, HumanMessage, AIMessage)):
                messages.append(msg)

        task_prompt = f"""
Please create tests for the following:

**Task:** {task['description']}

Requirements:
1. Write comprehensive test cases
2. Cover edge cases and error conditions
3. Use pytest conventions
4. Include setup and teardown as needed
5. Add descriptive test names and docstrings
"""
        messages.append(HumanMessage(content=task_prompt))
        return messages

    def _get_enhanced_prompt(self) -> str:
        """Get enhanced system prompt for testing."""
        return self.system_prompt + """

When writing tests:
1. Use pytest framework and conventions
2. Follow AAA pattern (Arrange, Act, Assert)
3. Test happy paths, edge cases, and error handling
4. Use fixtures for setup
5. Mock external dependencies
6. Aim for meaningful coverage, not just high numbers
"""

    def _get_assigned_task(self, state: AgentState) -> TaskState | None:
        """Get task assigned to this agent."""
        for task in state["pending_tasks"]:
            if task["assigned_agent"] == self.agent_type:
                return task
        return None

    def _complete_task_update(
        self,
        state: AgentState,
        task: TaskState,
        content: str,
    ) -> dict[str, Any]:
        """Build state update for completed task."""
        from datetime import datetime
        completed_task = TaskState(
            task_id=task["task_id"],
            description=task["description"],
            status=TaskStatus.COMPLETED,
            assigned_agent=task["assigned_agent"],
            created_at=task["created_at"],
            completed_at=datetime.now(),
            result=content[:500] if len(content) > 500 else content,
            error=None,
        )

        return {
            "messages": [self.format_response(
                content=content,
                metadata={"task_id": task["task_id"]},
            )],
            "current_agent": self.agent_type,
            "last_agent_output": content,
            "pending_tasks": [
                t for t in state["pending_tasks"]
                if t["task_id"] != task["task_id"]
            ],
            "completed_tasks": state["completed_tasks"] + [completed_task],
        }

    def _mark_task_failed(
        self,
        state: AgentState,
        task: TaskState,
        error: str,
    ) -> dict[str, Any]:
        """Mark task as failed."""
        from datetime import datetime
        failed_task = TaskState(
            task_id=task["task_id"],
            description=task["description"],
            status=TaskStatus.FAILED,
            assigned_agent=task["assigned_agent"],
            created_at=task["created_at"],
            completed_at=datetime.now(),
            result=None,
            error=error,
        )

        return {
            "pending_tasks": [
                t for t in state["pending_tasks"]
                if t["task_id"] != task["task_id"]
            ],
            "completed_tasks": state["completed_tasks"] + [failed_task],
            "error": error,
            "task_status": TaskStatus.FAILED,
        }

    def _handle_no_task(self) -> dict[str, Any]:
        """Handle no assigned task."""
        return {
            "messages": [self.format_response(
                content=(
                    "I'm the Tester agent, ready to help write tests "
                    "and validate implementations."
                ),
            )],
            "current_agent": self.agent_type,
            "task_status": TaskStatus.PENDING,
        }


class ReviewerAgent(BaseAgent):
    """
    Code Reviewer Agent for quality checks.

    Responsibilities:
        - Review code for quality and best practices
        - Identify bugs and security issues
        - Suggest improvements
        - Ensure coding standards compliance
    """

    @property
    def agent_type(self) -> AgentType:
        """Return the Reviewer agent type."""
        return AgentType.REVIEWER

    async def process(self, state: AgentState) -> dict[str, Any]:
        """
        Process a code review task.

        Args:
            state: The current workflow state.

        Returns:
            Dictionary of state updates.
        """
        logger.info(
            f"Reviewer Agent processing for session {state['session_id']}"
        )

        task = self._get_assigned_task(state)

        if not task:
            return self._handle_no_task()

        messages = self._build_messages(state, task)

        try:
            response = await self.invoke_llm(messages)
            content = self.extract_content(response.content)
        except Exception as e:
            logger.error(f"Reviewer Agent failed: {e}")
            return self._mark_task_failed(state, task, str(e))

        return self._complete_task_update(state, task, content)

    def _build_messages(
        self,
        state: AgentState,
        task: TaskState,
    ) -> list[SystemMessage | HumanMessage | AIMessage]:
        """Build messages for review task."""
        messages: list[SystemMessage | HumanMessage | AIMessage] = [
            SystemMessage(content=self._get_enhanced_prompt()),
        ]

        context = self.get_conversation_context(state, max_messages=5)
        for msg in context:
            if isinstance(msg, (SystemMessage, HumanMessage, AIMessage)):
                messages.append(msg)

        task_prompt = f"""
Please review the following:

**Task:** {task['description']}

Review for:
1. Code quality and readability
2. Best practices and design patterns
3. Potential bugs or edge cases
4. Security vulnerabilities
5. Performance considerations
6. Documentation completeness

Provide specific, actionable feedback with line references where applicable.
"""
        messages.append(HumanMessage(content=task_prompt))
        return messages

    def _get_enhanced_prompt(self) -> str:
        """Get enhanced system prompt for reviews."""
        return self.system_prompt + """

When reviewing code:
1. Be constructive and specific
2. Prioritize issues by severity
3. Explain *why* something is problematic
4. Suggest concrete improvements
5. Acknowledge good practices
6. Consider maintainability and team context
"""

    def _get_assigned_task(self, state: AgentState) -> TaskState | None:
        """Get task assigned to this agent."""
        for task in state["pending_tasks"]:
            if task["assigned_agent"] == self.agent_type:
                return task
        return None

    def _complete_task_update(
        self,
        state: AgentState,
        task: TaskState,
        content: str,
    ) -> dict[str, Any]:
        """Build state update for completed task."""
        from datetime import datetime
        completed_task = TaskState(
            task_id=task["task_id"],
            description=task["description"],
            status=TaskStatus.COMPLETED,
            assigned_agent=task["assigned_agent"],
            created_at=task["created_at"],
            completed_at=datetime.now(),
            result=content[:500] if len(content) > 500 else content,
            error=None,
        )

        return {
            "messages": [self.format_response(
                content=content,
                metadata={"task_id": task["task_id"]},
            )],
            "current_agent": self.agent_type,
            "last_agent_output": content,
            "pending_tasks": [
                t for t in state["pending_tasks"]
                if t["task_id"] != task["task_id"]
            ],
            "completed_tasks": state["completed_tasks"] + [completed_task],
        }

    def _mark_task_failed(
        self,
        state: AgentState,
        task: TaskState,
        error: str,
    ) -> dict[str, Any]:
        """Mark task as failed."""
        from datetime import datetime
        failed_task = TaskState(
            task_id=task["task_id"],
            description=task["description"],
            status=TaskStatus.FAILED,
            assigned_agent=task["assigned_agent"],
            created_at=task["created_at"],
            completed_at=datetime.now(),
            result=None,
            error=error,
        )

        return {
            "pending_tasks": [
                t for t in state["pending_tasks"]
                if t["task_id"] != task["task_id"]
            ],
            "completed_tasks": state["completed_tasks"] + [failed_task],
            "error": error,
            "task_status": TaskStatus.FAILED,
        }

    def _handle_no_task(self) -> dict[str, Any]:
        """Handle no assigned task."""
        return {
            "messages": [self.format_response(
                content=(
                    "I'm the Reviewer agent, ready to review code "
                    "for quality and best practices."
                ),
            )],
            "current_agent": self.agent_type,
            "task_status": TaskStatus.PENDING,
        }


class DocsAgent(BaseAgent):
    """
    Documentation Agent for creating documentation.

    Responsibilities:
        - Write technical documentation
        - Create API documentation
        - Write user guides and tutorials
        - Generate docstrings and comments
    """

    @property
    def agent_type(self) -> AgentType:
        """Return the Docs agent type."""
        return AgentType.DOCS

    async def process(self, state: AgentState) -> dict[str, Any]:
        """
        Process a documentation task.

        Args:
            state: The current workflow state.

        Returns:
            Dictionary of state updates.
        """
        logger.info(
            f"Docs Agent processing for session {state['session_id']}"
        )

        task = self._get_assigned_task(state)

        if not task:
            return self._handle_no_task()

        messages = self._build_messages(state, task)

        try:
            response = await self.invoke_llm(messages)
            content = self.extract_content(response.content)
        except Exception as e:
            logger.error(f"Docs Agent failed: {e}")
            return self._mark_task_failed(state, task, str(e))

        return self._complete_task_update(state, task, content)

    def _build_messages(
        self,
        state: AgentState,
        task: TaskState,
    ) -> list[SystemMessage | HumanMessage | AIMessage]:
        """Build messages for documentation task."""
        messages: list[SystemMessage | HumanMessage | AIMessage] = [
            SystemMessage(content=self._get_enhanced_prompt()),
        ]

        context = self.get_conversation_context(state, max_messages=4)
        for msg in context:
            if isinstance(msg, (SystemMessage, HumanMessage, AIMessage)):
                messages.append(msg)

        task_prompt = f"""
Please create documentation for the following:

**Task:** {task['description']}

Requirements:
1. Clear and concise language
2. Proper structure with headings
3. Code examples where appropriate
4. Installation/setup instructions if applicable
5. API reference for functions/classes
"""
        messages.append(HumanMessage(content=task_prompt))
        return messages

    def _get_enhanced_prompt(self) -> str:
        """Get enhanced system prompt for documentation."""
        return self.system_prompt + """

When writing documentation:
1. Use clear, concise language
2. Structure with meaningful headings
3. Include practical examples
4. Consider the audience's expertise level
5. Use consistent formatting
6. Keep it up-to-date with code
"""

    def _get_assigned_task(self, state: AgentState) -> TaskState | None:
        """Get task assigned to this agent."""
        for task in state["pending_tasks"]:
            if task["assigned_agent"] == self.agent_type:
                return task
        return None

    def _complete_task_update(
        self,
        state: AgentState,
        task: TaskState,
        content: str,
    ) -> dict[str, Any]:
        """Build state update for completed task."""
        from datetime import datetime
        completed_task = TaskState(
            task_id=task["task_id"],
            description=task["description"],
            status=TaskStatus.COMPLETED,
            assigned_agent=task["assigned_agent"],
            created_at=task["created_at"],
            completed_at=datetime.now(),
            result=content[:500] if len(content) > 500 else content,
            error=None,
        )

        return {
            "messages": [self.format_response(
                content=content,
                metadata={"task_id": task["task_id"]},
            )],
            "current_agent": self.agent_type,
            "last_agent_output": content,
            "pending_tasks": [
                t for t in state["pending_tasks"]
                if t["task_id"] != task["task_id"]
            ],
            "completed_tasks": state["completed_tasks"] + [completed_task],
        }

    def _mark_task_failed(
        self,
        state: AgentState,
        task: TaskState,
        error: str,
    ) -> dict[str, Any]:
        """Mark task as failed."""
        from datetime import datetime
        failed_task = TaskState(
            task_id=task["task_id"],
            description=task["description"],
            status=TaskStatus.FAILED,
            assigned_agent=task["assigned_agent"],
            created_at=task["created_at"],
            completed_at=datetime.now(),
            result=None,
            error=error,
        )

        return {
            "pending_tasks": [
                t for t in state["pending_tasks"]
                if t["task_id"] != task["task_id"]
            ],
            "completed_tasks": state["completed_tasks"] + [failed_task],
            "error": error,
            "task_status": TaskStatus.FAILED,
        }

    def _handle_no_task(self) -> dict[str, Any]:
        """Handle no assigned task."""
        return {
            "messages": [self.format_response(
                content=(
                    "I'm the Documentation agent, ready to help create "
                    "clear and comprehensive documentation."
                ),
            )],
            "current_agent": self.agent_type,
            "task_status": TaskStatus.PENDING,
        }
