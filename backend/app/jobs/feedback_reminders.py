from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.appointment import Appointment, AppointmentStatus
from app.models.feedback import Feedback
from app.models.notification import Notification, NotificationType
from app.services.formatting import format_dt
from app.services.notifications import notify


def notify_pending_feedback(db: Session) -> int:
    """Nag the patient (and attending, if one was assigned) to leave
    feedback for the treating student on a completed appointment -- same
    "recent-row check enables indefinite re-fire every window" idiom as
    jobs/unresolved_appointments.py, so it keeps nudging every
    `feedback_reminder_grace_hours` for as long as that specific person
    hasn't submitted feedback for that specific appointment. Once they do,
    their `Feedback` row removes them from "pending authors" on the next run
    -- the other party (if still pending) keeps getting nagged independently.
    """
    now = datetime.now(UTC)
    grace = timedelta(hours=settings.feedback_reminder_grace_hours)
    window_start = now - grace

    candidates = list(
        db.scalars(
            select(Appointment).where(
                Appointment.status == AppointmentStatus.completed,
                Appointment.end_time <= now - grace,
            )
        )
    )

    notified = 0
    for appointment in candidates:
        already_given = set(
            db.scalars(select(Feedback.author_id).where(Feedback.appointment_id == appointment.id))
        )
        pending_authors = {appointment.patient_id}
        if appointment.attending_id is not None:
            pending_authors.add(appointment.attending_id)
        pending_authors -= already_given

        for author_id in pending_authors:
            already_notified = db.scalar(
                select(Notification.id)
                .where(
                    Notification.recipient_id == author_id,
                    Notification.related_appointment_id == appointment.id,
                    Notification.notification_type == NotificationType.feedback_reminder,
                    Notification.created_at >= window_start,
                )
                .limit(1)
            )
            if already_notified is not None:
                continue

            notify(
                db,
                notification_type=NotificationType.feedback_reminder,
                message=(
                    f"Please leave feedback for {appointment.student_name} about your "
                    f"appointment on {format_dt(appointment.start_time)}."
                ),
                recipient_id=author_id,
                related_appointment_id=appointment.id,
            )
            db.commit()
            notified += 1

    return notified
