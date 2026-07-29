import asyncio
import uuid
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    """In-process registry of live WebSocket connections, keyed by recipient
    user id.

    One user can have multiple connections open at once (multiple tabs or
    devices); `send_to` fans out to all of them. Purely in-memory -- this
    app runs a single `api` process, so that's sufficient for connections
    made through this process. The Postgres LISTEN/NOTIFY bridge
    (`realtime/listener.py`) is what lets events originating in the separate
    `worker` process still reach connections registered here.
    """

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, recipient_id: uuid.UUID, websocket: WebSocket) -> None:
        # The caller (api/routes/websocket.py) accepts the connection itself,
        # before authenticating -- it needs to receive the client's first
        # message (the auth token) to get that far, which requires the
        # handshake already accepted.
        key = str(recipient_id)
        async with self._lock:
            self._connections[key].add(websocket)

    async def disconnect(self, recipient_id: uuid.UUID, websocket: WebSocket) -> None:
        key = str(recipient_id)
        async with self._lock:
            self._connections[key].discard(websocket)
            if not self._connections[key]:
                del self._connections[key]

    async def send_to(self, recipient_id: str, payload: dict) -> None:
        async with self._lock:
            sockets = list(self._connections.get(recipient_id, ()))
        for socket in sockets:
            try:
                await socket.send_json(payload)
            except Exception:
                # Best-effort push: a dead socket is cleaned up separately by
                # its own receive-loop's disconnect handler, not here.
                pass


manager = ConnectionManager()
