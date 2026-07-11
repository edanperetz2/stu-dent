import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.direct_message import DirectMessage
from app.models.user import RoleEnum, User
from app.realtime.events import publish
from app.schemas.direct_message import DirectMessageCreate, DirectMessageOut
from app.services.audit import record_audit_log
from app.services.patients import require_confirmed_patient

router = APIRouter(tags=["direct-messages"])


def _get_authorized_patient(db: Session, patient_id: uuid.UUID, current_user: User) -> User:
    patient = db.scalar(
        select(User).where(
            User.id == patient_id, User.role == RoleEnum.patient, User.deleted_at.is_(None)
        )
    )

    is_owning_student = (
        current_user.role == RoleEnum.student
        and patient is not None
        and patient.owner_student_id == current_user.id
    )
    is_self_patient = current_user.role == RoleEnum.patient and current_user.id == patient_id
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DirectMessage:
    patient = _get_authorized_patient(db, patient_id, current_user)
    if current_user.role == RoleEnum.patient:
        require_confirmed_patient(current_user)

    message = DirectMessage(
        patient_id=patient_id,
        body=payload.body,
        sender_id=current_user.id,
    )
    db.add(message)
    db.flush()

    record_audit_log(
        db,
        action="direct_message_create",
        actor_id=current_user.id,
        target_type="direct_message",
        target_id=message.id,
    )

    recipient_id = patient.owner_student_id if current_user.role == RoleEnum.patient else patient.id

    publish(
        db,
        recipient_id=recipient_id,
        event={
            "event": "direct_message",
            "id": str(message.id),
            "patient_id": str(message.patient_id),
            "body": message.body,
            "sender_id": str(message.sender_id),
        },
    )

    db.commit()
    db.refresh(message)
    return message


@router.get("/patients/{patient_id}/messages", response_model=list[DirectMessageOut])
def list_messages(
    patient_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DirectMessage]:
    _get_authorized_patient(db, patient_id, current_user)

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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DirectMessage:
    _get_authorized_patient(db, patient_id, current_user)

    message = db.scalar(
        select(DirectMessage).where(
            DirectMessage.id == message_id, DirectMessage.patient_id == patient_id
        )
    )
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    if message.sender_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the recipient can mark a message read",
        )

    if message.read_at is None:
        message.read_at = datetime.now(UTC)
        db.commit()
        db.refresh(message)
    return message
