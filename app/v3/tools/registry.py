"""Tool registry for V3."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from app.v3.hitl import HITLManager, get_hitl_manager
from app.v3.tools.base import Tool, ToolContext, ToolInput, ToolOutput


class ToolRegistry:
    def __init__(self, hitl_manager: HITLManager | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        self._hitl = hitl_manager or get_hitl_manager()

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    async def execute(
        self,
        name: str,
        payload: dict[str, Any],
        context: ToolContext,
    ) -> ToolOutput:
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"Unknown tool: {name}")

        if tool.requires_approval:
            run_id: UUID | None = None
            if context.run_id:
                try:
                    run_id = UUID(context.run_id)
                except (ValueError, TypeError):
                    run_id = None
            request = self._hitl.create_request(
                run_id=run_id,
                prompt=f"Approve tool '{name}'",
                context={"tool": name, "arguments": payload, "actor": context.actor},
            )
            self._hitl.register_pending_tool(
                request_id=request.id,
                tool_name=name,
                arguments=payload,
                context={
                    "session_id": context.session_id,
                    "run_id": context.run_id,
                    "actor": context.actor,
                },
            )
            return ToolOutput(
                success=False,
                error="approval_required",
                metadata={"request_id": str(request.id)},
            )

        parsed = tool.input_model(**payload)
        errors = await tool.validate(parsed)
        if errors:
            return ToolOutput(success=False, error="; ".join(errors))
        return await tool.run(parsed, context)
