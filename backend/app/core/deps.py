import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import PrincipalType, decode_access_token
from app.database import get_db
from app.models.patient import Patient
from app.models.user import RoleEnum, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

_credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def _decode(token: str) -> dict[str, Any]:
    try:
        return decode_access_token(token)
    except jwt.PyJWTError as err:
        raise _credentials_exception from err


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    payload = _decode(token)

    if payload.get("principal_type") != PrincipalType.user.value:
        raise _credentials_exception

    user_id = payload.get("sub")
    if user_id is None:
        raise _credentials_exception

    user = db.get(User, uuid.UUID(user_id))
    if user is None or not user.is_active or user.deleted_at is not None:
        raise _credentials_exception

    return user


def get_current_patient(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> Patient:
    payload = _decode(token)

    if payload.get("principal_type") != PrincipalType.patient.value:
        raise _credentials_exception

    patient_id = payload.get("sub")
    if patient_id is None:
        raise _credentials_exception

    patient = db.get(Patient, uuid.UUID(patient_id))
    if patient is None or not patient.is_active or patient.deleted_at is not None:
        raise _credentials_exception

    return patient


@dataclass
class Principal:
    """Either a User or a Patient, for endpoints both can reach.

    Only one of `user`/`patient` is ever set, matching `kind`. The
    `actor_*_id` properties exist so routes can feed `record_audit_log`
    without branching on `kind` themselves.
    """

    kind: PrincipalType
    user: User | None = None
    patient: Patient | None = None

    @property
    def actor_user_id(self) -> uuid.UUID | None:
        return self.user.id if self.user else None

    @property
    def actor_patient_id(self) -> uuid.UUID | None:
        return self.patient.id if self.patient else None


def get_current_principal(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> Principal:
    payload = _decode(token)

    subject = payload.get("sub")
    if subject is None:
        raise _credentials_exception

    principal_type = payload.get("principal_type")
    if principal_type == PrincipalType.user.value:
        user = db.get(User, uuid.UUID(subject))
        if user is None or not user.is_active or user.deleted_at is not None:
            raise _credentials_exception
        return Principal(kind=PrincipalType.user, user=user)

    if principal_type == PrincipalType.patient.value:
        patient = db.get(Patient, uuid.UUID(subject))
        if patient is None or not patient.is_active or patient.deleted_at is not None:
            raise _credentials_exception
        return Principal(kind=PrincipalType.patient, patient=patient)

    raise _credentials_exception


def require_role(*roles: RoleEnum) -> Callable[..., User]:
    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
            )
        return current_user

    return _dependency
