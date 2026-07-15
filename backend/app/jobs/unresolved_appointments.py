from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.appointment import Appointment
from app.models.notification import Notification, NotificationType
from app.services.formatting import format_dt
from app.services.notifications import notify
from app.services.scheduling import TERMINAL_STATUSES


def notify_unresolved_past_appointments(db: Session) -> int:
    """Nag the owning student about an appointment that's well past its own
    end_time but was never resolved to a real terminal outcome (completed/
    cancelled/no_show) -- the confirmed-and-forgotten case this project's
    planned feedback feature depends on not existing. Re-fires every
    `unresolved_appointment_grace_hours` for as long as it stays
    unresolved, by checking for a matching notification already sent within
    that same window (same "count/check recent rows" idiom as
    core/rate_limit.py::enforce_login_rate_limit, rather than a one-shot
    column like reminders.py's `reminder_sent_at` -- this one must genuinely
    repeat). Commits per appointment so one bad row doesn't block the rest
    of the batch, same convention as jobs/expiry.py.
    """
    now = datetime.now(UTC)
    grace = timedelta(hours=settings.unresolved_appointment_grace_hours)
    window_start = now - grace

    candidates = list(
        db.scalars(
            select(Appointment).where(
                Appointment.status.notin_(TERMINAL_STATUSES),
                Appointment.end_time <= now - grace,
            )
        )
    )

    notified = 0
    for appointment in candidates:
        already_notified = db.scalar(
            select(Notification.id)
            .where(
                Notification.related_appointment_id == appointment.id,
                Notification.notification_type == NotificationType.appointment_needs_resolution,
                Notification.created_at >= window_start,
            )
            .limit(1)
        )
        if already_notified is not None:
            continue

        notify(
            db,
            notification_type=NotificationType.appointment_needs_resolution,
            message=(
                f"Your appointment on {format_dt(appointment.start_time)} still hasn't "
                "been marked completed, no-show, or cancelled -- please resolve it or "
                "edit its details."
            ),
            recipient_id=appointment.student_id,
            related_appointment_id=appointment.id,
        )
        db.commit()
        notified += 1

    return notified
