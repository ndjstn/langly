"""
WebSocket Endpoints for Langly API.

This module provides real-time WebSocket communication for
workflow streaming, agent updates, and live monitoring.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


# =============================================================================
# Message Types
# =============================================================================


class WSMessageType(str, Enum):
    """Types of WebSocket messages."""

    # Client -> Server
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    WORKFLOW_START = "workflow_start"
    WORKFLOW_CANCEL = "workflow_cancel"
    HUMAN_INPUT = "human_input"
    PING = "ping"

    # Server -> Client
    WORKFLOW_UPDATE = "workflow_update"
    AGENT_UPDATE = "agent_update"
    TASK_UPDATE = "task_update"
    ERROR = "error"
    PONG = "pong"
    CONNECTED = "connected"


class WSMessage(BaseModel):
    """WebSocket message structure."""

    type: WSMessageType
    payload: dict[str, Any] = {}
    timestamp: str = ""

    def __init__(self, **data: Any) -> None:
        """Initialize with current timestamp if not provided."""
        if "timestamp" not in data or not data["timestamp"]:
            data["timestamp"] = datetime.utcnow().isoformat()
        super().__init__(**data)


# =============================================================================
# Connection Manager
# =============================================================================


class ConnectionManager:
    """
    Manages WebSocket connections and broadcasting.

    This class handles:
    - Active connection tracking
    - Subscription management
    - Message broadcasting to specific clients or groups
    """

    def __init__(self) -> None:
        """Initialize the connection manager."""
        # All active connections
        self._connections: dict[str, WebSocket] = {}
        # Subscriptions: topic -> set of connection IDs
        self._subscriptions: dict[str, set[str]] = {}
        # Connection -> subscriptions
        self._connection_subscriptions: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
        connection_id: str,
    ) -> None:
        """
        Accept a new WebSocket connection.

        Args:
            websocket: The WebSocket connection.
            connection_id: Unique identifier for this connection.
        """
        await websocket.accept()
        async with self._lock:
            self._connections[connection_id] = websocket
            self._connection_subscriptions[connection_id] = set()

        logger.info(f"WebSocket connected: {connection_id}")

        # Send connection confirmation
        await self.send_personal_message(
            connection_id,
            WSMessage(
                type=WSMessageType.CONNECTED,
                payload={"connection_id": connection_id},
            ),
        )

    async def disconnect(self, connection_id: str) -> None:
        """
        Handle WebSocket disconnection.

        Args:
            connection_id: The connection to disconnect.
        """
        async with self._lock:
            # Remove from all subscriptions
            if connection_id in self._connection_subscriptions:
                for topic in self._connection_subscriptions[connection_id]:
                    if topic in self._subscriptions:
                        self._subscriptions[topic].discard(connection_id)
                del self._connection_subscriptions[connection_id]

            # Remove connection
            if connection_id in self._connections:
                del self._connections[connection_id]

        logger.info(f"WebSocket disconnected: {connection_id}")

    async def subscribe(self, connection_id: str, topic: str) -> None:
        """
        Subscribe a connection to a topic.

        Args:
            connection_id: The connection to subscribe.
            topic: The topic to subscribe to.
        """
        async with self._lock:
            if topic not in self._subscriptions:
                self._subscriptions[topic] = set()
            self._subscriptions[topic].add(connection_id)

            if connection_id in self._connection_subscriptions:
                self._connection_subscriptions[connection_id].add(topic)

        logger.debug(f"Connection {connection_id} subscribed to {topic}")

    async def unsubscribe(self, connection_id: str, topic: str) -> None:
        """
        Unsubscribe a connection from a topic.

        Args:
            connection_id: The connection to unsubscribe.
            topic: The topic to unsubscribe from.
        """
        async with self._lock:
            if topic in self._subscriptions:
                self._subscriptions[topic].discard(connection_id)

            if connection_id in self._connection_subscriptions:
                self._connection_subscriptions[connection_id].discard(topic)

        logger.debug(f"Connection {connection_id} unsubscribed from {topic}")

    async def send_personal_message(
        self,
        connection_id: str,
        message: WSMessage,
    ) -> bool:
        """
        Send a message to a specific connection.

        Args:
            connection_id: The target connection.
            message: The message to send.

        Returns:
            True if message was sent successfully.
        """
        if connection_id not in self._connections:
            return False

        try:
            websocket = self._connections[connection_id]
            await websocket.send_text(message.model_dump_json())
            return True
        except Exception as e:
            logger.error(f"Failed to send message to {connection_id}: {e}")
            return False

    async def broadcast_to_topic(
        self,
        topic: str,
        message: WSMessage,
    ) -> int:
        """
        Broadcast a message to all subscribers of a topic.

        Args:
            topic: The topic to broadcast to.
            message: The message to broadcast.

        Returns:
            Number of connections that received the message.
        """
        if topic not in self._subscriptions:
            return 0

        sent_count = 0
        message_json = message.model_dump_json()

        # Get copy of subscribers to avoid lock issues
        async with self._lock:
            subscribers = list(self._subscriptions.get(topic, set()))

        for connection_id in subscribers:
            if connection_id in self._connections:
                try:
                    await self._connections[connection_id].send_text(
                        message_json
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(
                        f"Failed to broadcast to {connection_id}: {e}"
                    )

        return sent_count

    async def broadcast_all(self, message: WSMessage) -> int:
        """
        Broadcast a message to all connected clients.

        Args:
            message: The message to broadcast.

        Returns:
            Number of connections that received the message.
        """
        sent_count = 0
        message_json = message.model_dump_json()

        async with self._lock:
            connection_ids = list(self._connections.keys())

        for connection_id in connection_ids:
            if connection_id in self._connections:
                try:
                    await self._connections[connection_id].send_text(
                        message_json
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(
                        f"Failed to broadcast to {connection_id}: {e}"
                    )

        return sent_count

    def get_connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self._connections)

    def get_topic_subscribers(self, topic: str) -> int:
        """Get the number of subscribers to a topic."""
        return len(self._subscriptions.get(topic, set()))


# Global connection manager instance
manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance."""
    return manager


