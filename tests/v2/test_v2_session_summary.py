from uuid import UUID

from fastapi.testclient import TestClient

from app.api.app import create_app


def test_session_summary():
    app = create_app()
    client = TestClient(app)

    response = client.get(f"/api/v2/sessions/{UUID(int=0)}/summary")
    assert response.status_code == 200
    data = response.json()
    assert "runs" in data
    assert "tool_calls" in data
