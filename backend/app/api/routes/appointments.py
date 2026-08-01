import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.appointment import Appointment, AppointmentStatus
from app.models.notification import NotificationType
from app.models.user import RoleEnum, User
from app.schemas.appointment import (
    AppointmentAccept,
    AppointmentCreate,
    AppointmentOut,
    AppointmentUpdate,
)
from app.services.audit import record_audit_log
from app.services.formatting import format_dt
from app.services.notifications import notify
from app.services.scheduling import (
    TERMINAL_STATUSES,
    AppointmentConflictError,
    find_conflicts,
    flush_or_409,
    is_visible_to_participant,
    recompute_status,
    redact_conflicts_for_patient,
    resolve_appointment_requester,
    validate_participants,
)
from app.services.waitlist import (
    recheck_waitlist_after_cancellation,
    recheck_waitlist_for_freed_slot,
)

router = APIRouter(tags=["appointments"])


def _get_visible_appointment(
    db: Session, appointment_id: uuid.UUID, current_user: User
) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if appointment is None or not is_visible_to_participant(appointment, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    return appointment


def _require_owning_student(appointment: Appointment, current_user: User) -> None:
    if current_user.role != RoleEnum.student or appointment.student_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the owning student")


def _require_started(appointment: Appointment) -> None:
    if datetime.now(UTC) < appointment.start_time:
        raise HTTPException(
            status_code=409,
            detail="This appointment hasn't started yet -- try again after its "
            "start time, or edit the appointment if the time is wrong.",
        )


@router.post("/appointments", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
def create_appointment(
    payload: AppointmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Appointment:
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=422, detail="end_time must be after start_time")

    student_id, patient_id = resolve_appointment_requester(current_user, payload)
    if current_user.role == RoleEnum.student:
        if payload.room_id is None:
            raise HTTPException(status_code=422, detail="room_id is required")
        student_confirmed_at = datetime.now(UTC)
    else:
        student_confirmed_at = None

    validate_participants(
        db,
        student_id=student_id,
        patient_id=patient_id,
        attending_id=payload.attending_id,
        room_id=payload.room_id,
        equipment_id=payload.equipment_id,
    )

    conflicts = find_conflicts(
        db,
        student_id=student_id,
        patient_id=patient_id,
        attending_id=payload.attending_id,
        room_id=payload.room_id,
        equipment_id=payload.equipment_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    if conflicts:
        # A patient must never learn that their student is busy with
        # someone else's care -- see redact_conflicts_for_patient.
        if current_user.role == RoleEnum.patient:
            conflicts = redact_conflicts_for_patient(
                conflicts, patient_id=current_user.id, patient_name=current_user.full_name
            )
        raise AppointmentConflictError(
            "Requested time conflicts with an existing booking", conflicts
        )

    appointment = Appointment(
        student_id=student_id,
        patient_id=patient_id,
        attending_id=payload.attending_id,
        room_id=payload.room_id,
        equipment_id=payload.equipment_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        notes=payload.notes,
        student_confirmed_at=student_confirmed_at,
    )
    recompute_status(appointment)
    db.add(appointment)
    flush_or_409(db)

    # Whoever needs to act next on this new appointment should be told --
    # previously nobody but the creator ever found out it existed.
    if current_user.role == RoleEnum.student and payload.attending_id is not None:
        notify(
            db,
            notification_type=NotificationType.appointment_created,
            message=(
                f"New appointment with {appointment.patient_name} on "
                f"{format_dt(appointment.start_time)} needs your approval."
            ),
            recipient_id=payload.attending_id,
            related_appointment_id=appointment.id,
        )
    elif current_user.role == RoleEnum.patient:
        notify(
            db,
            notification_type=NotificationType.appointment_created,
            message=(
                f"{appointment.patient_name} requested an appointment on "
                f"{format_dt(appointment.start_time)} -- accept or reject it."
            ),
            recipient_id=student_id,
            related_appointment_id=appointment.id,
        )

    record_audit_log(
        db,
        action="appointment_create",
        actor_id=current_user.id,
        target_type="appointment",
        target_id=appointment.id,
    )
    db.commit()
    db.refresh(appointment)
    return appointment


@router.get("/appointments", response_model=list[AppointmentOut])
def list_appointments(
    # Lets the calendar sub-view ask only for what it's currently showing
    # (a month/week/day at a time) instead of the whole table -- both
    # bounds are optional so the List sub-view (no inherent date window)
    # can still request everything up to `limit`.
    start_after: datetime | None = Query(default=None),
    start_before: datetime | None = Query(default=None),
    # The frontend used to fetch every appointment and filter cancelled
    # ones out client-side -- moved server-side so a cancelled-heavy
    # account doesn't pay to transfer rows it's going to throw away.
    exclude_cancelled: bool = Query(default=False),
    limit: int = Query(default=500, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Appointment]:
    stmt = select(Appointment)
    if current_user.role == RoleEnum.patient:
        stmt = stmt.where(Appointment.patient_id == current_user.id)
    elif current_user.role == RoleEnum.student:
        stmt = stmt.where(Appointment.student_id == current_user.id)
    elif current_user.role == RoleEnum.attending:
        stmt = stmt.where(Appointment.attending_id == current_user.id)
    # else: admin sees every appointment, unfiltered.
    if start_after is not None:
        stmt = stmt.where(Appointment.start_time >= start_after)
    if start_before is not None:
        stmt = stmt.where(Appointment.start_time < start_before)
    if exclude_cancelled:
        stmt = stmt.where(Appointment.status != AppointmentStatus.cancelled)
    stmt = stmt.order_by(Appointment.start_time.desc()).offset(offset).limit(limit)
    return list(db.scalars(stmt))


@router.get("/appointments/{appointment_id}", response_model=AppointmentOut)
def get_appointment(
    appointment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Appointment:
    return _get_visible_appointment(db, appointment_id, current_user)


@router.patch("/appointments/{appointment_id}", response_model=AppointmentOut)
def update_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Appointment:
    appointment = _get_visible_appointment(db, appointment_id, current_user)
    _require_owning_student(appointment, current_user)

    if appointment.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="Cannot edit a finalized appointment")

    fields = payload.model_dump(exclude_unset=True)

    if "room_id" in fields and fields["room_id"] is None:
        raise HTTPException(status_code=422, detail="room_id cannot be cleared")

    new_start = fields.get("start_time", appointment.start_time)
    new_end = fields.get("end_time", appointment.end_time)
    if new_end <= new_start:
        raise HTTPException(status_code=422, detail="end_time must be after start_time")

    new_attending_id = fields.get("attending_id", appointment.attending_id)
    new_room_id = fields.get("room_id", appointment.room_id)
    new_equipment_id = fields.get("equipment_id", appointment.equipment_id)

    old_start, old_end = appointment.start_time, appointment.end_time
    old_attending_id, old_room_id, old_equipment_id = (
        appointment.attending_id,
        appointment.room_id,
        appointment.equipment_id,
    )
    freed_slot_changed = (
        new_start != old_start
        or new_end != old_end
        or new_attending_id != old_attending_id
        or new_room_id != old_room_id
        or new_equipment_id != old_equipment_id
    )

    # Compares actual values, not payload-key presence -- the frontend's
    # edit form always submits start_time/end_time on every PATCH (even
    # when only e.g. notes changed), so checking "start_time" in fields
    # used to incorrectly reset attending approval on every single edit.
    time_changed = new_start != old_start or new_end != old_end
    attending_changed = (
        "attending_id" in fields and fields["attending_id"] != appointment.attending_id
    )

    validate_participants(
        db,
        student_id=appointment.student_id,
        patient_id=appointment.patient_id,
        attending_id=new_attending_id,
        room_id=new_room_id,
        equipment_id=new_equipment_id,
    )

    # Checked before any field is mutated -- excludes this appointment's own
    # (not-yet-updated) row so it never conflicts with itself, and lets a
    # conflict bail out before the ORM object is touched at all.
    conflicts = find_conflicts(
        db,
        student_id=appointment.student_id,
        patient_id=appointment.patient_id,
        attending_id=new_attending_id,
        room_id=new_room_id,
        equipment_id=new_equipment_id,
        start_time=new_start,
        end_time=new_end,
        exclude_appointment_id=appointment.id,
    )
    if conflicts:
        raise AppointmentConflictError(
            "Requested change conflicts with an existing booking", conflicts
        )

    if "start_time" in fields:
        appointment.start_time = fields["start_time"]
    if "end_time" in fields:
        appointment.end_time = fields["end_time"]
    if "room_id" in fields:
        appointment.room_id = fields["room_id"]
    if "equipment_id" in fields:
        appointment.equipment_id = fields["equipment_id"]
    if "attending_id" in fields:
        appointment.attending_id = fields["attending_id"]
    if "notes" in fields:
        appointment.notes = fields["notes"]

    if time_changed:
        # The one-time reminder already sent (if any) was for the old
        # time -- without this, a rescheduled appointment would never get
        # a reminder for its new time at all.
        appointment.reminder_sent_at = None

    if time_changed or attending_changed:
        if appointment.attending_id is not None:
            appointment.attending_approved_at = None
            notify(
                db,
                notification_type=NotificationType.appointment_created,
                message=(
                    f"The appointment with {appointment.patient_name} on "
                    f"{format_dt(appointment.start_time)} was changed and needs "
                    "your approval again."
                ),
                recipient_id=appointment.attending_id,
                related_appointment_id=appointment.id,
            )
        recompute_status(appointment, time_changed=time_changed)

    flush_or_409(db)

    if freed_slot_changed:
        # This appointment moved away from its old attending/room/
        # equipment/time combination without anyone cancelling anything --
        # a waitlist entry that wanted the vacated combination would
        # otherwise never get rechecked (only cancel/reject/expiry used to
        # trigger this).
        recheck_waitlist_for_freed_slot(
            db,
            student_id=appointment.student_id,
            patient_id=appointment.patient_id,
            attending_id=old_attending_id,
            room_id=old_room_id,
            equipment_id=old_equipment_id,
            start_time=old_start,
            end_time=old_end,
        )
        flush_or_409(db)

    record_audit_log(
        db,
        action="appointment_update",
        actor_id=current_user.id,
        target_type="appointment",
        target_id=appointment.id,
    )
    db.commit()
    db.refresh(appointment)
    return appointment


@router.post("/appointments/{appointment_id}/accept", response_model=AppointmentOut)
def accept_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentAccept | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Appointment:
    appointment = _get_visible_appointment(db, appointment_id, current_user)
    _require_owning_student(appointment, current_user)

    if appointment.status != AppointmentStatus.proposed:
        raise HTTPException(status_code=409, detail="Only a proposed appointment can be accepted")

    supplied_room_id = payload.room_id if payload is not None else None
    room_id = supplied_room_id if supplied_room_id is not None else appointment.room_id
    if room_id is None:
        raise HTTPException(
            status_code=422, detail="room_id is required to accept this appointment"
        )
    old_room_id = appointment.room_id
    room_changed = room_id != appointment.room_id
    if room_changed:
        validate_participants(
            db,
            student_id=appointment.student_id,
            patient_id=appointment.patient_id,
            attending_id=appointment.attending_id,
            room_id=room_id,
            equipment_id=appointment.equipment_id,
        )
        conflicts = find_conflicts(
            db,
            student_id=appointment.student_id,
            patient_id=appointment.patient_id,
            attending_id=appointment.attending_id,
            room_id=room_id,
            equipment_id=appointment.equipment_id,
            start_time=appointment.start_time,
            end_time=appointment.end_time,
            exclude_appointment_id=appointment.id,
        )
        if conflicts:
            raise AppointmentConflictError(
                "Requested room conflicts with an existing booking", conflicts
            )
        appointment.room_id = room_id

    appointment.student_confirmed_at = datetime.now(UTC)
    recompute_status(appointment)
    flush_or_409(db)

    if room_changed and old_room_id is not None:
        # The old room is now free at this appointment's time -- a
        # waitlist entry that wanted it would otherwise never get
        # rechecked (only cancel/reject/expiry used to trigger this).
        recheck_waitlist_for_freed_slot(
            db,
            student_id=appointment.student_id,
            patient_id=appointment.patient_id,
            attending_id=appointment.attending_id,
            room_id=old_room_id,
            equipment_id=appointment.equipment_id,
            start_time=appointment.start_time,
            end_time=appointment.end_time,
        )
        flush_or_409(db)

    notify(
        db,
        notification_type=NotificationType.appointment_status_changed,
        message=f"Your appointment request for {format_dt(appointment.start_time)} was accepted.",
        recipient_id=appointment.patient_id,
        related_appointment_id=appointment.id,
    )
    if appointment.attending_id is not None and appointment.attending_approved_at is None:
        notify(
            db,
            notification_type=NotificationType.appointment_created,
            message=(
                f"New appointment with {appointment.patient_name} on "
                f"{format_dt(appointment.start_time)} needs your approval."
            ),
            recipient_id=appointment.attending_id,
            related_appointment_id=appointment.id,
        )

    record_audit_log(
        db,
        action="appointment_accept",
        actor_id=current_user.id,
        target_type="appointment",
        target_id=appointment.id,
    )
    db.commit()
    db.refresh(appointment)
    return appointment


@router.post("/appointments/{appointment_id}/approve", response_model=AppointmentOut)
def approve_appointment(
    appointment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Appointment:
    appointment = _get_visible_appointment(db, appointment_id, current_user)
    if current_user.role != RoleEnum.attending or appointment.attending_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not the assigned attending"
        )

    if appointment.status not in (
        AppointmentStatus.awaiting_confirmation,
        AppointmentStatus.rescheduling_requested,
    ):
        raise HTTPException(
            status_code=409, detail="Appointment is not awaiting attending approval"
        )

    appointment.attending_approved_at = datetime.now(UTC)
    recompute_status(appointment)
    flush_or_409(db)

    approve_message = (
        f"Your appointment on {format_dt(appointment.start_time)} was approved and confirmed."
    )
    notify(
        db,
        notification_type=NotificationType.appointment_status_changed,
        message=approve_message,
        recipient_id=appointment.student_id,
        related_appointment_id=appointment.id,
    )
    notify(
        db,
        notification_type=NotificationType.appointment_status_changed,
        message=approve_message,
        recipient_id=appointment.patient_id,
        related_appointment_id=appointment.id,
    )

    record_audit_log(
        db,
        action="appointment_approve",
        actor_id=current_user.id,
        target_type="appointment",
        target_id=appointment.id,
    )
    db.commit()
    db.refresh(appointment)
    return appointment


@router.post("/appointments/{appointment_id}/reject", response_model=AppointmentOut)
def reject_appointment(
    appointment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Appointment:
    appointment = _get_visible_appointment(db, appointment_id, current_user)

    is_owning_student = (
        current_user.role == RoleEnum.student and appointment.student_id == current_user.id
    )
    is_assigned_attending = (
        current_user.role == RoleEnum.attending and appointment.attending_id == current_user.id
    )
    if not (is_owning_student or is_assigned_attending):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to reject this appointment",
        )

    if appointment.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="Appointment is already finalized")

    appointment.status = AppointmentStatus.cancelled
    recheck_waitlist_after_cancellation(db, appointment)
    flush_or_409(db)

    reject_message = f"Your appointment on {format_dt(appointment.start_time)} was rejected."
    if not is_owning_student:
        notify(
            db,
            notification_type=NotificationType.appointment_status_changed,
            message=reject_message,
            recipient_id=appointment.student_id,
            related_appointment_id=appointment.id,
        )
    notify(
        db,
        notification_type=NotificationType.appointment_status_changed,
        message=reject_message,
        recipient_id=appointment.patient_id,
        related_appointment_id=appointment.id,
    )
    if appointment.attending_id is not None and not is_assigned_attending:
        notify(
            db,
            notification_type=NotificationType.appointment_status_changed,
            message=reject_message,
            recipient_id=appointment.attending_id,
            related_appointment_id=appointment.id,
        )

    record_audit_log(
        db,
        action="appointment_reject",
        actor_id=current_user.id,
        target_type="appointment",
        target_id=appointment.id,
    )
    db.commit()
    db.refresh(appointment)
    return appointment


@router.post("/appointments/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_appointment(
    appointment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Appointment:
    appointment = _get_visible_appointment(db, appointment_id, current_user)

    is_owning_student = (
        current_user.role == RoleEnum.student and appointment.student_id == current_user.id
    )
    is_self_patient = (
        current_user.role == RoleEnum.patient and appointment.patient_id == current_user.id
    )
    if not (is_owning_student or is_self_patient):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to cancel this appointment",
        )

    if appointment.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="Appointment is already finalized")

    appointment.status = AppointmentStatus.cancelled
    recheck_waitlist_after_cancellation(db, appointment)
    flush_or_409(db)

    cancel_message = f"Your appointment on {format_dt(appointment.start_time)} was cancelled."
    if not is_owning_student:
        notify(
            db,
            notification_type=NotificationType.appointment_status_changed,
            message=cancel_message,
            recipient_id=appointment.student_id,
            related_appointment_id=appointment.id,
        )
    if not is_self_patient:
        notify(
            db,
            notification_type=NotificationType.appointment_status_changed,
            message=cancel_message,
            recipient_id=appointment.patient_id,
            related_appointment_id=appointment.id,
        )
    if appointment.attending_id is not None:
        notify(
            db,
            notification_type=NotificationType.appointment_status_changed,
            message=cancel_message,
            recipient_id=appointment.attending_id,
            related_appointment_id=appointment.id,
        )

    record_audit_log(
        db,
        action="appointment_cancel",
        actor_id=current_user.id,
        target_type="appointment",
        target_id=appointment.id,
    )
    db.commit()
    db.refresh(appointment)
    return appointment


@router.post("/appointments/{appointment_id}/complete", response_model=AppointmentOut)
def complete_appointment(
    appointment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Appointment:
    appointment = _get_visible_appointment(db, appointment_id, current_user)
    _require_owning_student(appointment, current_user)

    if appointment.status != AppointmentStatus.confirmed:
        raise HTTPException(status_code=409, detail="Only a confirmed appointment can be completed")
    _require_started(appointment)

    appointment.status = AppointmentStatus.completed
    flush_or_409(db)

    record_audit_log(
        db,
        action="appointment_complete",
        actor_id=current_user.id,
        target_type="appointment",
        target_id=appointment.id,
    )
    db.commit()
    db.refresh(appointment)
    return appointment


@router.post("/appointments/{appointment_id}/no-show", response_model=AppointmentOut)
def mark_no_show(
    appointment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Appointment:
    appointment = _get_visible_appointment(db, appointment_id, current_user)
    _require_owning_student(appointment, current_user)

    if appointment.status != AppointmentStatus.confirmed:
        raise HTTPException(
            status_code=409, detail="Only a confirmed appointment can be marked no-show"
        )
    _require_started(appointment)

    appointment.status = AppointmentStatus.no_show
    flush_or_409(db)

    record_audit_log(
        db,
        action="appointment_no_show",
        actor_id=current_user.id,
        target_type="appointment",
        target_id=appointment.id,
    )
    db.commit()
    db.refresh(appointment)
    return appointment