# =============================================================================
# WebSocket Endpoints
# =============================================================================


@router.websocket("/workflow/{workflow_id}")
async def workflow_websocket(websocket: WebSocket, workflow_id: str) -> None:
    """
    WebSocket endpoint for workflow-specific updates.

    Clients connect to this endpoint to receive real-time updates
    about a specific workflow execution.

    Args:
        websocket: The WebSocket connection.
        workflow_id: The ID of the workflow to monitor.
    """
    connection_id = f"workflow_{workflow_id}_{id(websocket)}"

    await manager.connect(websocket, connection_id)
    await manager.subscribe(connection_id, f"workflow:{workflow_id}")

    try:
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                msg_type = message.get("type", "")

                if msg_type == WSMessageType.PING.value:
                    await manager.send_personal_message(
                        connection_id,
                        WSMessage(type=WSMessageType.PONG, payload={}),
                    )

                elif msg_type == WSMessageType.HUMAN_INPUT.value:
                    # Handle human input for the workflow
                    payload = message.get("payload", {})
                    logger.info(
                        f"Received human input for workflow {workflow_id}: "
                        f"{payload}"
                    )
                    # TODO: Process human input through workflow manager

                elif msg_type == WSMessageType.WORKFLOW_CANCEL.value:
                    # Handle workflow cancellation
                    logger.info(
                        f"Received cancel request for workflow {workflow_id}"
                    )
                    # TODO: Cancel workflow through workflow manager

            except json.JSONDecodeError:
                await manager.send_personal_message(
                    connection_id,
                    WSMessage(
                        type=WSMessageType.ERROR,
                        payload={"error": "Invalid JSON message"},
                    ),
                )

    except WebSocketDisconnect:
        await manager.disconnect(connection_id)


