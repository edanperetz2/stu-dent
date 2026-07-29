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
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
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

    await manager.connect(user.id, websocket)
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
        await manager.disconnect(user.id, websocket)
