import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import Principal, get_current_principal
from app.core.security import PrincipalType
from app.database import get_db
from app.models.notification import Notification
from app.schemas.notification import NotificationOut

router = APIRouter(tags=["notifications"])


def _recipient_filter(principal: Principal):
    if principal.kind == PrincipalType.patient:
        return Notification.recipient_patient_id == principal.patient.id
    return Notification.recipient_user_id == principal.user.id


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = False,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[Notification]:
    stmt = select(Notification).where(_recipient_filter(principal))
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    stmt = stmt.order_by(Notification.sequence.desc())
    return list(db.scalars(stmt))


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> Notification:
    notification = db.scalar(
        select(Notification).where(Notification.id == notification_id, _recipient_filter(principal))
    )
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        db.commit()
        db.refresh(notification)
    return notification