@router.websocket("/agents")
async def agents_websocket(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for agent status updates.

    Clients connect to this endpoint to receive real-time updates
    about all agent statuses.

    Args:
        websocket: The WebSocket connection.
    """
    connection_id = f"agents_{id(websocket)}"

    await manager.connect(websocket, connection_id)
    await manager.subscribe(connection_id, "agents:all")

    try:
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                msg_type = message.get("type", "")

                if msg_type == WSMessageType.PING.value:
                    await manager.send_personal_message(
                        connection_id,
                        WSMessage(type=WSMessageType.PONG, payload={}),
                    )

                elif msg_type == WSMessageType.SUBSCRIBE.value:
                    topic = message.get("payload", {}).get("topic", "")
                    if topic:
                        await manager.subscribe(connection_id, topic)

                elif msg_type == WSMessageType.UNSUBSCRIBE.value:
                    topic = message.get("payload", {}).get("topic", "")
                    if topic:
                        await manager.unsubscribe(connection_id, topic)

            except json.JSONDecodeError:
                await manager.send_personal_message(
                    connection_id,
                    WSMessage(
                        type=WSMessageType.ERROR,
                        payload={"error": "Invalid JSON message"},
                    ),
                )

    except WebSocketDisconnect:
        await manager.disconnect(connection_id)


@router.websocket("/stream")
async def stream_websocket(websocket: WebSocket) -> None:
    """
    General-purpose WebSocket for streaming all platform updates.

    This endpoint provides a unified stream of all platform events
    including workflows, agents, and system status.

    Args:
        websocket: The WebSocket connection.
    """
    connection_id = f"stream_{id(websocket)}"

    await manager.connect(websocket, connection_id)

    try:
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                msg_type = message.get("type", "")

                if msg_type == WSMessageType.PING.value:
                    await manager.send_personal_message(
                        connection_id,
                        WSMessage(type=WSMessageType.PONG, payload={}),
                    )

                elif msg_type == WSMessageType.SUBSCRIBE.value:
                    topic = message.get("payload", {}).get("topic", "")
                    if topic:
                        await manager.subscribe(connection_id, topic)
                        await manager.send_personal_message(
                            connection_id,
                            WSMessage(
                                type=WSMessageType.WORKFLOW_UPDATE,
                                payload={
                                    "status": "subscribed",
                                    "topic": topic,
                                },
                            ),
                        )

                elif msg_type == WSMessageType.UNSUBSCRIBE.value:
                    topic = message.get("payload", {}).get("topic", "")
                    if topic:
                        await manager.unsubscribe(connection_id, topic)
                        await manager.send_personal_message(
                            connection_id,
                            WSMessage(
                                type=WSMessageType.WORKFLOW_UPDATE,
                                payload={
                                    "status": "unsubscribed",
                                    "topic": topic,
                                },
                            ),
                        )

                elif msg_type == WSMessageType.WORKFLOW_START.value:
                    # Handle workflow start request
                    payload = message.get("payload", {})
                    logger.info(f"Workflow start request: {payload}")
                    # TODO: Trigger workflow through workflow manager

            except json.JSONDecodeError:
                await manager.send_personal_message(
                    connection_id,
                    WSMessage(
                        type=WSMessageType.ERROR,
                        payload={"error": "Invalid JSON message"},
                    ),
                )

    except WebSocketDisconnect:
        await manager.disconnect(connection_id)


# =============================================================================
# Helper Functions for Broadcasting
# =============================================================================


async def broadcast_workflow_update(
    workflow_id: str,
    status: str,
    data: dict[str, Any],
) -> int:
    """
    Broadcast a workflow update to all subscribers.

    Args:
        workflow_id: The workflow ID.
        status: The new status.
        data: Additional data to include.

    Returns:
        Number of connections notified.
    """
    message = WSMessage(
        type=WSMessageType.WORKFLOW_UPDATE,
        payload={
            "workflow_id": workflow_id,
            "status": status,
            **data,
        },
    )
    return await manager.broadcast_to_topic(f"workflow:{workflow_id}", message)


async def broadcast_agent_update(
    agent_type: str,
    status: str,
    data: dict[str, Any],
) -> int:
    """
    Broadcast an agent update to all subscribers.

    Args:
        agent_type: The type of agent.
        status: The new status.
        data: Additional data to include.

    Returns:
        Number of connections notified.
    """
    message = WSMessage(
        type=WSMessageType.AGENT_UPDATE,
        payload={
            "agent_type": agent_type,
            "status": status,
            **data,
        },
    )
    return await manager.broadcast_to_topic("agents:all", message)


async def broadcast_task_update(
    task_id: str,
    workflow_id: str,
    status: str,
    data: dict[str, Any],
) -> int:
    """
    Broadcast a task update to workflow subscribers.

    Args:
        task_id: The task ID.
        workflow_id: The parent workflow ID.
        status: The new status.
        data: Additional data to include.

    Returns:
        Number of connections notified.
    """
    message = WSMessage(
        type=WSMessageType.TASK_UPDATE,
        payload={
            "task_id": task_id,
            "workflow_id": workflow_id,
            "status": status,
            **data,
        },
    )
    return await manager.broadcast_to_topic(f"workflow:{workflow_id}", message)
