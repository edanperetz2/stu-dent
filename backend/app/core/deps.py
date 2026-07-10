import uuid
from collections.abc import Callable

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


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as err:
        raise _credentials_exception from err

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
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as err:
        raise _credentials_exception from err

    if payload.get("principal_type") != PrincipalType.patient.value:
        raise _credentials_exception

    patient_id = payload.get("sub")
    if patient_id is None:
        raise _credentials_exception

    patient = db.get(Patient, uuid.UUID(patient_id))
    if patient is None or not patient.is_active or patient.deleted_at is not None:
        raise _credentials_exception

    return patient


def require_role(*roles: RoleEnum) -> Callable[..., User]:
    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
            )
        return current_user

    return _dependency
