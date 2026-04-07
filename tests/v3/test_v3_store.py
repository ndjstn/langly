import pytest
from uuid import uuid4

from app.v3.models import DeltaKind, Run, RunStatus, StateDelta
from app.v3.store import AsyncEventStore


@pytest.mark.asyncio
async def test_v3_store_roundtrip(tmp_path) -> None:
    db_path = tmp_path / "runtime_v3.db"
    store = AsyncEventStore(db_path=db_path)

    run = Run(session_id=uuid4(), status=RunStatus.RUNNING)
    await store.save_run(run)
    await store.update_run(run.id, RunStatus.COMPLETED, {"ok": True}, None)

    runs = await store.list_runs()
    assert len(runs) == 1
    assert runs[0]["status"] == RunStatus.COMPLETED.value

    delta = StateDelta(
        run_id=run.id,
        node_id="test",
        kind=DeltaKind.USER_INPUT,
        changes={"message": "hi"},
    )
    await store.save_delta(delta)

    deltas = await store.list_deltas(run.id)
    assert len(deltas) == 1
    assert deltas[0]["changes"]["message"] == "hi"

    fetched = await store.get_run(run.id)
    assert fetched is not None
    assert fetched["id"] == str(run.id)
