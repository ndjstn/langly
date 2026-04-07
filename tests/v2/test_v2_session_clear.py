from uuid import UUID

from fastapi.testclient import TestClient

from app.api.app import create_app


def test_session_clear():
    app = create_app()
    client = TestClient(app)

    response = client.post(f"/api/v2/sessions/{UUID(int=0)}/clear")
    assert response.status_code == 200
    data = response.json()
    assert "runs_deleted" in data
    assert "snapshots_deleted" in data


def test_run_delete():
    app = create_app()
    client = TestClient(app)

    response = client.delete(f"/api/v2/sessions/runs/{UUID(int=0)}")
    assert response.status_code == 200
    data = response.json()
    assert "approvals_cleared" in data
