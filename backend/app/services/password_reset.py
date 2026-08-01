import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import hash_password
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.services.audit import record_audit_log
from app.services.email import send_email

# secrets.token_urlsafe(32) -- 32 bytes of real entropy, far more than
# enough that a SHA-256 digest of it isn't meaningfully brute-forceable,
# unlike a low-entropy human password (see PasswordResetToken.token_hash's
# own comment for why that rules out argon2 here).
_TOKEN_BYTES = 32


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def request_password_reset(db: Session, *, email: str, ip_address: str | None = None) -> None:
    """Always succeeds from the caller's perspective, whether or not `email`
    matches a real account -- enumeration resistance, same spirit as the
    DUMMY_PASSWORD_HASH timing mitigation on login. Only a real, active
    match gets a minted token + email; either way an audit_log row is
    written and committed, since the route's rate limiter depends on it
    being recorded regardless of outcome -- `ip_address` must be threaded
    through to that row, or enforce_password_reset_rate_limit's per-IP
    filter never matches anything it wrote.
    """
    user = db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if user is not None and user.is_active:
        raw_token = secrets.token_urlsafe(_TOKEN_BYTES)
        expires_at = datetime.now(UTC) + timedelta(
            minutes=settings.password_reset_token_expire_minutes
        )
        db.add(
            PasswordResetToken(
                user_id=user.id, token_hash=_hash_token(raw_token), expires_at=expires_at
            )
        )

        base_url = settings.frontend_origin_list[0] if settings.frontend_origin_list else ""
        reset_link = f"{base_url}/reset-password?token={raw_token}"
        send_email(
            to=user.email,
            subject="Reset your Stu-Dent password",
            body=(
                "Someone requested a password reset for your Stu-Dent account. "
                f"If this was you, use the link below within "
                f"{settings.password_reset_token_expire_minutes} minutes:\n\n{reset_link}\n\n"
                "If you didn't request this, you can safely ignore this email -- "
                "your password hasn't been changed."
            ),
        )

    record_audit_log(
        db, action="password_reset_request", attempted_identifier=email, ip_address=ip_address
    )
    db.commit()


def confirm_password_reset(db: Session, *, raw_token: str, new_password: str) -> bool:
    """Returns False for a missing/expired/already-used token or a since-
    deactivated account -- a plain "invalid or expired" outcome the route
    turns into a 400, keeping this service free of HTTP concerns. True on a
    real reset.
    """
    token = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash_token(raw_token))
    )
    now = datetime.now(UTC)
    if token is None or token.used_at is not None or token.expires_at < now:
        return False

    user = db.get(User, token.user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        return False

    user.hashed_password = hash_password(new_password)
    token.used_at = now
    record_audit_log(
        db,
        action="password_reset_success",
        actor_id=user.id,
        target_type="user",
        target_id=user.id,
    )
    db.commit()
    return True
