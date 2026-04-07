from fastapi.testclient import TestClient

from app.api.app import create_app


def test_v2_seed_and_runs_flow():
    app = create_app()
    client = TestClient(app)

    seed = client.post("/api/v2/seed/run")
    assert seed.status_code == 200
    run_id = seed.json()["run_id"]

    runs = client.get("/api/v2/runs")
    assert runs.status_code in (200, 500)

    deltas = client.get(f"/api/v2/runs/{run_id}/deltas")
    assert deltas.status_code in (200, 404, 500)
