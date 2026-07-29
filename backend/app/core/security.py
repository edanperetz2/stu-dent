import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import settings

_password_hasher = PasswordHasher()

# A real argon2 hash of an arbitrary, never-used password -- verified
# against on a login attempt for an email that doesn't exist, so that path
# costs the same argon2 work as a real wrong-password attempt. Without
# this, skipping verify_password() entirely for a nonexistent account made
# that response measurably faster, letting an attacker enumerate
# registered emails purely from login response timing.
DUMMY_PASSWORD_HASH = PasswordHasher().hash("not-a-real-account-timing-placeholder")


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return _password_hasher.verify(hashed_password, password)
    except VerifyMismatchError:
        return False


def create_access_token(subject: uuid.UUID, role: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(subject),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
