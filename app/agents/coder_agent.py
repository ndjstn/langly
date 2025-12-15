"""
Coder Agent Implementation.

This module defines the Coder Agent, which handles code generation,
modification, and implementation tasks delegated by the PM Agent.
"""
import logging
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.core.schemas import AgentType, TaskStatus
from app.graphs.state import AgentState, TaskState

logger = logging.getLogger(__name__)


class CoderAgent(BaseAgent):
    """
    Coder Agent for code generation and implementation tasks.

    The Coder Agent specializes in writing, modifying, and explaining code.
    It receives tasks from the PM Agent and produces code solutions with
    explanations.

    Responsibilities:
        - Generate new code based on specifications
        - Modify existing code to add features or fix bugs
        - Explain code implementations
        - Follow best practices and coding standards

    Example:
        llm = get_granite_code()
        coder_agent = CoderAgent(llm=llm)
        state_updates = await coder_agent.process(current_state)
    """

    @property
    def agent_type(self) -> AgentType:
        """Return the Coder agent type."""
        return AgentType.CODER

    async def process(self, state: AgentState) -> dict[str, Any]:
        """
        Process a coding task and return implementation.

        This method analyzes the task context, generates or modifies code,
        and returns the results with explanations.

        Args:
            state: The current workflow state.

        Returns:
            Dictionary of state updates including generated code.
        """
        logger.info(
            f"Coder Agent processing state for session {state['session_id']}"
        )

        # Get the task assigned to this agent
        task = self._get_assigned_task(state)

        if not task:
            # No assigned task, check for direct message
            last_message = self.extract_last_human_message(state)
            if last_message:
                return await self._handle_direct_request(state, last_message)
            return self._handle_no_task(state)

        # Build messages for the coding task
        messages = self._build_coder_messages(state, task)

        # Invoke LLM for code generation
        try:
            response = await self.invoke_llm(messages)
        except Exception as e:
            logger.error(f"Coder Agent LLM invocation failed: {e}")
            return self._mark_task_failed(state, task, str(e))

        # Extract content
        content = self.extract_content(response.content)

        # Parse the response to extract code blocks
        parsed = self._parse_code_response(content)

        # Update task status
        updated_task = self._complete_task(task, parsed["full_response"])

        # Build state updates
        updates: dict[str, Any] = {
            "messages": [self.format_response(
                content=parsed["full_response"],
                metadata={
                    "code_blocks": len(parsed["code_blocks"]),
                    "language": parsed.get("primary_language"),
                    "task_id": task["task_id"],
                },
            )],
            "current_agent": self.agent_type,
            "last_agent_output": parsed["full_response"],
        }

        # Update task lists
        updates["pending_tasks"] = [
            t for t in state["pending_tasks"]
            if t["task_id"] != task["task_id"]
        ]
        updates["completed_tasks"] = state["completed_tasks"] + [updated_task]

        # Store code in scratchpad for later use
        if parsed["code_blocks"]:
            scratchpad_update = self.update_scratchpad(
                state,
                f"code_{task['task_id'][:8]}",
                {
                    "blocks": parsed["code_blocks"],
                    "language": parsed.get("primary_language"),
                },
            )
            updates.update(scratchpad_update)

        return updates

    async def _handle_direct_request(
        self,
        state: AgentState,
        message: HumanMessage,
    ) -> dict[str, Any]:
        """
        Handle a direct coding request without a task.

        Args:
            state: Current workflow state.
            message: The user's request.

        Returns:
            State updates with generated code.
        """
        messages: list[SystemMessage | HumanMessage | AIMessage] = [
            SystemMessage(content=self.system_prompt),
        ]

        # Add conversation context
        context = self.get_conversation_context(state, max_messages=4)
        for msg in context:
            if isinstance(msg, (SystemMessage, HumanMessage, AIMessage)):
                messages.append(msg)

        if context and context[-1] != message:
            messages.append(message)

        try:
            response = await self.invoke_llm(messages)
            content = self.extract_content(response.content)
            parsed = self._parse_code_response(content)

            return {
                "messages": [self.format_response(
                    content=parsed["full_response"],
                    metadata={"code_blocks": len(parsed["code_blocks"])},
                )],
                "current_agent": self.agent_type,
                "last_agent_output": parsed["full_response"],
            }

        except Exception as e:
            logger.error(f"Coder Agent direct request failed: {e}")
            return self.set_error(f"Failed to generate code: {e}")

    def _build_coder_messages(
        self,
        state: AgentState,
        task: TaskState,
    ) -> list[SystemMessage | HumanMessage | AIMessage]:
        """
        Build the message list for code generation.

        Args:
            state: Current workflow state.
            task: The assigned coding task.

        Returns:
            List of messages for LLM invocation.
        """
        system_prompt = self._get_enhanced_system_prompt()

        messages: list[SystemMessage | HumanMessage | AIMessage] = [
            SystemMessage(content=system_prompt),
        ]

        # Add relevant context from conversation
        context = self.get_conversation_context(state, max_messages=3)
        for msg in context:
            if isinstance(msg, (SystemMessage, HumanMessage, AIMessage)):
                messages.append(msg)

        # Add the task as a focused request
        task_prompt = f"""
Please complete the following coding task:

**Task Description:**
{task['description']}

**Requirements:**
1. Write clean, well-documented code
2. Follow best practices and coding standards
3. Include comments explaining key logic
4. Handle edge cases appropriately
5. Return the code in properly formatted code blocks

Please provide your implementation.
"""
        messages.append(HumanMessage(content=task_prompt))

        return messages

    def _get_enhanced_system_prompt(self) -> str:
        """
        Get the enhanced system prompt for code generation.

        Returns:
            Complete system prompt with coding guidelines.
        """
        base_prompt = self.system_prompt

        enhancements = """

When generating code, always:
1. Use proper formatting with appropriate indentation
2. Include type hints for Python code
3. Write comprehensive docstrings
4. Follow PEP 8 for Python code
5. Include error handling where appropriate
6. Use meaningful variable and function names

When modifying existing code:
1. Preserve the original style and conventions
2. Minimize changes to achieve the goal
3. Comment on significant changes
4. Maintain backward compatibility when possible

Format code in markdown code blocks with the appropriate language tag:
```python
# Python code here
```

```javascript
// JavaScript code here
```
"""
        return base_prompt + enhancements

    def _get_assigned_task(self, state: AgentState) -> TaskState | None:
        """
        Get the task assigned to this agent from pending tasks.

        Args:
            state: Current workflow state.

        Returns:
            The assigned task, or None if not found.
        """
        for task in state["pending_tasks"]:
            if task["assigned_agent"] == self.agent_type:
                return task
        return None

    def _parse_code_response(self, content: str) -> dict[str, Any]:
        """
        Parse the response to extract code blocks.

        Args:
            content: The raw response content.

        Returns:
            Parsed response with code blocks extracted.
        """
        result: dict[str, Any] = {
            "full_response": content,
            "code_blocks": [],
            "primary_language": None,
        }

        # Extract code blocks using regex
        code_pattern = r"```(\w+)?\n(.*?)```"
        matches = re.findall(code_pattern, content, re.DOTALL)

        for language, code in matches:
            result["code_blocks"].append({
                "language": language or "text",
                "code": code.strip(),
            })

            if result["primary_language"] is None and language:
                result["primary_language"] = language

        return result

    def _complete_task(
        self,
        task: TaskState,
        result: str,
    ) -> TaskState:
        """
        Mark a task as completed with result.

        Args:
            task: The task to complete.
            result: The task result.

        Returns:
            Updated task with completion status.
        """
        from datetime import datetime
        return TaskState(
            task_id=task["task_id"],
            description=task["description"],
            status=TaskStatus.COMPLETED,
            assigned_agent=task["assigned_agent"],
            created_at=task["created_at"],
            completed_at=datetime.now(),
            result=result[:500] if len(result) > 500 else result,
            error=None,
        )

    def _mark_task_failed(
        self,
        state: AgentState,
        task: TaskState,
        error: str,
    ) -> dict[str, Any]:
        """
        Mark a task as failed.

        Args:
            state: Current workflow state.
            task: The failed task.
            error: Error description.

        Returns:
            State updates reflecting failure.
        """
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

    def _handle_no_task(self, state: AgentState) -> dict[str, Any]:
        """
        Handle case where no task is assigned.

        Args:
            state: Current workflow state.

        Returns:
            State updates indicating no task.
        """
        return {
            "messages": [self.format_response(
                content=(
                    "I'm the Coder agent and I'm ready to help with "
                    "coding tasks. Please provide a coding task or have "
                    "the PM delegate one to me."
                ),
            )],
            "current_agent": self.agent_type,
            "task_status": TaskStatus.PENDING,
        }
