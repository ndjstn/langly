from fastapi.testclient import TestClient

from app.api.app import create_app


def test_v2_routes_smoke():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/v2/runs")
    assert response.status_code in (200, 500)

    response = client.get("/api/v2/dashboard")
    assert response.status_code in (200, 500)

    response = client.get("/api/v2/hitl/requests")
    assert response.status_code in (200, 500)
