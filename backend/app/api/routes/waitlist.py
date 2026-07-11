import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import RoleEnum, User
from app.models.waitlist_entry import WaitlistEntry, WaitlistStatus
from app.schemas.waitlist import WaitlistEntryCreate, WaitlistEntryOut
from app.services.audit import record_audit_log
from app.services.patients import require_confirmed_patient
from app.services.scheduling import is_visible_to_participant, validate_participants

router = APIRouter(tags=["waitlist"])


def _get_visible_entry(db: Session, entry_id: uuid.UUID, current_user: User) -> WaitlistEntry:
    entry = db.get(WaitlistEntry, entry_id)
    if entry is None or not is_visible_to_participant(entry, current_user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waitlist entry not found"
        )
    return entry


@router.post("/waitlist", response_model=WaitlistEntryOut, status_code=status.HTTP_201_CREATED)
def create_waitlist_entry(
    payload: WaitlistEntryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WaitlistEntry:
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=422, detail="end_time must be after start_time")

    if current_user.role == RoleEnum.patient:
        require_confirmed_patient(current_user)
        student_id = current_user.owner_student_id
        patient_id = current_user.id
    elif current_user.role == RoleEnum.student:
        if payload.patient_id is None:
            raise HTTPException(status_code=422, detail="patient_id is required")
        student_id = current_user.id
        patient_id = payload.patient_id
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students or patients can create waitlist entries",
        )

    validate_participants(
        db,
        student_id=student_id,
        patient_id=patient_id,
        attending_id=payload.attending_id,
        room_id=payload.room_id,
        equipment_id=payload.equipment_id,
    )

    entry = WaitlistEntry(
        student_id=student_id,
        patient_id=patient_id,
        attending_id=payload.attending_id,
        room_id=payload.room_id,
        equipment_id=payload.equipment_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
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
    return entry


@router.get("/waitlist", response_model=list[WaitlistEntryOut])
def list_waitlist_entries(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WaitlistEntry]:
    stmt = select(WaitlistEntry)
    if current_user.role == RoleEnum.patient:
        stmt = stmt.where(WaitlistEntry.patient_id == current_user.id)
    elif current_user.role == RoleEnum.student:
        stmt = stmt.where(WaitlistEntry.student_id == current_user.id)
    elif current_user.role == RoleEnum.attending:
        stmt = stmt.where(WaitlistEntry.attending_id == current_user.id)
    return list(db.scalars(stmt))


@router.get("/waitlist/{entry_id}", response_model=WaitlistEntryOut)
def get_waitlist_entry(
    entry_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WaitlistEntry:
    return _get_visible_entry(db, entry_id, current_user)


@router.post("/waitlist/{entry_id}/cancel", response_model=WaitlistEntryOut)
def cancel_waitlist_entry(
    entry_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WaitlistEntry:
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

    if entry.status == WaitlistStatus.cancelled:
        raise HTTPException(status_code=409, detail="Waitlist entry is already cancelled")

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
    return entry
