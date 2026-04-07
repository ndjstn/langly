"""Builtin tools for v2 runtime."""
from __future__ import annotations

from app.runtime.tools.base import Tool, ToolContext, ToolInput, ToolOutput


class EchoInput(ToolInput):
    """Input for echo tool."""

    text: str


class EchoTool(Tool):
    """Simple echo tool for validation."""

    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Return the provided text."

    @property
    def input_model(self) -> type[ToolInput]:
        return EchoInput

    async def run(self, _input: EchoInput, _context: ToolContext) -> ToolOutput:
        return ToolOutput(success=True, result=_input.text)
