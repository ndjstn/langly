"""
Project Manager Agent Implementation.

This module defines the PM Agent, which serves as the primary interface
for user interactions and coordinates work between specialist agents.
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.core.schemas import AgentType, TaskStatus
from app.graphs.state import AgentState, TaskState

logger = logging.getLogger(__name__)


class PMAgent(BaseAgent):
    """
    Project Manager Agent for user interaction and task coordination.

    The PM Agent is the primary point of contact for users, understanding
    their requirements and delegating work to appropriate specialist agents.
    It aggregates results and presents coherent responses.

    Responsibilities:
        - Parse user intent and requirements
        - Break down complex requests into subtasks
        - Delegate tasks to appropriate specialist agents
        - Track progress and aggregate results
        - Present final responses to users

    Example:
        llm = get_granite_dense_8b()
        pm_agent = PMAgent(llm=llm)
        state_updates = await pm_agent.process(current_state)
    """

    @property
    def agent_type(self) -> AgentType:
        """Return the PM agent type."""
        return AgentType.PM

    async def process(self, state: AgentState) -> dict[str, Any]:
        """
        Process user request and coordinate task delegation.

        This method analyzes the user's request, determines what actions
        need to be taken, and either responds directly or delegates to
        specialist agents.

        Args:
            state: The current workflow state.

        Returns:
            Dictionary of state updates including messages and tasks.
        """
        logger.info(f"PM Agent processing state for session {state['session_id']}")

        # Get the last user message
        last_message = self.extract_last_human_message(state)

        if not last_message:
            return self._handle_no_input(state)

        # Build conversation context
        messages = self._build_pm_messages(state, last_message)

        # Invoke LLM
        try:
            response = await self.invoke_llm(messages)
        except Exception as e:
            logger.error(f"PM Agent LLM invocation failed: {e}")
            return self.set_error(f"Failed to process request: {e}")

        # Extract content as string
        content = self.extract_content(response.content)

        # Parse the response to determine next actions
        parsed = self._parse_pm_response(content)

        # Build state updates
        updates: dict[str, Any] = {
            "messages": [self.format_response(
                content=parsed["response"],
                metadata={"parsed_intent": parsed.get("intent")},
            )],
            "current_agent": self.agent_type,
            "last_agent_output": parsed["response"],
        }

        # Handle task delegation if needed
        if parsed.get("delegate_to"):
            delegation_updates = self._create_delegation_tasks(
                state=state,
                delegations=parsed["delegate_to"],
            )
            updates.update(delegation_updates)

        # Update task status based on parsed response
        if parsed.get("is_complete"):
            updates["task_status"] = TaskStatus.COMPLETED
        else:
            updates["task_status"] = TaskStatus.IN_PROGRESS

        # Check if human review is needed
        if parsed.get("needs_human_review"):
            updates["requires_human_input"] = True
            updates["task_status"] = TaskStatus.NEEDS_REVIEW

        return updates

    def _build_pm_messages(
        self,
        state: AgentState,
        user_message: HumanMessage,
    ) -> list[SystemMessage | HumanMessage | AIMessage]:
        """
        Build the message list for PM LLM invocation.

        Args:
            state: Current workflow state.
            user_message: The user's request.

        Returns:
            List of messages including system prompt and context.
        """
        messages: list[SystemMessage | HumanMessage | AIMessage] = [
            SystemMessage(content=self._get_pm_system_prompt()),
        ]

        # Add conversation context
        context_messages = self.get_conversation_context(state, max_messages=6)
        for msg in context_messages:
            if isinstance(msg, (SystemMessage, HumanMessage, AIMessage)):
                messages.append(msg)

        # Add current user message if not already included
        if context_messages and context_messages[-1] != user_message:
            messages.append(user_message)

        return messages

    def _get_pm_system_prompt(self) -> str:
        """
        Get the enhanced PM system prompt with task analysis instructions.

        Returns:
            The complete PM system prompt.
        """
        base_prompt = self.system_prompt

        task_analysis_prompt = """

When analyzing user requests, you should:
1. Identify the type of task (coding, architecture, testing, etc.)
2. Determine if the task can be handled directly or needs delegation
3. Break complex tasks into smaller, actionable subtasks
4. Consider dependencies between subtasks

Format your response as follows:
- First, provide your natural language response to the user
- If delegation is needed, end with a JSON block like this:

```json
{
    "delegate_to": [
        {"agent": "coder", "task": "description of coding task"},
        {"agent": "tester", "task": "description of testing task"}
    ],
    "needs_human_review": false,
    "is_complete": false
}
```

Available agents for delegation:
- coder: For writing and modifying code
- architect: For system design and architecture decisions
- tester: For writing tests and verification
- reviewer: For code review and quality checks
- docs: For documentation tasks

