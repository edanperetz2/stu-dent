import uuid
from typing import Protocol

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus
from app.models.equipment import Equipment
from app.models.room import Room
from app.models.user import RoleEnum, User

TERMINAL_STATUSES = (
    AppointmentStatus.cancelled,
    AppointmentStatus.completed,
    AppointmentStatus.no_show,
)


class _HasParticipants(Protocol):
    student_id: uuid.UUID
    patient_id: uuid.UUID
    attending_id: uuid.UUID | None


def is_visible_to_participant(entity: _HasParticipants, current_user: User) -> bool:
    """Shared visibility rule for both Appointment and WaitlistEntry -- both
    expose the same student_id/patient_id/attending_id participant shape.
    """
    if current_user.role == RoleEnum.admin:
        return True
    if current_user.role == RoleEnum.student:
        return entity.student_id == current_user.id
    if current_user.role == RoleEnum.attending:
        return entity.attending_id == current_user.id
    if current_user.role == RoleEnum.patient:
        return entity.patient_id == current_user.id
    return False


def recompute_status(appointment: Appointment, *, time_changed: bool = False) -> None:
    """Derive `status` from the two confirmation gates.

    Never called on an appointment already in a terminal status — those are
    set directly by the dedicated cancel/complete/no-show actions, not
    derived here. `time_changed` picks the label used while an attending's
    approval is pending: `rescheduling_requested` if the slot itself moved,
    `awaiting_confirmation` otherwise (e.g. a plain attending reassignment).
    """
    if appointment.status in TERMINAL_STATUSES:
        return

    if appointment.student_confirmed_at is None:
        appointment.status = AppointmentStatus.proposed
        return

    if appointment.attending_id is not None and appointment.attending_approved_at is None:
        appointment.status = (
            AppointmentStatus.rescheduling_requested
            if time_changed
            else AppointmentStatus.awaiting_confirmation
        )
        return

    appointment.status = AppointmentStatus.confirmed


def validate_participants(
    db: Session,
    *,
    student_id: uuid.UUID,
    patient_id: uuid.UUID,
    attending_id: uuid.UUID | None,
    room_id: uuid.UUID | None,
    equipment_id: uuid.UUID | None,
) -> None:
    """Check invariants the DB's FKs/constraints can't express."""
    student = db.get(User, student_id)
    if (
        student is None
        or student.role != RoleEnum.student
        or not student.is_active
        or student.deleted_at is not None
    ):
        raise HTTPException(status_code=422, detail="Invalid student for appointment")

    patient = db.get(User, patient_id)
    if (
        patient is None
        or patient.role != RoleEnum.patient
        or patient.deleted_at is not None
        or patient.owner_student_id != student_id
    ):
        raise HTTPException(status_code=422, detail="Patient does not belong to this student")

    if attending_id is not None:
        attending = db.get(User, attending_id)
        if (
            attending is None
            or attending.role != RoleEnum.attending
            or not attending.is_active
            or attending.deleted_at is not None
        ):
            raise HTTPException(status_code=422, detail="Invalid attending for appointment")

    if room_id is not None:
        room = db.get(Room, room_id)
        if room is None or not room.is_active:
            raise HTTPException(status_code=422, detail="Invalid room for appointment")

    if equipment_id is not None:
        equipment = db.get(Equipment, equipment_id)
        if equipment is None or not equipment.is_active:
            raise HTTPException(status_code=422, detail="Invalid equipment for appointment")


def flush_or_409(db: Session) -> None:
    """Flush, translating an exclusion-constraint violation into a 409.

    Must roll back before the session can be touched again (audit write,
    response serialization) or SQLAlchemy raises PendingRollbackError.
    """
    try:
        db.flush()
    except IntegrityError as err:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Appointment conflicts with an existing booking",
        ) from err
