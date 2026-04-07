import pytest
from uuid import uuid4

from app.v3.engine import V3Engine


@pytest.mark.asyncio
async def test_v3_engine_pauses_on_approval(monkeypatch) -> None:
    engine = V3Engine()

    async def _fake_invoke(role: str, prompt: str) -> str:
        return """```tools
{"tool_calls": [{"name": "approval_required", "arguments": {"action": "deploy"}}]}
```"""

    monkeypatch.setattr(engine, "_invoke_role", _fake_invoke)

    run, response = await engine.run("deploy now", session_id=uuid4())
    assert run.status.value == "paused"
    assert "tool_calls" in (run.result or {})
    assert response
