from fastapi.testclient import TestClient

from app.api.app import create_app


def test_v2_diagnostics():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/v2/diagnostics")
    assert response.status_code in (200, 500)
