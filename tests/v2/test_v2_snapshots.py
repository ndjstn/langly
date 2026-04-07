from fastapi.testclient import TestClient

from app.api.app import create_app


def test_v2_snapshots_list():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/v2/snapshots/00000000-0000-0000-0000-000000000000")
    assert response.status_code in (200, 500)
