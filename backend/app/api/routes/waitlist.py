import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import Principal, get_current_principal
from app.core.security import PrincipalType
from app.database import get_db
from app.models.user import RoleEnum
from app.models.waitlist_entry import WaitlistEntry, WaitlistStatus
from app.schemas.waitlist import WaitlistEntryCreate, WaitlistEntryOut
from app.services.audit import record_audit_log
from app.services.scheduling import validate_participants

router = APIRouter(tags=["waitlist"])


def _is_visible(entry: WaitlistEntry, principal: Principal) -> bool:
    if principal.kind == PrincipalType.patient:
        return entry.patient_id == principal.patient.id

    user = principal.user
    if user.role == RoleEnum.admin:
        return True
    if user.role == RoleEnum.student:
        return entry.student_id == user.id
    if user.role == RoleEnum.attending:
        return entry.attending_id == user.id
    return False


def _get_visible_entry(db: Session, entry_id: uuid.UUID, principal: Principal) -> WaitlistEntry:
    entry = db.get(WaitlistEntry, entry_id)
    if entry is None or not _is_visible(entry, principal):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waitlist entry not found"
        )
    return entry


@router.post("/waitlist", response_model=WaitlistEntryOut, status_code=status.HTTP_201_CREATED)
def create_waitlist_entry(
    payload: WaitlistEntryCreate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> WaitlistEntry:
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=422, detail="end_time must be after start_time")

    if principal.kind == PrincipalType.patient:
        student_id = principal.patient.owner_student_id
        patient_id = principal.patient.id
    else:
        if principal.user.role != RoleEnum.student:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only students or patients can create waitlist entries",
            )
        if payload.patient_id is None:
            raise HTTPException(status_code=422, detail="patient_id is required")
        student_id = principal.user.id
        patient_id = payload.patient_id

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
        actor_user_id=principal.actor_user_id,
        actor_patient_id=principal.actor_patient_id,
        target_type="waitlist_entry",
        target_id=entry.id,
    )
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/waitlist", response_model=list[WaitlistEntryOut])
def list_waitlist_entries(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[WaitlistEntry]:
    stmt = select(WaitlistEntry)
    if principal.kind == PrincipalType.patient:
        stmt = stmt.where(WaitlistEntry.patient_id == principal.patient.id)
    elif principal.user.role == RoleEnum.student:
        stmt = stmt.where(WaitlistEntry.student_id == principal.user.id)
    elif principal.user.role == RoleEnum.attending:
        stmt = stmt.where(WaitlistEntry.attending_id == principal.user.id)
    return list(db.scalars(stmt))


@router.get("/waitlist/{entry_id}", response_model=WaitlistEntryOut)
def get_waitlist_entry(
    entry_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> WaitlistEntry:
    return _get_visible_entry(db, entry_id, principal)


@router.post("/waitlist/{entry_id}/cancel", response_model=WaitlistEntryOut)
def cancel_waitlist_entry(
    entry_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> WaitlistEntry:
    entry = _get_visible_entry(db, entry_id, principal)

    is_owning_student = (
        principal.kind == PrincipalType.user
        and principal.user.role == RoleEnum.student
        and entry.student_id == principal.user.id
    )
    is_self_patient = (
        principal.kind == PrincipalType.patient and entry.patient_id == principal.patient.id
    )
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
        actor_user_id=principal.actor_user_id,
        actor_patient_id=principal.actor_patient_id,
        target_type="waitlist_entry",
        target_id=entry.id,
    )
    db.commit()
    db.refresh(entry)
    return entry
