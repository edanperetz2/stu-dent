import asyncio
import uuid

import jwt
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models.user import User
from app.realtime.manager import manager

router = APIRouter(tags=["realtime"])

_AUTH_TIMEOUT_SECONDS = 10


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, db: Session = Depends(get_db)) -> None:
    # The token used to be a `?token=` query param -- it ends up in access
    # logs, proxy logs, and browser history that way, and a leaked log line
    # is a replayable bearer token for the rest of its 30-minute life.
    # Accepting first and requiring the token as the first message instead
    # keeps it out of anything that logs the request line/URL.
    await websocket.accept()
    try:
        auth_message = await asyncio.wait_for(
            websocket.receive_json(), timeout=_AUTH_TIMEOUT_SECONDS
        )
    except (TimeoutError, WebSocketDisconnect, ValueError):
        # Distinct from WS_1008_POLICY_VIOLATION below -- this path means no
        # usable auth message arrived at all (a slow/congested connection
        # timing out, a client disconnecting mid-handshake, or malformed
        # JSON), not that a token was actually evaluated and rejected. The
        # frontend (RealtimeContext.tsx) treats 1008 as a hard "your session
        # expired" and logs the user out instead of retrying -- conflating
        # this with a real rejection meant a merely slow connection could
        # trigger an unwanted logout.
        await websocket.close(code=status.WS_1002_PROTOCOL_ERROR)
        return

    token = auth_message.get("token") if isinstance(auth_message, dict) else None
    if not isinstance(token, str):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    subject = payload.get("sub")
    if subject is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user = db.get(User, uuid.UUID(subject))
    if user is None or not user.is_active or user.deleted_at is not None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    user_id = user.id

    # Release the connection now, rather than holding it for the rest of
    # this function -- FastAPI only tears a `Depends(get_db)` session down
    # when the endpoint function returns, and for a WebSocket endpoint
    # that's only once the connection actually closes. Left open, this
    # session's transaction sat idle in transaction for the connection's
    # entire lifetime: any client with the app open in a browser tab held
    # it open for as long as the tab stayed open, which is a real resource
    # leak (idle transactions can block autovacuum) and a real migration
    # hazard -- it blocked a schema migration's `ALTER TABLE` outright
    # during work on this file. Closing explicitly here (safe to call
    # twice -- `get_db`'s own `finally: db.close()` still runs harmlessly
    # once this function eventually returns) is deliberately not the same
    # fix as dropping `Depends(get_db)` in favor of a module-level
    # `SessionLocal` -- that would silently route this connection's DB
    # access around `app.dependency_overrides[get_db]`, which is exactly
    # how the test suite points it at the test database instead of dev.
    db.close()

    await manager.connect(user_id, websocket)
    # Accepting happens before auth now (see above), so a caller can no
    # longer infer "the connection is registered and ready to receive
    # events" just from the socket opening -- this ack gives them (and the
    # test suite, which otherwise had a real race between this and an HTTP
    # call meant to trigger a push) an explicit, unambiguous signal.
    await websocket.send_json({"event": "connected"})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(user_id, websocket)
