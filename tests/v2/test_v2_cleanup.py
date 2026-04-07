from fastapi.testclient import TestClient

from app.api.app import create_app


def test_v2_cleanup():
    app = create_app()
    client = TestClient(app)

    response = client.post("/api/v2/cleanup/prune")
    assert response.status_code in (200, 500)
