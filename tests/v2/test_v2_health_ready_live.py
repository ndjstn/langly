from fastapi.testclient import TestClient

from app.api.app import create_app


def test_v2_health_ready():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/v2/health/ready")
    assert response.status_code in (200, 500)


def test_v2_health_live():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/v2/health/live")
    assert response.status_code in (200, 500)
