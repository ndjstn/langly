"""V3 event stream endpoints (WebSocket)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.v3.events import get_event_bus


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["events-v3"])


@router.websocket("/deltas")
async def stream_deltas(websocket: WebSocket) -> None:
    await websocket.accept()
    bus = get_event_bus()
    queue = await bus.subscribe()
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        logger.info("v3 delta stream disconnected")
    finally:
        await bus.unsubscribe(queue)
