from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.audit_log import AuditLog


def _enforce_rate_limit(
    db: Session,
    *,
    identifier: str,
    ip_address: str | None,
    action: str,
    max_attempts: int,
    window_minutes: int,
) -> None:
    """Raise 429 if (identifier, ip_address) has too many recent matching
    audit_log rows.

    There is no Redis or in-process counter in this stack; the audit_log
    table it already writes to doubles as the rate-limit store, so lockouts
    survive container restarts and work across multiple workers. Keying on
    the IP *in addition to* the identifier (not identifier alone) matters:
    otherwise anyone who merely knows a victim's email/identifier could
    lock their real account out from anywhere, since the block previously
    applied to the identifier globally regardless of who was making the
    requests.
    """
    window_start = datetime.now(UTC) - timedelta(minutes=window_minutes)

    count = db.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.attempted_identifier == identifier,
            AuditLog.ip_address == ip_address,
            AuditLog.action == action,
            AuditLog.created_at >= window_start,
        )
    )
    if count is not None and count >= max_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Try again later.",
        )


def enforce_login_rate_limit(
    db: Session, *, identifier: str, ip_address: str | None, failure_action: str
) -> None:
    _enforce_rate_limit(
        db,
        identifier=identifier,
        ip_address=ip_address,
        action=failure_action,
        max_attempts=settings.login_rate_limit_max_attempts,
        window_minutes=settings.login_rate_limit_window_minutes,
    )


def enforce_registration_rate_limit(db: Session, *, ip_address: str | None) -> None:
    """Same store/mechanism as the login limiter, keyed on IP alone (there's
    no existing account to scope a registration attempt to) -- caps both
    unbounded automated account creation and probing many emails for the
    409-vs-201 enumeration signal from one source.
    """
    _enforce_rate_limit(
        db,
        identifier="register",
        ip_address=ip_address,
        action="user_register_attempt",
        max_attempts=settings.registration_rate_limit_max_attempts,
        window_minutes=settings.registration_rate_limit_window_minutes,
    )
