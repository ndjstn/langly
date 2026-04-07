from uuid import uuid4

from app.runtime.run_store import RunStore


def test_run_store_roundtrip(tmp_path):
    db_path = tmp_path / "runtime.db"
    store = RunStore(db_path=db_path)

    run_id = uuid4()
    deltas = store.list_deltas(run_id)
    assert deltas == []
