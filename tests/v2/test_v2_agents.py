from fastapi.testclient import TestClient

from app.api.app import create_app


def test_v2_agents_list():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/v2/agents")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert "total" in data


def test_v2_agent_detail():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/v2/agents/pm")
    assert response.status_code in (200, 404)
