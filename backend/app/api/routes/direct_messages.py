import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import Principal, get_current_principal
from app.core.security import PrincipalType
from app.database import get_db
from app.models.direct_message import DirectMessage
from app.models.patient import Patient
from app.models.user import RoleEnum
from app.realtime.events import publish
from app.schemas.direct_message import DirectMessageCreate, DirectMessageOut
from app.services.audit import record_audit_log

router = APIRouter(tags=["direct-messages"])


def _get_authorized_patient(db: Session, patient_id: uuid.UUID, principal: Principal) -> Patient:
    patient = db.scalar(
        select(Patient).where(Patient.id == patient_id, Patient.deleted_at.is_(None))
    )

    is_owning_student = (
        principal.kind == PrincipalType.user
        and principal.user.role == RoleEnum.student
        and patient is not None
        and patient.owner_student_id == principal.user.id
    )
    is_self_patient = (
        principal.kind == PrincipalType.patient
        and patient is not None
        and principal.patient.id == patient.id
    )
    if patient is None or not (is_owning_student or is_self_patient):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    return patient


@router.post(
    "/patients/{patient_id}/messages",
    response_model=DirectMessageOut,
    status_code=status.HTTP_201_CREATED,
)
def create_message(
    patient_id: uuid.UUID,
    payload: DirectMessageCreate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> DirectMessage:
    patient = _get_authorized_patient(db, patient_id, principal)

    message = DirectMessage(
        patient_id=patient_id,
        body=payload.body,
        sender_user_id=principal.actor_user_id,
        sender_patient_id=principal.actor_patient_id,
    )
    db.add(message)
    db.flush()

    record_audit_log(
        db,
        action="direct_message_create",
        actor_user_id=principal.actor_user_id,
        actor_patient_id=principal.actor_patient_id,
        target_type="direct_message",
        target_id=message.id,
    )

    if message.sender_user_id is not None:
        recipient_kind, recipient_id = "patient", patient.id
    else:
        recipient_kind, recipient_id = "user", patient.owner_student_id

    publish(
        db,
        kind=recipient_kind,
        recipient_id=recipient_id,
        event={
            "event": "direct_message",
            "id": str(message.id),
            "patient_id": str(message.patient_id),
            "body": message.body,
            "sender_user_id": str(message.sender_user_id) if message.sender_user_id else None,
            "sender_patient_id": (
                str(message.sender_patient_id) if message.sender_patient_id else None
            ),
        },
    )

    db.commit()
    db.refresh(message)
    return message


@router.get("/patients/{patient_id}/messages", response_model=list[DirectMessageOut])
def list_messages(
    patient_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[DirectMessage]:
    _get_authorized_patient(db, patient_id, principal)

    stmt = (
        select(DirectMessage)
        .where(DirectMessage.patient_id == patient_id)
        .order_by(DirectMessage.sequence.asc())
    )
    return list(db.scalars(stmt))


@router.post("/patients/{patient_id}/messages/{message_id}/read", response_model=DirectMessageOut)
def mark_message_read(
    patient_id: uuid.UUID,
    message_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> DirectMessage:
    _get_authorized_patient(db, patient_id, principal)

    message = db.scalar(
        select(DirectMessage).where(
            DirectMessage.id == message_id, DirectMessage.patient_id == patient_id
        )
    )
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    is_recipient = (
        message.sender_user_id is not None and principal.kind == PrincipalType.patient
    ) or (message.sender_patient_id is not None and principal.kind == PrincipalType.user)
    if not is_recipient:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the recipient can mark a message read",
        )

    if message.read_at is None:
        message.read_at = datetime.now(UTC)
        db.commit()
        db.refresh(message)
    return message