If no delegation is needed, just respond naturally without the JSON block.
"""
        return base_prompt + task_analysis_prompt

    def _parse_pm_response(self, content: str) -> dict[str, Any]:
        """
        Parse PM response to extract response text and delegation info.

        Args:
            content: The raw LLM response content.

        Returns:
            Parsed response with response text and optional delegation info.
        """
        result: dict[str, Any] = {
            "response": content,
            "delegate_to": None,
            "needs_human_review": False,
            "is_complete": False,
            "intent": None,
        }

        # Try to extract JSON block
        if "```json" in content:
            try:
                json_start = content.index("```json") + 7
                json_end = content.index("```", json_start)
                json_str = content[json_start:json_end].strip()
                parsed_json = json.loads(json_str)

                # Extract delegation info
                result["delegate_to"] = parsed_json.get("delegate_to")
                result["needs_human_review"] = parsed_json.get(
                    "needs_human_review", False
                )
                result["is_complete"] = parsed_json.get("is_complete", False)
                result["intent"] = parsed_json.get("intent")

                # Clean the response by removing the JSON block
                result["response"] = content[:content.index("```json")].strip()

            except (ValueError, json.JSONDecodeError) as e:
                logger.warning(f"Failed to parse PM response JSON: {e}")

        return result

    def _create_delegation_tasks(
        self,
        state: AgentState,
        delegations: list[dict[str, str]],
    ) -> dict[str, Any]:
        """
        Create task entries for delegated work.

        Args:
            state: Current workflow state.
            delegations: List of delegation specifications.

        Returns:
            State updates with new pending tasks.
        """
        new_tasks: list[TaskState] = []

        for delegation in delegations:
            agent_name = delegation.get("agent", "")
            task_description = delegation.get("task", "")

            # Map agent name to AgentType
            agent_type = self._map_agent_name(agent_name)

            if agent_type:
                task: TaskState = {
                    "task_id": str(uuid.uuid4()),
                    "description": task_description,
                    "status": TaskStatus.PENDING,
                    "assigned_agent": agent_type,
                    "created_at": datetime.now(),
                    "completed_at": None,
                    "result": None,
                    "error": None,
                }
                new_tasks.append(task)
                logger.info(
                    f"PM created task {task['task_id'][:8]} "
                    f"for {agent_type.value}: {task_description[:50]}..."
                )

        return {
            "pending_tasks": state["pending_tasks"] + new_tasks,
            "routing_decision": (
                delegations[0]["agent"] if delegations else None
            ),
        }

    def _map_agent_name(self, name: str) -> AgentType | None:
        """
        Map agent name string to AgentType enum.

        Args:
            name: Agent name as string.

        Returns:
            Corresponding AgentType or None if not found.
        """
        mapping = {
            "coder": AgentType.CODER,
            "architect": AgentType.ARCHITECT,
            "tester": AgentType.TESTER,
            "reviewer": AgentType.REVIEWER,
            "docs": AgentType.DOCS,
            "pm": AgentType.PM,
            "router": AgentType.ROUTER,
        }
        return mapping.get(name.lower())

    def _handle_no_input(self, state: AgentState) -> dict[str, Any]:
        """
        Handle case where no user input is available.

        Args:
            state: Current workflow state.

        Returns:
            State updates with greeting message.
        """
        greeting = (
            "Hello! I'm your Project Manager. I'm here to help you with "
            "your development tasks. I can coordinate coding, testing, "
            "architecture design, code review, and documentation work. "
            "What would you like to accomplish today?"
        )

        return {
            "messages": [self.format_response(content=greeting)],
            "current_agent": self.agent_type,
            "task_status": TaskStatus.PENDING,
        }

    async def aggregate_agent_responses(
        self,
        state: AgentState,
    ) -> dict[str, Any]:
        """
        Aggregate responses from completed tasks into a summary.

        This method is called when all delegated tasks are complete
        to synthesize results into a coherent response for the user.

        Args:
            state: Current workflow state with completed tasks.

        Returns:
            State updates with aggregated response.
        """
        completed = state["completed_tasks"]

        if not completed:
            return {}

        # Build summary of completed work
        summaries = []
        for task in completed:
            if task["result"]:
                agent_name = (
                    task["assigned_agent"].value
                    if task["assigned_agent"] else "unknown"
                )
                summaries.append(
                    f"**{agent_name.title()}**: {task['result']}"
                )
            elif task["error"]:
                summaries.append(f"**Error**: {task['error']}")

        if summaries:
            summary_text = "\n\n".join(summaries)
            aggregation_prompt = f"""
Based on the completed work from the team:

{summary_text}

Please provide a coherent summary for the user, highlighting the key 
outcomes and any important details they should know.
"""

            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=aggregation_prompt),
            ]

            try:
                response = await self.invoke_llm(messages)
                return {
                    "messages": [self.format_response(
                        content=self.extract_content(response.content),
                        metadata={"aggregated_from": len(completed)},
                    )],
                    "task_status": TaskStatus.COMPLETED,
                }
            except Exception as e:
                logger.error(f"Failed to aggregate responses: {e}")

        return {"task_status": TaskStatus.COMPLETED}
