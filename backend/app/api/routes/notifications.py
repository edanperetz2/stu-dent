import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationOut, UnreadCountOut

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=30, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Notification]:
    stmt = select(Notification).where(Notification.recipient_id == current_user.id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    stmt = stmt.order_by(Notification.sequence.desc()).offset(offset).limit(limit)
    return list(db.scalars(stmt))


@router.get("/notifications/unread-count", response_model=UnreadCountOut)
def get_unread_notification_count(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> UnreadCountOut:
    # A real COUNT query, not `len(list_notifications(..., limit=huge))` --
    # same reasoning as messages/unread-count: the badge shouldn't have to
    # transfer every unread row just to report how many there are, and
    # shouldn't silently undercount past whatever page size the list
    # endpoint happens to use.
    count = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.recipient_id == current_user.id, Notification.read_at.is_(None))
    )
    return UnreadCountOut(count=count or 0)


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
