"""
Real-Time Agent Event Broadcaster & Activity Tracker
=====================================================
Dispatches real-time events (thoughts, tool calls, tool results, errors)
to connected WebSockets and the Management Center UI.
"""

import time
import asyncio
import json
from typing import List, Dict, Any, Callable
from fastapi import WebSocket


class EventBroadcaster:
    """Manages active WebSocket connections and event streaming for the agent."""

    def __init__(self):
        self.active_websockets: List[WebSocket] = []
        self.subscribers: List[asyncio.Queue] = []
        self.recent_events: List[Dict[str, Any]] = []
        self._max_recent = 200

    async def connect(self, websocket: WebSocket):
        """Accepts and registers a new WebSocket client."""
        await websocket.accept()
        self.active_websockets.append(websocket)

    async def disconnect(self, websocket: WebSocket):
        """Removes a disconnected WebSocket client."""
        if websocket in self.active_websockets:
            self.active_websockets.remove(websocket)

    def subscribe(self) -> asyncio.Queue:
        """Registers a queue subscriber."""
        q = asyncio.Queue()
        self.subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        """Removes a queue subscriber."""
        if q in self.subscribers:
            self.subscribers.remove(q)

    async def emit(self, event_type: str, data: Any):
        """
        Broadcasts an event payload to all active WebSockets and subscribers.
        """
        payload = {
            "type": event_type,
            "data": data,
            "timestamp": time.strftime("%H:%M:%S")
        }
        self.recent_events.append(payload)
        if len(self.recent_events) > self._max_recent:
            self.recent_events.pop(0)

        # Broadcast directly to open WebSockets
        for ws in list(self.active_websockets):
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                if ws in self.active_websockets:
                    self.active_websockets.remove(ws)

        # Broadcast to queue subscribers
        for q in list(self.subscribers):
            try:
                await q.put(payload)
            except Exception:
                pass


# Global singleton broadcaster
broadcaster = EventBroadcaster()
