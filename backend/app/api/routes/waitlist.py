import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import RoleEnum, User
from app.models.waitlist_entry import WaitlistEntry, WaitlistStatus
from app.schemas.appointment import AppointmentCreate
from app.schemas.scheduling import ConflictReason
from app.schemas.waitlist import WaitlistEntryOut
from app.services.audit import record_audit_log
from app.services.scheduling import (
    find_conflicts,
    is_visible_to_participant,
    redact_conflicts_for_patient,
    resolve_appointment_requester,
    validate_participants,
)

router = APIRouter(tags=["waitlist"])

_RESOURCE_FIELDS: dict[str, tuple[str, str]] = {
    "student": ("student_id", "student_name"),
    "patient": ("patient_id", "patient_name"),
    "attending": ("attending_id", "attending_name"),
    "room": ("room_id", "room_name"),
    "equipment": ("equipment_id", "equipment_name"),
}


def _entry_out(entry: WaitlistEntry, current_user: User) -> WaitlistEntryOut:
    conflicts = [
        ConflictReason(
            resource_type=resource_type,  # type: ignore[arg-type]
            resource_id=getattr(entry, _RESOURCE_FIELDS[resource_type][0]),
            resource_name=getattr(entry, _RESOURCE_FIELDS[resource_type][1]),
        )
        for resource_type in entry.conflict_resource_types
    ]
    # The stored causes stay precise (needed for correct re-check logic on
    # every cancellation) -- only redacted for a patient viewing their own
    # entry, same reasoning as create_appointment's 409 response.
    if current_user.role == RoleEnum.patient:
        conflicts = redact_conflicts_for_patient(
            conflicts, patient_id=current_user.id, patient_name=current_user.full_name
        )
    return WaitlistEntryOut(
        id=entry.id,
        student_id=entry.student_id,
        patient_id=entry.patient_id,
        attending_id=entry.attending_id,
        room_id=entry.room_id,
        equipment_id=entry.equipment_id,
        start_time=entry.start_time,
        end_time=entry.end_time,
        notes=entry.notes,
        status=entry.status,
        resolved_at=entry.resolved_at,
        resulting_appointment_id=entry.resulting_appointment_id,
        resulting_appointment_status=(
            entry.resulting_appointment.status if entry.resulting_appointment else None
        ),
        conflicts=conflicts,
        student_name=entry.student_name,
        patient_name=entry.patient_name,
        attending_name=entry.attending_name,
        room_name=entry.room_name,
        equipment_name=entry.equipment_name,
    )


def _get_visible_entry(db: Session, entry_id: uuid.UUID, current_user: User) -> WaitlistEntry:
    entry = db.get(WaitlistEntry, entry_id)
    if entry is None or not is_visible_to_participant(entry, current_user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waitlist entry not found"
        )
    return entry


@router.post("/waitlist", response_model=WaitlistEntryOut, status_code=status.HTTP_201_CREATED)
def create_waitlist_entry(
    payload: AppointmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WaitlistEntryOut:
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=422, detail="end_time must be after start_time")

    student_id, patient_id = resolve_appointment_requester(current_user, payload)

    validate_participants(
        db,
        student_id=student_id,
        patient_id=patient_id,
        attending_id=payload.attending_id,
        room_id=payload.room_id,
        equipment_id=payload.equipment_id,
    )

    # Never trust a client-supplied reason -- re-derive it independently,
    # exactly like the real create/update/accept routes do.
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
    if not conflicts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No conflict exists for this request -- book it directly instead of joining "
            "the waitlist.",
        )

    entry = WaitlistEntry(
        student_id=student_id,
        patient_id=patient_id,
        attending_id=payload.attending_id,
        room_id=payload.room_id,
        equipment_id=payload.equipment_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        notes=payload.notes,
        student_confirmed_at=datetime.now(UTC) if current_user.role == RoleEnum.student else None,
        conflict_resource_types=[c.resource_type for c in conflicts],
    )
    db.add(entry)
    db.flush()

    record_audit_log(
        db,
        action="waitlist_create",
        actor_id=current_user.id,
        target_type="waitlist_entry",
        target_id=entry.id,
    )
    db.commit()
    db.refresh(entry)
    return _entry_out(entry, current_user)


@router.get("/waitlist", response_model=list[WaitlistEntryOut])
def list_waitlist_entries(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WaitlistEntryOut]:
    stmt = select(WaitlistEntry)
    if current_user.role == RoleEnum.patient:
        stmt = stmt.where(WaitlistEntry.patient_id == current_user.id)
    elif current_user.role == RoleEnum.student:
        stmt = stmt.where(WaitlistEntry.student_id == current_user.id)
    elif current_user.role == RoleEnum.attending:
        stmt = stmt.where(WaitlistEntry.attending_id == current_user.id)
    return [_entry_out(entry, current_user) for entry in db.scalars(stmt)]


@router.get("/waitlist/{entry_id}", response_model=WaitlistEntryOut)
def get_waitlist_entry(
    entry_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WaitlistEntryOut:
    return _entry_out(_get_visible_entry(db, entry_id, current_user), current_user)


@router.post("/waitlist/{entry_id}/cancel", response_model=WaitlistEntryOut)
def cancel_waitlist_entry(
    entry_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WaitlistEntryOut:
    entry = _get_visible_entry(db, entry_id, current_user)

    is_owning_student = (
        current_user.role == RoleEnum.student and entry.student_id == current_user.id
    )
    is_self_patient = current_user.role == RoleEnum.patient and entry.patient_id == current_user.id
    if not (is_owning_student or is_self_patient):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to cancel this waitlist entry",
        )

    if entry.status != WaitlistStatus.active:
        raise HTTPException(
            status_code=409, detail="Only an active waitlist entry can be cancelled"
        )

    entry.status = WaitlistStatus.cancelled
    db.flush()

    record_audit_log(
        db,
        action="waitlist_cancel",
        actor_id=current_user.id,
        target_type="waitlist_entry",
        target_id=entry.id,
    )
    db.commit()
    db.refresh(entry)
    return _entry_out(entry, current_user)


@router.post("/waitlist/{entry_id}/reactivate", response_model=WaitlistEntryOut)
def reactivate_waitlist_entry(
    entry_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WaitlistEntryOut:
    """Undoes a cancel -- safe because cancelling a waitlist entry is a pure
    status flip with no side effects (unlike cancelling an appointment,
    which can synchronously auto-promote a *different* waitlist entry into
    a real booking; see the frontend's undo-toast usage for why that one
    still uses a real confirm instead of this pattern). Doesn't re-derive
    conflicts -- a short-window undo should restore exactly what was
    cancelled, not silently change what it's waiting for.
    """
    entry = _get_visible_entry(db, entry_id, current_user)

    is_owning_student = (
        current_user.role == RoleEnum.student and entry.student_id == current_user.id
    )
    is_self_patient = current_user.role == RoleEnum.patient and entry.patient_id == current_user.id
    if not (is_owning_student or is_self_patient):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to reactivate this waitlist entry",
        )

    if entry.status != WaitlistStatus.cancelled:
        raise HTTPException(
            status_code=409, detail="Only a cancelled waitlist entry can be reactivated"
        )

    entry.status = WaitlistStatus.active
    db.flush()

    record_audit_log(
        db,
        action="waitlist_reactivate",
        actor_id=current_user.id,
        target_type="waitlist_entry",
        target_id=entry.id,
    )
    db.commit()
    db.refresh(entry)
    return _entry_out(entry, current_user)
