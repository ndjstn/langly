import pytest

from app.v3.tools import get_tool_registry
from app.v3.tools.base import ToolContext


@pytest.mark.asyncio
async def test_echo_tool() -> None:
    registry = get_tool_registry()
    output = await registry.execute(
        "echo",
        {"text": "hello"},
        ToolContext(session_id=None, run_id=None, actor="test"),
    )
    assert output.success is True
    assert output.result == {"text": "hello"}


@pytest.mark.asyncio
async def test_approval_tool_requests() -> None:
    registry = get_tool_registry()
    output = await registry.execute(
        "approval_required",
        {"action": "deploy"},
        ToolContext(session_id=None, run_id=None, actor="test"),
    )
    assert output.success is False
    assert output.error == "approval_required"
    assert "request_id" in output.metadata
