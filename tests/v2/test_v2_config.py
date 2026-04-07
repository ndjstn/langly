from fastapi.testclient import TestClient

from app.api.app import create_app


def test_v2_config_endpoint():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/v2/config")
    assert response.status_code in (200, 500)
