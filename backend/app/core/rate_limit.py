from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.audit_log import AuditLog


def enforce_login_rate_limit(db: Session, *, identifier: str, failure_action: str) -> None:
    """Raise 429 if `identifier` has too many recent failure rows in audit_log.

    There is no Redis or in-process counter in this stack; the audit_log
    table it already writes to doubles as the rate-limit store, so lockouts
    survive container restarts and work across multiple workers.
    """
    window_start = datetime.now(UTC) - timedelta(minutes=settings.login_rate_limit_window_minutes)

    count = db.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.attempted_identifier == identifier,
            AuditLog.action == failure_action,
            AuditLog.created_at >= window_start,
        )
    )
    if count is not None and count >= settings.login_rate_limit_max_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again later.",
        )
