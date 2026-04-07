"""Built-in V3 tools."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.v3.tools.base import Tool, ToolContext, ToolInput, ToolOutput


class EchoInput(ToolInput):
    text: str = Field(..., min_length=1)


class EchoTool(Tool):
    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echo input text."

    @property
    def input_model(self) -> type[ToolInput]:
        return EchoInput

    async def run(self, _input: EchoInput, _context: ToolContext) -> ToolOutput:
        return ToolOutput(success=True, result={"text": _input.text})


class ApprovalInput(ToolInput):
    action: str = Field(..., min_length=1)


class ApprovalRequiredTool(Tool):
    @property
    def name(self) -> str:
        return "approval_required"

    @property
    def description(self) -> str:
        return "Request human approval before proceeding."

    @property
    def requires_approval(self) -> bool:
        return True

    @property
    def input_model(self) -> type[ToolInput]:
        return ApprovalInput

    async def run(self, _input: ApprovalInput, _context: ToolContext) -> ToolOutput:
        return ToolOutput(success=True, result={"action": _input.action})
