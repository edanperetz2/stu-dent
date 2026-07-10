import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_patient, require_role
from app.core.rate_limit import enforce_login_rate_limit
from app.core.security import PrincipalType, create_access_token, hash_password, verify_password
from app.database import get_db
from app.models.patient import Patient
from app.models.user import RoleEnum, User
from app.schemas.auth import TokenOut
from app.schemas.patient import (
    PatientCreate,
    PatientCredentialsIn,
    PatientLoginIn,
    PatientOut,
    PatientUpdate,
)
from app.services.audit import record_audit_log

router = APIRouter(tags=["patients"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _get_owned_patient(db: Session, patient_id: uuid.UUID, owner: User) -> Patient:
    patient = db.scalar(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.owner_student_id == owner.id,
            Patient.deleted_at.is_(None),
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
) -> Patient:
    patient = Patient(
        owner_student_id=current_user.id,
        full_name=payload.full_name,
        contact_phone=payload.contact_phone,
    )
    db.add(patient)
    db.flush()

    record_audit_log(
        db,
        action="patient_create",
        actor_user_id=current_user.id,
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
) -> list[Patient]:
    return list(
        db.scalars(
            select(Patient).where(
                Patient.owner_student_id == current_user.id,
                Patient.deleted_at.is_(None),
            )
        )
    )


@router.get("/patients/me", response_model=PatientOut)
def read_current_patient(current_patient: Patient = Depends(get_current_patient)) -> Patient:
    return current_patient


@router.get("/patients/{patient_id}", response_model=PatientOut)
def get_patient(
    patient_id: uuid.UUID,
    current_user: User = Depends(require_role(RoleEnum.student)),
    db: Session = Depends(get_db),
) -> Patient:
    return _get_owned_patient(db, patient_id, current_user)


@router.patch("/patients/{patient_id}", response_model=PatientOut)
def update_patient(
    patient_id: uuid.UUID,
    payload: PatientUpdate,
    current_user: User = Depends(require_role(RoleEnum.student)),
    db: Session = Depends(get_db),
) -> Patient:
    patient = _get_owned_patient(db, patient_id, current_user)

    if payload.full_name is not None:
        patient.full_name = payload.full_name
    if payload.contact_phone is not None:
        patient.contact_phone = payload.contact_phone

    record_audit_log(
        db,
        action="patient_update",
        actor_user_id=current_user.id,
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
        actor_user_id=current_user.id,
        target_type="patient",
        target_id=patient.id,
    )
    db.commit()


@router.post("/patients/{patient_id}/credentials", response_model=PatientOut)
def set_patient_credentials(
    patient_id: uuid.UUID,
    payload: PatientCredentialsIn,
    current_user: User = Depends(require_role(RoleEnum.student)),
    db: Session = Depends(get_db),
) -> Patient:
    patient = _get_owned_patient(db, patient_id, current_user)

    email = payload.email.lower()
    existing = db.scalar(select(Patient).where(Patient.email == email, Patient.id != patient.id))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

    patient.email = email
    patient.hashed_password = hash_password(payload.password)

    record_audit_log(
        db,
        action="patient_credentials_set",
        actor_user_id=current_user.id,
        target_type="patient",
        target_id=patient.id,
    )
    db.commit()
    db.refresh(patient)
    return patient


@router.post("/patients/login", response_model=TokenOut)
def patient_login(
    payload: PatientLoginIn, request: Request, db: Session = Depends(get_db)
) -> TokenOut:
    email = payload.email.lower()
    ip = _client_ip(request)

    enforce_login_rate_limit(db, identifier=email, failure_action="patient_login_failure")

    patient = db.scalar(select(Patient).where(Patient.email == email, Patient.deleted_at.is_(None)))
    if (
        patient is None
        or not patient.is_active
        or patient.hashed_password is None
        or not verify_password(payload.password, patient.hashed_password)
    ):
        record_audit_log(
            db,
            action="patient_login_failure",
            actor_patient_id=patient.id if patient else None,
            attempted_identifier=email,
            ip_address=ip,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
        )

    record_audit_log(
        db,
        action="patient_login_success",
        actor_patient_id=patient.id,
        attempted_identifier=email,
        ip_address=ip,
    )
    db.commit()

    token = create_access_token(subject=patient.id, principal_type=PrincipalType.patient)
    return TokenOut(access_token=token)
