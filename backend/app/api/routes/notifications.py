import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationOut

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Notification]:
    stmt = select(Notification).where(Notification.recipient_id == current_user.id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    # Defensive cap, not full pagination (out of scope for this fix) --
    # notifications are never hard-deleted, so this list grows monotonically
    # for the life of a single account.
    stmt = stmt.order_by(Notification.sequence.desc()).limit(500)
    return list(db.scalars(stmt))


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Notification:
    notification = db.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.recipient_id == current_user.id
        )
    )
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        db.commit()
        db.refresh(notification)
    return notification


@router.post("/notifications/{notification_id}/unread", response_model=NotificationOut)
def mark_notification_unread(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Notification:
    notification = db.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.recipient_id == current_user.id
        )
    )
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    if notification.read_at is not None:
        notification.read_at = None
        db.commit()
        db.refresh(notification)
    return notification
