"""
OpsPilot — WebSocket Connection and Presence Manager.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from app.core.metrics import active_ws_connections
from app.websocket.connection import ActiveConnection

logger = logging.getLogger("opspilot.websocket.manager")


class WebSocketManager:
    """Manages active WebSocket connections and staff presence tracking."""

    def __init__(self) -> None:
        # Maps business_id -> list of ActiveConnection objects
        self._connections: dict[str, list[ActiveConnection]] = defaultdict(list)
        # Maps business_id -> user_id -> presence details (e.g. status, active_view)
        self._presence: dict[str, dict[str, dict[str, Any]]] = defaultdict(lambda: defaultdict(dict))

    def connect(self, connection: ActiveConnection) -> None:
        """Register an active connection and set default presence status to online."""
        b_id = str(connection.business_id)
        u_id = str(connection.user_id)
        self._connections[b_id].append(connection)
        self._presence[b_id][u_id] = {
            "user_id": u_id,
            "status": "online",
            "current_view": None,
        }
        active_ws_connections.labels(business_id=b_id).inc()
        logger.info("User %s connected in business %s", u_id, b_id)

    def disconnect(self, connection: ActiveConnection) -> None:
        """De-register a connection and clean up presence."""
        b_id = str(connection.business_id)
        u_id = str(connection.user_id)
        if connection in self._connections[b_id]:
            self._connections[b_id].remove(connection)
        if u_id in self._presence[b_id]:
            del self._presence[b_id][u_id]
        active_ws_connections.labels(business_id=b_id).dec()
        logger.info("User %s disconnected from business %s", u_id, b_id)

    def update_presence(self, business_id: str, user_id: str, status: str, current_view: str | None = None) -> None:
        """Update active view/status details for a workspace user."""
        b_id = str(business_id)
        u_id = str(user_id)
        if u_id in self._presence[b_id]:
            self._presence[b_id][u_id]["status"] = status
            self._presence[b_id][u_id]["current_view"] = current_view
            logger.debug("Presence updated for user %s: %s (view: %s)", u_id, status, current_view)

    def get_presence(self, business_id: str) -> list[dict[str, Any]]:
        """Return all active presence details for a business."""
        return list(self._presence[str(business_id)].values())

    async def broadcast_to_business(self, business_id: str, event_type: str, payload: dict[str, Any]) -> None:
        """Emit a formatted message to all active WebSocket clients of a business."""
        b_id = str(business_id)
        connections = self._connections.get(b_id, [])
        if not connections:
            return

        message = {
            "event": event_type,
            "business_id": b_id,
            "payload": payload,
        }

        # Send concurrently to all active business connections
        import asyncio

        disconnected = []

        async def send(conn: ActiveConnection) -> None:
            success = await conn.send_json(message)
            if not success:
                disconnected.append(conn)

        await asyncio.gather(*(send(conn) for conn in connections))

        # Cleanup any stale connections detected during send
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_to_user(self, business_id: str, user_id: str, event_type: str, payload: dict[str, Any]) -> None:
        """Target a message specifically to a user in a given business."""
        b_id = str(business_id)
        u_id = str(user_id)
        connections = [c for c in self._connections.get(b_id, []) if c.user_id == u_id]
        if not connections:
            return

        message = {
            "event": event_type,
            "business_id": b_id,
            "payload": payload,
        }

        import asyncio

        disconnected = []

        async def send(conn: ActiveConnection) -> None:
            success = await conn.send_json(message)
            if not success:
                disconnected.append(conn)

        await asyncio.gather(*(send(conn) for conn in connections))

        # Cleanup
        for conn in disconnected:
            self.disconnect(conn)


# Singleton manager
ws_manager = WebSocketManager()
