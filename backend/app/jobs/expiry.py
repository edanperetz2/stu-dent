from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus
from app.models.notification import NotificationType
from app.services.notifications import notify
from app.services.waitlist import check_and_notify_waitlist

_EXPIRABLE_STATUSES = (
    AppointmentStatus.proposed,
    AppointmentStatus.awaiting_confirmation,
    AppointmentStatus.rescheduling_requested,
)


def expire_stale_appointments(db: Session) -> int:
    """Auto-cancel appointments still awaiting someone's action once their
    requested time has already passed -- the request is moot at that point,
    regardless of how long it sat unconfirmed. Also runs the waitlist
    matcher, since an expiry can free a shared resource exactly like an
    explicit cancel/reject does. Commits per appointment so one bad row
    doesn't block the rest of the batch.
    """
    now = datetime.now(UTC)

    candidates = list(
        db.scalars(
            select(Appointment).where(
                Appointment.status.in_(_EXPIRABLE_STATUSES),
                Appointment.end_time < now,
            )
        )
    )

    expired = 0
    for appointment in candidates:
        appointment.status = AppointmentStatus.cancelled
        check_and_notify_waitlist(db, appointment)

        message = (
            f"Your appointment request for {appointment.start_time.isoformat()} "
            "expired because it was never confirmed in time."
        )
        notify(
            db,
            notification_type=NotificationType.appointment_expired,
            message=message,
            recipient_user_id=appointment.student_id,
            related_appointment_id=appointment.id,
        )
        notify(
            db,
            notification_type=NotificationType.appointment_expired,
            message=message,
            recipient_patient_id=appointment.patient_id,
            related_appointment_id=appointment.id,
        )
        if appointment.attending_id is not None:
            notify(
                db,
                notification_type=NotificationType.appointment_expired,
                message=message,
                recipient_user_id=appointment.attending_id,
                related_appointment_id=appointment.id,
            )

        db.commit()
        expired += 1

    return expired
