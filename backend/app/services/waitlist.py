from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus
from app.models.notification import NotificationType
from app.models.waitlist_entry import WaitlistEntry, WaitlistStatus
from app.services.audit import record_audit_log
from app.services.notifications import notify


def check_and_notify_waitlist(db: Session, appointment: Appointment) -> None:
    """Match a freshly-cancelled appointment against active waitlist entries.

    Only fires when the cancelled appointment held a genuinely shared
    resource (attending/room/equipment) — one with none of those set didn't
    free anything a waitlist entry could be contending for, so a generic
    (no-preference) waitlist entry never matches through this path. Matches
    are one-shot: `active` -> `notified`, never re-checked; the requester
    re-enters the waitlist by creating a new entry.

    Stages its changes on `db` without committing, so it composes into
    whatever transaction the caller (an appointment cancel/reject route, or
    the expiry job) is already running.
    """
    if appointment.status != AppointmentStatus.cancelled:
        return
    if (
        appointment.attending_id is None
        and appointment.room_id is None
        and appointment.equipment_id is None
    ):
        return

    candidates = db.scalars(
        select(WaitlistEntry).where(
            WaitlistEntry.status == WaitlistStatus.active,
            WaitlistEntry.start_time < appointment.end_time,
            WaitlistEntry.end_time > appointment.start_time,
        )
    )

    now = datetime.now(UTC)
    for entry in candidates:
        if entry.attending_id is None and entry.room_id is None and entry.equipment_id is None:
            continue
        if entry.attending_id is not None and entry.attending_id != appointment.attending_id:
            continue
        if entry.room_id is not None and entry.room_id != appointment.room_id:
            continue
        if entry.equipment_id is not None and entry.equipment_id != appointment.equipment_id:
            continue

        entry.status = WaitlistStatus.notified
        entry.notified_at = now

        message = (
            f"A slot opened up matching your waitlist request for "
            f"{entry.start_time.isoformat()} - {entry.end_time.isoformat()}. "
            "Book it soon through the normal appointment request flow."
        )
        notify(
            db,
            notification_type=NotificationType.waitlist_slot_available,
            message=message,
            recipient_user_id=entry.student_id,
            related_appointment_id=appointment.id,
        )
        notify(
            db,
            notification_type=NotificationType.waitlist_slot_available,
            message=message,
            recipient_patient_id=entry.patient_id,
            related_appointment_id=appointment.id,
        )

        record_audit_log(
            db,
            action="waitlist_match_notified",
            target_type="waitlist_entry",
            target_id=entry.id,
            extra_data={"appointment_id": str(appointment.id)},
        )
