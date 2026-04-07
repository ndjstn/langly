"""Snapshot store for v2 runtime."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from app.runtime.models import WorkflowState


class SnapshotStore:
    """SQLite-backed state snapshot store."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        default_path = Path("./runtime_v2.db")
        if db_path is None:
            db_env = "./runtime_v2.db"
            try:
                import os
                db_env = os.environ.get("V2_DB_PATH", db_env)
            except Exception:
                db_env = "./runtime_v2.db"
            self._path = Path(db_env)
        else:
            self._path = Path(db_path)
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS state_snapshots (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def save_snapshot(self, snapshot_id: UUID, state: WorkflowState) -> None:
        payload = json.dumps(state.model_dump(mode="json"))
        self._conn.execute(
            "INSERT OR REPLACE INTO state_snapshots (id, session_id, created_at, payload) VALUES (?, ?, ?, ?)",
            (
                str(snapshot_id),
                str(state.session_id),
                datetime.utcnow().isoformat(),
                payload,
            ),
        )
        self._conn.commit()

    def list_snapshots(self, session_id: UUID, limit: int = 20) -> list[dict[str, Any]]:
        cursor = self._conn.execute(
            "SELECT id, created_at, payload FROM state_snapshots WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
            (str(session_id), limit),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "state": json.loads(row["payload"]),
            }
            for row in rows
        ]

    def delete_snapshots(self, session_id: UUID) -> int:
        cursor = self._conn.execute(
            "DELETE FROM state_snapshots WHERE session_id = ?",
            (str(session_id),),
        )
        self._conn.commit()
        return cursor.rowcount
