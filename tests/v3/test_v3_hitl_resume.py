import pytest
from uuid import UUID, uuid4

from app.v3.engine import V3Engine
from app.v3.hitl import get_hitl_manager, ApprovalResponse
from app.v3.tools.base import ToolContext


@pytest.mark.asyncio
async def test_hitl_pending_tool_registration() -> None:
    engine = V3Engine()
    manager = get_hitl_manager()

    output = await engine._tools.execute(
        "approval_required",
        {"action": "deploy"},
        ToolContext(session_id=str(uuid4()), run_id=str(uuid4()), actor="test"),
    )
    request_id = output.metadata.get("request_id")
    assert request_id

    pending = manager.pop_pending_tool(UUID(request_id))
    assert pending is not None


@pytest.mark.asyncio
async def test_hitl_resolve_approved_marks_resolved() -> None:
    manager = get_hitl_manager()
    request = manager.create_request(run_id=None, prompt="Approve")
    response = ApprovalResponse(request_id=request.id, approved=True)
    manager.resolve(response)
    assert manager.list_requests(resolved=True)
