"""Persistent run store for v2 (SQLite)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from app.runtime.models import RunStatus, WorkflowRun


class RunStore:
    """SQLite-backed store for run metadata and deltas."""

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
            CREATE TABLE IF NOT EXISTS run_deltas (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                node TEXT NOT NULL,
                created_at TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                result TEXT,
                error TEXT
            )
            """
        )
        self._conn.commit()

    def save_run(self, run: WorkflowRun) -> None:
        payload = json.dumps(run.result, default=str) if run.result is not None else None
        self._conn.execute(
            """
            INSERT OR REPLACE INTO runs (id, session_id, status, created_at, updated_at, result, error)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(run.id),
                str(run.session_id),
                run.status.value,
                run.created_at.isoformat(),
                run.updated_at.isoformat(),
                payload,
                run.error,
            ),
        )
        self._conn.commit()

    def update_run(
        self,
        run_id: UUID,
        status: RunStatus,
        result: dict | None,
        error: str | None,
    ) -> None:
        payload = json.dumps(result, default=str) if result is not None else None
        self._conn.execute(
            """
            UPDATE runs SET status = ?, updated_at = ?, result = ?, error = ? WHERE id = ?
            """,
            (
                status.value,
                datetime.utcnow().isoformat(),
                payload,
                error,
                str(run_id),
            ),
        )
        self._conn.commit()

    def save_delta(self, delta: dict[str, Any]) -> None:
        payload = json.dumps(delta, default=str)
        delta_id = delta.get("id")
        run_id = delta.get("run_id")
        created_at = delta.get("created_at")
        self._conn.execute(
            "INSERT OR REPLACE INTO run_deltas (id, run_id, node, created_at, payload) VALUES (?, ?, ?, ?, ?)",
            (
                str(delta_id) if delta_id is not None else None,
                str(run_id) if run_id is not None else None,
                delta.get("node"),
                str(created_at) if created_at is not None else None,
                payload,
            ),
        )
        self._conn.commit()

    def list_deltas(self, run_id: UUID) -> list[dict[str, Any]]:
        cursor = self._conn.execute(
            "SELECT payload FROM run_deltas WHERE run_id = ? ORDER BY created_at ASC",
            (str(run_id),),
        )
        rows = cursor.fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        cursor = self._conn.execute(
            "SELECT id, session_id, status, created_at, updated_at, result, error FROM runs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
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
                }
            )
        return results

    def delete_runs_for_session(self, session_id: UUID) -> list[str]:
        cursor = self._conn.execute(
            "SELECT id FROM runs WHERE session_id = ?",
            (str(session_id),),
        )
        run_ids = [row["id"] for row in cursor.fetchall()]
        self._conn.execute(
            "DELETE FROM runs WHERE session_id = ?",
            (str(session_id),),
        )
        self._conn.commit()
        return run_ids

    def delete_deltas_for_runs(self, run_ids: list[str]) -> int:
        if not run_ids:
            return 0
        placeholders = ",".join(["?"] * len(run_ids))
        cursor = self._conn.execute(
            f"DELETE FROM run_deltas WHERE run_id IN ({placeholders})",
            run_ids,
        )
        self._conn.commit()
        return cursor.rowcount

    def delete_run(self, run_id: UUID) -> None:
        self._conn.execute("DELETE FROM runs WHERE id = ?", (str(run_id),))
        self._conn.commit()

    def list_runs_for_session(
        self,
        session_id: UUID,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        cursor = self._conn.execute(
            "SELECT id, session_id, status, created_at, updated_at, result, error FROM runs WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
            (str(session_id), limit),
        )
        rows = cursor.fetchall()
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
                }
            )
        return results

    def get_run(self, run_id: UUID) -> dict[str, Any] | None:
        cursor = self._conn.execute(
            "SELECT id, session_id, status, created_at, updated_at, result, error FROM runs WHERE id = ?",
            (str(run_id),),
        )
        row = cursor.fetchone()
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
        }

    def get_run_summary(self, run_id: UUID) -> dict[str, Any]:
        deltas = self.list_deltas(run_id)
        tool_calls = 0
        tasks = 0
        for delta in deltas:
            changes = delta.get("changes", {})
            tool_calls += len(changes.get("tool_calls", []) or [])
            tasks = max(tasks, len(changes.get("tasks", []) or []))
        return {
            "tool_calls": tool_calls,
            "tasks": tasks,
        }
