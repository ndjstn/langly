"""Harness status event emitter."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.runtime.events import EventBus


@dataclass
class HarnessStatusEmitter:
    bus: EventBus
    request_id: str
    loop: asyncio.AbstractEventLoop
    session_id: str | None = None
    run_id: str | None = None

    def set_run(self, run_id: str | None, session_id: str | None) -> None:
        self.run_id = run_id
        self.session_id = session_id

    async def emit(
        self,
        stage: str,
        status: str,
        *,
        detail: dict[str, Any] | None = None,
        progress: float | None = None,
    ) -> None:
        event = {
            "type": "harness_status",
            "request_id": self.request_id,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "stage": stage,
            "status": status,
            "detail": detail or {},
            "progress": progress,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self.bus.publish(event)

    def emit_sync(
        self,
        stage: str,
        status: str,
        *,
        detail: dict[str, Any] | None = None,
        progress: float | None = None,
    ) -> None:
        asyncio.run_coroutine_threadsafe(
            self.emit(stage, status, detail=detail, progress=progress),
            self.loop,
        )

    def emit_token_sync(
        self,
        *,
        token: str,
        role: str,
        stage: str,
        iteration: int | None = None,
    ) -> None:
        event = {
            "type": "harness_token",
            "request_id": self.request_id,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "role": role,
            "stage": stage,
            "iteration": iteration,
            "token": token,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        asyncio.run_coroutine_threadsafe(
            self.bus.publish(event),
            self.loop,
        )
