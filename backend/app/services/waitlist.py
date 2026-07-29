import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus
from app.models.notification import NotificationType
from app.models.waitlist_entry import WaitlistEntry, WaitlistStatus
from app.services.audit import record_audit_log
from app.services.formatting import format_dt
from app.services.notifications import notify
from app.services.scheduling import find_conflicts, recompute_status


def recheck_waitlist_after_cancellation(db: Session, appointment: Appointment) -> None:
    """A cancelled/rejected/expired appointment may have freed exactly what
    an active waitlist entry needs -- thin wrapper around
    `recheck_waitlist_for_freed_slot` for the cancel/reject/expiry call
    sites, which have a real cancelled Appointment row to read the freed
    combination from.
    """
    if appointment.status != AppointmentStatus.cancelled:
        return

    # The session has autoflush disabled (see database.py), so the
    # caller's `appointment.status = cancelled` mutation is still only
    # in-memory at this point -- find_conflicts()'s raw SELECTs would
    # otherwise see this very appointment as still active and never
    # resolve anything. Flushing (not committing) makes it visible to
    # every query below without finalizing the transaction.
    db.flush()

    recheck_waitlist_for_freed_slot(
        db,
        student_id=appointment.student_id,
        patient_id=appointment.patient_id,
        attending_id=appointment.attending_id,
        room_id=appointment.room_id,
        equipment_id=appointment.equipment_id,
        start_time=appointment.start_time,
        end_time=appointment.end_time,
    )


def recheck_waitlist_for_freed_slot(
    db: Session,
    *,
    student_id: uuid.UUID,
    patient_id: uuid.UUID,
    attending_id: uuid.UUID | None,
    room_id: uuid.UUID | None,
    equipment_id: uuid.UUID | None,
    start_time: datetime,
    end_time: datetime,
) -> None:
    """Core promotion logic, factored out so it can run both for a real
    cancellation (`recheck_waitlist_after_cancellation`, above) and for a
    reschedule/room-reassignment that frees up a combination without any
    appointment actually being cancelled (`update_appointment`/
    `accept_appointment`'s room-change path) -- previously only the
    cancel/reject/expiry paths triggered a recheck, so moving an
    appointment out of a slot a waitlist entry wanted left that entry
    stranded until some *other* cancellation happened to touch it.

    Caller is responsible for flushing whatever change actually freed this
    combination first, so find_conflicts() below sees the post-change
    state, not stale data. For each candidate, re-run the same
    find_conflicts() check used at request time -- only when it comes back
    fully clear (not just the one thing this call touched) does the entry
    get promoted into a real Appointment, using recompute_status() so it
    lands in proposed/awaiting_confirmation/confirmed exactly like a fresh
    booking would, never a fabricated confirmation.

    Stages its changes on `db` without committing, so it composes into
    whatever transaction the caller is already running.
    """
    if attending_id is None and room_id is None and equipment_id is None:
        return

    # Ordered by creation sequence: whichever entry has been waiting
    # longest is always tried first. This is also what makes a losing
    # entry (see the `continue` below) fair across repeated cancellations
    # -- it keeps its place ahead of every entry created after it rather
    # than being re-shuffled to arbitrary DB row order on the next attempt.
    # `sequence` (not `created_at`) because entries created in the same
    # transaction can otherwise tie on the timestamp.
    candidates = db.scalars(
        select(WaitlistEntry)
        .where(
            WaitlistEntry.status == WaitlistStatus.active,
            WaitlistEntry.start_time < end_time,
            WaitlistEntry.end_time > start_time,
        )
        .order_by(WaitlistEntry.sequence.asc())
    )

    now = datetime.now(UTC)
    for entry in candidates:
        # Not used to skip the real find_conflicts() check below -- only
        # to decide whether this freed combination is even relevant to
        # this entry at all. `entry.conflict_resource_types` is captured
        # once at entry-creation time and never updated, so it can name a
        # cause that's since become stale (e.g. some *other* resource
        # started blocking the entry after it was created); gating the
        # real check on it as well used to let an entry go permanently
        # unchecked once its original cause stopped matching a
        # cancellation, even though the entry's actual current blocker was
        # something else entirely. A held-type match just means "this
        # freed slot overlaps something this entry cares about" -- cheap
        # enough to always run the authoritative check when it does.
        held_types: set[str] = set()
        if student_id == entry.student_id:
            held_types.add("student")
        if patient_id == entry.patient_id:
            held_types.add("patient")
        if entry.attending_id is not None and attending_id == entry.attending_id:
            held_types.add("attending")
        if entry.room_id is not None and room_id == entry.room_id:
            held_types.add("room")
        if entry.equipment_id is not None and equipment_id == entry.equipment_id:
            held_types.add("equipment")

        if not held_types:
            continue

        remaining = find_conflicts(
            db,
            student_id=entry.student_id,
            patient_id=entry.patient_id,
            attending_id=entry.attending_id,
            room_id=entry.room_id,
            equipment_id=entry.equipment_id,
            start_time=entry.start_time,
            end_time=entry.end_time,
        )
        if remaining:
            continue

        new_appointment = Appointment(
            student_id=entry.student_id,
            patient_id=entry.patient_id,
            attending_id=entry.attending_id,
            room_id=entry.room_id,
            equipment_id=entry.equipment_id,
            start_time=entry.start_time,
            end_time=entry.end_time,
            notes=entry.notes,
            student_confirmed_at=entry.student_confirmed_at,
        )
        recompute_status(new_appointment)

        # Scoped to a SAVEPOINT, not a bare flush: the caller (cancel/
        # reject/expiry) has already staged its own uncommitted changes
        # (e.g. appointment.status = cancelled) on this same session. A
        # bare IntegrityError + db.rollback() here would discard that too.
        # A savepoint means a race here (e.g. two entries contending for
        # the same freed slot, or a genuine concurrent external booking)
        # only aborts this one promotion attempt -- the entry simply stays
        # active for the next opportunity.
        try:
            with db.begin_nested():
                db.add(new_appointment)
                db.flush()
        except IntegrityError:
            continue

        entry.status = WaitlistStatus.booked
        entry.resolved_at = now
        entry.resulting_appointment_id = new_appointment.id

        message = (
            f"Your waitlisted request for {format_dt(entry.start_time)} - "
            f"{format_dt(entry.end_time)} was automatically booked "
            f"(status: {new_appointment.status.value})."
        )
        notify(
            db,
            notification_type=NotificationType.waitlist_slot_available,
            message=message,
            recipient_id=entry.student_id,
            related_appointment_id=new_appointment.id,
        )
        notify(
            db,
            notification_type=NotificationType.waitlist_slot_available,
            message=message,
            recipient_id=entry.patient_id,
            related_appointment_id=new_appointment.id,
        )
        if entry.attending_id is not None:
            notify(
                db,
                notification_type=NotificationType.waitlist_slot_available,
                message=message,
                recipient_id=entry.attending_id,
                related_appointment_id=new_appointment.id,
            )

        record_audit_log(
            db,
            action="waitlist_auto_booked",
            target_type="waitlist_entry",
            target_id=entry.id,
            extra_data={"appointment_id": str(new_appointment.id)},
        )
