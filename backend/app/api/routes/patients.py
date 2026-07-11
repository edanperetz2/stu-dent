import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.core.security import hash_password
from app.database import get_db
from app.models.user import RoleEnum, User
from app.schemas.patient import PatientCreate, PatientOut, PatientUpdate
from app.services.audit import record_audit_log

router = APIRouter(tags=["patients"])


def _get_owned_patient(db: Session, patient_id: uuid.UUID, owner: User) -> User:
    patient = db.scalar(
        select(User).where(
            User.id == patient_id,
            User.role == RoleEnum.patient,
            User.owner_student_id == owner.id,
            User.deleted_at.is_(None),
        )
    )
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


@router.post("/patients", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: PatientCreate,
    current_user: User = Depends(require_role(RoleEnum.student)),
    db: Session = Depends(get_db),
) -> User:
    email = payload.email.lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    patient = User(
        email=email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=RoleEnum.patient,
        owner_student_id=current_user.id,
        owner_confirmed_at=datetime.now(UTC),
        contact_phone=payload.contact_phone,
    )
    db.add(patient)
    db.flush()

    record_audit_log(
        db,
        action="patient_create",
        actor_id=current_user.id,
        target_type="patient",
        target_id=patient.id,
    )
    db.commit()
    db.refresh(patient)
    return patient


@router.get("/patients", response_model=list[PatientOut])
def list_patients(
    current_user: User = Depends(require_role(RoleEnum.student)),
    db: Session = Depends(get_db),
) -> list[User]:
    return list(
        db.scalars(
            select(User).where(
                User.role == RoleEnum.patient,
                User.owner_student_id == current_user.id,
                User.deleted_at.is_(None),
            )
        )
    )


@router.get("/patients/{patient_id}", response_model=PatientOut)
def get_patient(
    patient_id: uuid.UUID,
    current_user: User = Depends(require_role(RoleEnum.student)),
    db: Session = Depends(get_db),
) -> User:
    return _get_owned_patient(db, patient_id, current_user)


@router.patch("/patients/{patient_id}", response_model=PatientOut)
def update_patient(
    patient_id: uuid.UUID,
    payload: PatientUpdate,
    current_user: User = Depends(require_role(RoleEnum.student)),
    db: Session = Depends(get_db),
) -> User:
    patient = _get_owned_patient(db, patient_id, current_user)

    if payload.full_name is not None:
        patient.full_name = payload.full_name
    if payload.contact_phone is not None:
        patient.contact_phone = payload.contact_phone
    if payload.preferred_time_of_day is not None:
        patient.preferred_time_of_day = payload.preferred_time_of_day

    record_audit_log(
        db,
        action="patient_update",
        actor_id=current_user.id,
        target_type="patient",
        target_id=patient.id,
    )
    db.commit()
    db.refresh(patient)
    return patient


@router.delete("/patients/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patient(
    patient_id: uuid.UUID,
    current_user: User = Depends(require_role(RoleEnum.student)),
    db: Session = Depends(get_db),
) -> None:
    patient = _get_owned_patient(db, patient_id, current_user)
    patient.deleted_at = datetime.now(UTC)

    record_audit_log(
        db,
        action="patient_delete",
        actor_id=current_user.id,
        target_type="patient",
        target_id=patient.id,
    )
    db.commit()


@router.post("/patients/{patient_id}/confirm", response_model=PatientOut)
def confirm_patient(
    patient_id: uuid.UUID,
    current_user: User = Depends(require_role(RoleEnum.student)),
    db: Session = Depends(get_db),
) -> User:
    """Confirm a patient who self-registered under this student, picked up
    from the pending state left by POST /auth/register. A no-op (not an
    error) if already confirmed, so the button can be clicked idempotently.
    """
    patient = _get_owned_patient(db, patient_id, current_user)

    if patient.owner_confirmed_at is None:
        patient.owner_confirmed_at = datetime.now(UTC)

        record_audit_log(
            db,
            action="patient_confirm",
            actor_id=current_user.id,
            target_type="patient",
            target_id=patient.id,
        )
        db.commit()
        db.refresh(patient)
    return patient
