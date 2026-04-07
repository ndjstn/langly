"""Tool registry for v2 runtime."""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.runtime.hitl import HITLManager, get_hitl_manager
from app.runtime.tools.base import Tool, ToolContext, ToolInput, ToolOutput
from app.runtime.tools.guardian import guard_tool_call


logger = logging.getLogger(__name__)


class ToolRegistry:
    """Register and execute tools with optional safety gate."""

    def __init__(self, hitl_manager: HITLManager | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        self._hitl = hitl_manager or get_hitl_manager()

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """Return registered tools."""
        return list(self._tools.values())

    async def execute(
        self,
        name: str,
        payload: dict[str, Any],
        context: ToolContext,
        *,
        bypass_approval: bool = False,
    ) -> ToolOutput:
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"Unknown tool: {name}")

        if tool.requires_approval and not bypass_approval:
            run_id: UUID | None = None
            try:
                run_id = UUID(context.run_id)
            except (ValueError, TypeError):
                run_id = None
            request = self._hitl.create_request(
                run_id=run_id,
                prompt=f"Approve tool '{name}'",
                context={
                    "tool": name,
                    "arguments": payload,
                    "actor": context.actor,
                },
            )
            self._hitl.register_pending_tool(
                request_id=request.id,
                tool_name=name,
                arguments=payload,
                context=context,
            )
            return ToolOutput(
                success=False,
                error="approval_required",
                metadata={"request_id": str(request.id)},
            )

        allowed, reason = await guard_tool_call(name, payload)
        if not allowed:
            return ToolOutput(success=False, error=reason or "blocked")

        input_model = tool.input_model
        parsed = input_model(**payload)

        errors = await tool.validate(parsed)
        if errors:
            return ToolOutput(success=False, error="; ".join(errors))

        logger.info("Executing tool %s", name)
        return await tool.run(parsed, context)
