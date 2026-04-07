import asyncio

from app.runtime.tools.base import Tool, ToolContext, ToolInput, ToolOutput
from app.runtime.tools.registry import ToolRegistry


class AlwaysApproveTool(Tool):
    @property
    def name(self) -> str:
        return "needs_approval"

    @property
    def requires_approval(self) -> bool:
        return True

    async def run(self, _input: ToolInput, _context: ToolContext) -> ToolOutput:
        return ToolOutput(success=True, result="ok")


def test_tool_requires_approval():
    registry = ToolRegistry()
    registry.register(AlwaysApproveTool())

    context = ToolContext(session_id="s", run_id="r", actor="pm")
    output = asyncio.run(registry.execute("needs_approval", {}, context))
    assert output.success is False
    assert output.error == "approval_required"
