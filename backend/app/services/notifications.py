import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationType
from app.models.user import User
from app.realtime.events import publish
from app.services.email import send_email


def notify(
    db: Session,
    *,
    notification_type: NotificationType,
    message: str,
    recipient_id: uuid.UUID,
    related_appointment_id: uuid.UUID | None = None,
    related_patient_id: uuid.UUID | None = None,
) -> Notification:
    """Stage a notification row on `db` without committing, best-effort
    email the recipient, and publish a real-time event for it.

    Callers are expected to commit alongside whatever primary write this
    notification documents, same convention as
    services/audit.py::record_audit_log.
    """
    entry = Notification(
        notification_type=notification_type,
        message=message,
        recipient_id=recipient_id,
        related_appointment_id=related_appointment_id,
        related_patient_id=related_patient_id,
    )
    db.add(entry)
    db.flush()

    recipient = db.get(User, recipient_id)
    if recipient is not None and recipient.email:
        subject = notification_type.value.replace("_", " ").title()
        send_email(to=recipient.email, subject=subject, body=message)

    publish(
        db,
        recipient_id=recipient_id,
        event={
            "event": "notification",
            "id": str(entry.id),
            "notification_type": notification_type.value,
            "message": message,
            "related_appointment_id": (
                str(related_appointment_id) if related_appointment_id is not None else None
            ),
            "related_patient_id": (
                str(related_patient_id) if related_patient_id is not None else None
            ),
        },
    )

    return entry


def resolve_notifications(
    db: Session,
    *,
    notification_type: NotificationType,
    related_appointment_id: uuid.UUID | None = None,
    related_patient_id: uuid.UUID | None = None,
    recipient_id: uuid.UUID | None = None,
) -> None:
    """Mark still-unread "nag until resolved" notifications
    (appointment_needs_resolution, feedback_reminder, appointment_created,
    patient_registration_request) as read once the thing they were nagging
    about actually happens, and push a refresh to each affected recipient's
    connected client.

    Without this, resolving the appointment/feedback/patient-confirmation
    from anywhere other than the notification itself (e.g. the
    Appointments, Feedback, or Patients page directly) left the
    notification sitting there unread and now-false -- "still hasn't been
    marked completed" after it just was. `recipient_id` scopes this to one
    specific person when the notification type can have independent
    per-person outcomes (feedback_reminder: the patient and the attending
    each have their own pending/given state for the same appointment;
    appointment_created's accept/approve are each one specific person's own
    action) -- omit it for types where resolving is a single event for
    everyone regardless of who acted (appointment_needs_resolution: only
    ever the owning student anyway; appointment_created on reject/cancel:
    the appointment is terminal, so nobody's copy is still actionable).

    Exactly one of `related_appointment_id`/`related_patient_id` must be
    given -- whichever this notification type is actually linked by (see
    the Notification model's own comment on `related_patient_id` for why
    patient_registration_request needs the latter, not an appointment).

    Deliberately not the same "notification" realtime event `notify()`
    emits -- that event's payload is a fresh notification's own text, and
    replaying it here would show a stale "still needs resolving" toast for
    the exact moment it stopped being true. `notifications_resolved` is a
    plain refresh signal with no message of its own.
    """
    if (related_appointment_id is None) == (related_patient_id is None):
        raise ValueError(
            "resolve_notifications needs exactly one of related_appointment_id/related_patient_id"
        )

    stmt = select(Notification).where(
        Notification.notification_type == notification_type,
        Notification.read_at.is_(None),
    )
    if related_appointment_id is not None:
        stmt = stmt.where(Notification.related_appointment_id == related_appointment_id)
    if related_patient_id is not None:
        stmt = stmt.where(Notification.related_patient_id == related_patient_id)
    if recipient_id is not None:
        stmt = stmt.where(Notification.recipient_id == recipient_id)

    rows = list(db.scalars(stmt))
    if not rows:
        return

    now = datetime.now(UTC)
    affected_recipients: set[uuid.UUID] = set()
    for row in rows:
        row.read_at = now
        affected_recipients.add(row.recipient_id)
    db.flush()

    for affected_recipient_id in affected_recipients:
        publish(db, recipient_id=affected_recipient_id, event={"event": "notifications_resolved"})
