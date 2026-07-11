import uuid

import jwt
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.core.security import PrincipalType, decode_access_token
from app.database import get_db
from app.models.patient import Patient
from app.models.user import User
from app.realtime.manager import manager

router = APIRouter(tags=["realtime"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket, token: str, db: Session = Depends(get_db)
) -> None:
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    principal_type = payload.get("principal_type")
    subject = payload.get("sub")
    if subject is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if principal_type == PrincipalType.user.value:
        user = db.get(User, uuid.UUID(subject))
        if user is None or not user.is_active or user.deleted_at is not None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        kind, recipient_id = PrincipalType.user, user.id
    elif principal_type == PrincipalType.patient.value:
        patient = db.get(Patient, uuid.UUID(subject))
        if patient is None or not patient.is_active or patient.deleted_at is not None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        kind, recipient_id = PrincipalType.patient, patient.id
    else:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(kind, recipient_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(kind, recipient_id, websocket)
