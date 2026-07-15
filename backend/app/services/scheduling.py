import uuid
from datetime import datetime
from typing import Protocol

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.appointment import ACTIVE_STATUSES, Appointment, AppointmentStatus
from app.models.equipment import Equipment
from app.models.room import Room
from app.models.user import RoleEnum, User
from app.schemas.appointment import AppointmentCreate
from app.schemas.scheduling import ConflictReason, ConflictResourceType

TERMINAL_STATUSES = (
    AppointmentStatus.cancelled,
    AppointmentStatus.completed,
    AppointmentStatus.no_show,
)


class AppointmentConflictError(Exception):
    """Raised instead of inserting/updating when find_conflicts() finds a
    real, named blocker -- caught by a dedicated FastAPI exception handler
    (see main.py) that returns a 409 with a structured `conflicts` array,
    unlike flush_or_409's generic message for the rare DB-level race case.
    """

    def __init__(self, message: str, conflicts: list[ConflictReason]) -> None:
        super().__init__(message)
        self.message = message
        self.conflicts = conflicts


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


def resolve_appointment_requester(
    current_user: User, payload: AppointmentCreate
) -> tuple[uuid.UUID, uuid.UUID]:
    """Shared patient-vs-student request resolution for both
    POST /appointments and POST /waitlist -- identical role rules: a
    patient requests for themself and can't pick an attending/room/
    equipment, a student must name which patient. Returns
    (student_id, patient_id). Appointment-only concerns (student
    requiring a room, setting student_confirmed_at) stay in the caller.
    """
    from app.services.patients import require_confirmed_patient

    if current_user.role == RoleEnum.patient:
        require_confirmed_patient(current_user)
        if payload.attending_id or payload.room_id or payload.equipment_id:
            raise HTTPException(
                status_code=422,
                detail="Patients cannot set attending, room, or equipment when requesting",
            )
        return current_user.owner_student_id, current_user.id
    if current_user.role == RoleEnum.student:
        if payload.patient_id is None:
            raise HTTPException(status_code=422, detail="patient_id is required")
        return current_user.id, payload.patient_id
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only students or patients can request appointments",
    )


def find_conflicts(
    db: Session,
    *,
    student_id: uuid.UUID,
    patient_id: uuid.UUID,
    attending_id: uuid.UUID | None,
    room_id: uuid.UUID | None,
    equipment_id: uuid.UUID | None,
    start_time: datetime,
    end_time: datetime,
    exclude_appointment_id: uuid.UUID | None = None,
) -> list[ConflictReason]:
    """Proactively check each requested participant/resource for a real
    overlapping active appointment, so the caller knows exactly *which*
    one is blocking the request instead of learning only that "some"
    exclusion constraint would fire. Student and patient are always
    checked (every appointment has both); attending/room/equipment are
    only checked when the request actually specifies one.

    `exclude_appointment_id` lets an in-place edit ignore its own row.
    Used both for the pre-check ahead of create/update/accept and for the
    waitlist's own creation + auto-promotion re-check -- the single source
    of truth for "is this exact combination free right now".
    """
    checks: list[tuple[ConflictResourceType, object, uuid.UUID, type]] = [
        ("student", Appointment.student_id, student_id, User),
        ("patient", Appointment.patient_id, patient_id, User),
    ]
    if attending_id is not None:
        checks.append(("attending", Appointment.attending_id, attending_id, User))
    if room_id is not None:
        checks.append(("room", Appointment.room_id, room_id, Room))
    if equipment_id is not None:
        checks.append(("equipment", Appointment.equipment_id, equipment_id, Equipment))

    reasons: list[ConflictReason] = []
    for resource_type, column, value, model in checks:
        stmt = select(Appointment.id).where(
            column == value,
            Appointment.status.in_(ACTIVE_STATUSES),
            Appointment.start_time < end_time,
            Appointment.end_time > start_time,
        )
        if exclude_appointment_id is not None:
            stmt = stmt.where(Appointment.id != exclude_appointment_id)
        if db.scalar(stmt.limit(1)) is None:
            continue

        entity = db.get(model, value)
        name = entity.full_name if model is User else entity.name  # type: ignore[union-attr]
        reasons.append(
            ConflictReason(resource_type=resource_type, resource_id=value, resource_name=name)
        )
    return reasons


def redact_conflicts_for_patient(
    conflicts: list[ConflictReason], *, patient_id: uuid.UUID, patient_name: str
) -> list[ConflictReason]:
    """A "student" conflict means the treating student has some other
    active appointment overlapping the request -- which may belong to a
    completely different patient. A patient has no legitimate reason to
    learn that their student is occupied by someone else's care at a
    specific time, so this collapses "student" into the same
    undifferentiated "patient" signal a genuine self-conflict would
    produce, before a patient-originated request/waitlist-view ever sees
    the response. Never call this for a student/attending/admin viewer --
    they're allowed the real, precise cause.
    """
    redacted: list[ConflictReason] = []
    merged_patient_cause = False
    for conflict in conflicts:
        if conflict.resource_type in ("student", "patient"):
            if merged_patient_cause:
                continue
            redacted.append(
                ConflictReason(
                    resource_type="patient", resource_id=patient_id, resource_name=patient_name
                )
            )
            merged_patient_cause = True
        else:
            redacted.append(conflict)
    return redacted


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
