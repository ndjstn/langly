"""Example tool that requires approval."""
from __future__ import annotations

from app.runtime.tools.base import Tool, ToolContext, ToolInput, ToolOutput


class ApprovalInput(ToolInput):
    """Input for approval tool."""

    action: str


class ApprovalRequiredTool(Tool):
    """Tool that always requires approval."""

    @property
    def name(self) -> str:
        return "approval_required"

    @property
    def description(self) -> str:
        return "Example tool requiring human approval."

    @property
    def requires_approval(self) -> bool:
        return True

    @property
    def input_model(self) -> type[ToolInput]:
        return ApprovalInput

    async def run(self, _input: ApprovalInput, _context: ToolContext) -> ToolOutput:
        return ToolOutput(success=True, result=f"approved: {_input.action}")
