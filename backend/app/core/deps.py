import uuid
from collections.abc import Callable
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
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

    user_id = payload.get("sub")
    if user_id is None:
        raise _credentials_exception

    try:
        subject = uuid.UUID(user_id)
    except (ValueError, TypeError, AttributeError) as err:
        # A non-UUID `sub` (a forged/corrupted token) would otherwise raise
        # an unhandled 500 instead of the same 401 every other
        # malformed-credentials path here already returns. `uuid.UUID()`
        # raises ValueError for a malformed string, TypeError for `None`,
        # and AttributeError for a non-string JSON scalar (an int/list/dict
        # `sub` -- it calls `.replace()` on its argument before any type
        # check) -- all three need catching, not just the first two.
        raise _credentials_exception from err

    user = db.get(User, subject)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise _credentials_exception

    return user


def require_role(*roles: RoleEnum) -> Callable[..., User]:
    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
            )
        return current_user

    return _dependency
