from uuid import UUID

from fastapi.testclient import TestClient

from app.api.app import create_app


def test_session_runs_empty():
    app = create_app()
    client = TestClient(app)

    response = client.get(f"/api/v2/sessions/{UUID(int=0)}/runs")
    assert response.status_code == 200
    data = response.json()
    assert "runs" in data


def test_session_messages_not_found():
    app = create_app()
    client = TestClient(app)

    response = client.get(f"/api/v2/sessions/{UUID(int=0)}/messages")
    assert response.status_code in (200, 404)
