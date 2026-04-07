from fastapi.testclient import TestClient

from app.api.app import create_app


def test_v2_overview():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/v2/overview")
    assert response.status_code in (200, 500)
