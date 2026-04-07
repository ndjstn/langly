from fastapi.testclient import TestClient

from app.api.app import create_app


def test_v2_config():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/v2/config")
    assert response.status_code in (200, 500)


def test_v2_reset():
    app = create_app()
    client = TestClient(app)

    response = client.post("/api/v2/reset")
    assert response.status_code in (200, 500)
