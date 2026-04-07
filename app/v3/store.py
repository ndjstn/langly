"""Async event store for V3."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import aiosqlite

from app.v3.models import Run, RunStatus, StateDelta


class AsyncEventStore:
    """SQLite-backed async store for runs and deltas."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        default_path = Path("./runtime_v3.db")
        if db_path is None:
            db_env = os.environ.get("V3_DB_PATH", str(default_path))
            self._path = Path(db_env)
        else:
            self._path = Path(db_path)
        self._initialized = False

    async def _ensure_schema(self) -> None:
        if self._initialized:
            return
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    result TEXT,
                    error TEXT,
                    metadata TEXT
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS deltas (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            await db.commit()
        self._initialized = True

    async def save_run(self, run: Run) -> None:
        await self._ensure_schema()
        payload = (
            json.dumps(run.result, default=str)
            if run.result is not None
            else None
        )
        metadata = json.dumps(run.metadata, default=str) if run.metadata else None
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO runs
                (id, session_id, status, created_at, updated_at, result, error, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(run.id),
                    str(run.session_id),
                    run.status.value,
                    run.created_at.isoformat(),
                    run.updated_at.isoformat(),
                    payload,
                    run.error,
                    metadata,
                ),
            )
            await db.commit()

    async def update_run(
        self,
        run_id: UUID,
        status: RunStatus,
        result: dict[str, Any] | None,
        error: str | None,
    ) -> None:
        await self._ensure_schema()
        payload = json.dumps(result, default=str) if result is not None else None
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                """
                UPDATE runs
                SET status = ?, updated_at = ?, result = ?, error = ?
                WHERE id = ?
                """,
                (
                    status.value,
                    datetime.utcnow().isoformat(),
                    payload,
                    error,
                    str(run_id),
                ),
            )
            await db.commit()

    async def save_delta(self, delta: StateDelta) -> None:
        await self._ensure_schema()
        payload = json.dumps(delta.model_dump(mode="json"))
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO deltas
                (id, run_id, node_id, kind, created_at, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(delta.id),
                    str(delta.run_id),
                    delta.node_id,
                    delta.kind.value,
                    delta.created_at.isoformat(),
                    payload,
                ),
            )
            await db.commit()

    async def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        await self._ensure_schema()
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT id, session_id, status, created_at, updated_at, result, error, metadata
                FROM runs ORDER BY created_at DESC LIMIT ?
                """,
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            results.append(
                {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "result": json.loads(row["result"]) if row["result"] else None,
                    "error": row["error"],
                    "metadata": (
                        json.loads(row["metadata"]) if row["metadata"] else {}
                    ),
                }
            )
        return results

    async def list_deltas(self, run_id: UUID) -> list[dict[str, Any]]:
        await self._ensure_schema()
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT payload FROM deltas
                WHERE run_id = ? ORDER BY created_at ASC
                """,
                (str(run_id),),
            ) as cursor:
                rows = await cursor.fetchall()
        return [json.loads(row["payload"]) for row in rows]

    async def get_run(self, run_id: UUID) -> dict[str, Any] | None:
        await self._ensure_schema()
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT id, session_id, status, created_at, updated_at, result, error, metadata
                FROM runs WHERE id = ?
                """,
                (str(run_id),),
            ) as cursor:
                row = await cursor.fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "session_id": row["session_id"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "result": json.loads(row["result"]) if row["result"] else None,
            "error": row["error"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
        }
