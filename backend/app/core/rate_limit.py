from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.audit_log import AuditLog


def _count_recent(
    db: Session,
    *,
    ip_address: str | None,
    action: str,
    window_minutes: int,
    identifier: str | None = None,
) -> int:
    """Count matching audit_log rows in the trailing window. `identifier`
    is optional: omitting it counts every row for this IP regardless of
    which identifier (email) each attempt named, for an IP-only ceiling.

    There is no Redis or in-process counter in this stack; the audit_log
    table it already writes to doubles as the rate-limit store, so lockouts
    survive container restarts and work across multiple workers.
    """
    window_start = datetime.now(UTC) - timedelta(minutes=window_minutes)
    stmt = (
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.ip_address == ip_address,
            AuditLog.action == action,
            AuditLog.created_at >= window_start,
        )
    )
    if identifier is not None:
        stmt = stmt.where(AuditLog.attempted_identifier == identifier)
    return db.scalar(stmt) or 0


def _raise_too_many() -> None:
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many attempts. Try again later.",
    )


def enforce_login_rate_limit(
    db: Session, *, identifier: str, ip_address: str | None, failure_action: str
) -> None:
    """Raise 429 if (identifier, ip_address) has too many recent failures.

    Keying on the IP *in addition to* the identifier (not identifier alone)
    matters: otherwise anyone who merely knows a victim's email could lock
    their real account out from anywhere, since the block previously
    applied to the identifier globally regardless of who was making the
    requests.
    """
    count = _count_recent(
        db,
        ip_address=ip_address,
        action=failure_action,
        window_minutes=settings.login_rate_limit_window_minutes,
        identifier=identifier,
    )
    if count >= settings.login_rate_limit_max_attempts:
        _raise_too_many()


def enforce_registration_rate_limit(db: Session, *, email: str, ip_address: str | None) -> None:
    """Two layered checks, not one IP-only counter:

    1. A per-(email, IP) check with a low threshold -- still stops
       repeated probing/spam aimed at one specific email (registration
       attempts, success or the 409-already-registered path, are recorded
       under the real email being registered, not a shared placeholder).
    2. A per-IP-only check (no identifier filter) with a much higher
       threshold -- still stops a genuine mass-registration/enumeration
       flood from one source, without bunching a shared classroom/clinic
       WiFi's many *different* real registrants into the same tight
       counter (that used to lock out the last people through the door
       purely for sharing an IP with earlier legitimate signups).
    """
    per_email_count = _count_recent(
        db,
        ip_address=ip_address,
        action="user_register_attempt",
        window_minutes=settings.registration_rate_limit_window_minutes,
        identifier=email,
    )
    if per_email_count >= settings.registration_rate_limit_max_attempts:
        _raise_too_many()

    per_ip_count = _count_recent(
        db,
        ip_address=ip_address,
        action="user_register_attempt",
        window_minutes=settings.registration_rate_limit_window_minutes,
    )
    if per_ip_count >= settings.registration_rate_limit_max_attempts_per_ip:
        _raise_too_many()


def enforce_password_reset_rate_limit(db: Session, *, email: str, ip_address: str | None) -> None:
    """Same two-layer shape as enforce_registration_rate_limit -- a tight
    per-(email, IP) check plus a much higher per-IP-only ceiling. Recorded
    under `password_reset_request` regardless of whether the email actually
    matches a real account (see the route), so this also doubles as the
    limiter for someone probing which emails have accounts.
    """
    per_email_count = _count_recent(
        db,
        ip_address=ip_address,
        action="password_reset_request",
        window_minutes=settings.password_reset_rate_limit_window_minutes,
        identifier=email,
    )
    if per_email_count >= settings.password_reset_rate_limit_max_attempts:
        _raise_too_many()

    per_ip_count = _count_recent(
        db,
        ip_address=ip_address,
        action="password_reset_request",
        window_minutes=settings.password_reset_rate_limit_window_minutes,
    )
    if per_ip_count >= settings.password_reset_rate_limit_max_attempts_per_ip:
        _raise_too_many()
