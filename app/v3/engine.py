"""V3 runtime engine (graph-first, small-model)."""
from __future__ import annotations

import json
import logging
from uuid import UUID, uuid4

from langchain_core.messages import HumanMessage, SystemMessage

from app.v3.graph import NodeContext
from app.v3.llm import TinyLLMProvider
from app.v3.models import (
    DeltaKind,
    Run,
    RunStatus,
    StateDelta,
    TaskStatus,
    ToolCall,
    ToolCallStatus,
)
from app.v3.nodes import PlannerNode, RouterNode
from app.v3.events import get_event_bus
from app.v3.store import AsyncEventStore
from app.v3.tools import get_tool_registry
from app.v3.tools.base import ToolContext


logger = logging.getLogger(__name__)


class V3Engine:
    """Graph-native V3 engine with event-sourced deltas."""

    def __init__(self) -> None:
        self._provider = TinyLLMProvider()
        self._store = AsyncEventStore()
        self._router = RouterNode()
        self._planner = PlannerNode()
        self._events = get_event_bus()
        self._tools = get_tool_registry()

    async def run(
        self,
        message: str,
        session_id: UUID | None = None,
    ) -> tuple[Run, str]:
        session_id = session_id or uuid4()
        run = Run(session_id=session_id, status=RunStatus.RUNNING)
        await self._store.save_run(run)

        await self._emit_delta(
            run_id=run.id,
            node_id="user_input",
            kind=DeltaKind.USER_INPUT,
            changes={"message": message},
        )

        context = NodeContext(run_id=run.id, session_id=session_id)

        # Route
        await self._emit_delta(run.id, "router", DeltaKind.NODE_START, {})
        router_result = await self._router.run(context, message)
        await self._emit_delta(
            run.id,
            "router",
            DeltaKind.NODE_END,
            {"route_role": router_result.output},
        )

        # Plan
        await self._emit_delta(run.id, "planner", DeltaKind.NODE_START, {})
        planner_result = await self._planner.run(context, message)
        await self._emit_delta(
            run.id,
            "planner",
            DeltaKind.NODE_END,
            {"tasks": [task.model_dump() for task in planner_result.tasks]},
        )

        outputs: list[str] = []
        for task in planner_result.tasks:
            task.status = TaskStatus.IN_PROGRESS
            role = task.assigned_agent or "planner"
            outputs.append(await self._invoke_role(role, task.description))
            task.status = TaskStatus.COMPLETED

        synthesis = await self._invoke_role(
            "planner",
            "Synthesize these outputs:\n\n" + "\n\n".join(outputs),
        )

        tool_calls = self._extract_tool_calls(synthesis)
        executed_calls: list[ToolCall] = []
        for call in tool_calls:
            result = await self._execute_tool(
                session_id=session_id,
                run_id=run.id,
                tool_name=str(call.get("name", "")),
                arguments=call.get("arguments", {}),
            )
            executed_calls.append(result)
            if result.status == ToolCallStatus.APPROVAL_REQUIRED:
                run.status = RunStatus.PAUSED
                run.error = "approval_required"
                run.result = {
                    "response": synthesis,
                    "tool_calls": [tool.model_dump() for tool in executed_calls],
                }
                await self._store.update_run(
                    run.id,
                    run.status,
                    run.result,
                    run.error,
                )
                return run, synthesis

        if executed_calls:
            synthesis = await self._invoke_role(
                "planner",
                "Incorporate these tool results into the response:\n\n"
                + "\n\n".join(
                    json.dumps(call.model_dump()) for call in executed_calls
                ),
            )

        run.status = RunStatus.COMPLETED
        run.result = {
            "response": synthesis,
            "tool_calls": [tool.model_dump() for tool in executed_calls],
        }
        await self._store.update_run(run.id, run.status, run.result, None)
        return run, synthesis

    async def _invoke_role(self, role: str, prompt: str) -> str:
        messages = [
            SystemMessage(content=f"You are the {role} agent."),
            HumanMessage(content=prompt),
        ]
        return await self._provider.invoke(role, messages)

    async def _emit_delta(
        self,
        run_id: UUID,
        node_id: str,
        kind: DeltaKind,
        changes: dict[str, object],
    ) -> None:
        delta = StateDelta(
            run_id=run_id,
            node_id=node_id,
            kind=kind,
            changes=changes,
        )
        await self._store.save_delta(delta)
        await self._events.publish(
            {
                "type": "state_delta",
                "delta": delta.model_dump(),
            }
        )

    def _extract_tool_calls(self, content: str) -> list[dict[str, object]]:
        if "```tools" not in content:
            return []
        try:
            start = content.index("```tools") + len("```tools")
            end = content.index("```", start)
            payload = content[start:end].strip()
            data = json.loads(payload)
            calls = data.get("tool_calls", [])
            if isinstance(calls, list):
                return [call for call in calls if isinstance(call, dict)]
        except (ValueError, json.JSONDecodeError):
            return []
        return []

    async def _execute_tool(
        self,
        *,
        session_id: UUID,
        run_id: UUID,
        tool_name: str,
        arguments: dict[str, object],
    ) -> ToolCall:
        context = ToolContext(
            session_id=str(session_id),
            run_id=str(run_id),
            actor="planner",
        )
        output = await self._tools.execute(tool_name, arguments, context)
        status = (
            ToolCallStatus.APPROVAL_REQUIRED
            if output.error == "approval_required"
            else (ToolCallStatus.COMPLETED if output.success else ToolCallStatus.FAILED)
        )
        call = ToolCall(
            name=tool_name,
            arguments=arguments,
            status=status,
            result=output.result,
            error=output.error,
            metadata=output.metadata,
        )
        await self._emit_delta(
            run_id=run_id,
            node_id=f"tool:{tool_name}",
            kind=DeltaKind.TOOL_CALL,
            changes=call.model_dump(),
        )
        if status == ToolCallStatus.APPROVAL_REQUIRED:
            await self._emit_delta(
                run_id=run_id,
                node_id="hitl",
                kind=DeltaKind.APPROVAL,
                changes={
                    "tool": tool_name,
                    "request_id": output.metadata.get("request_id"),
                },
            )
        return call
