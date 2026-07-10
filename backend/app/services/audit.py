import uuid

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def record_audit_log(
    db: Session,
    action: str,
    *,
    actor_user_id: uuid.UUID | None = None,
    actor_patient_id: uuid.UUID | None = None,
    attempted_identifier: str | None = None,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    extra_data: dict | None = None,
) -> AuditLog:
    """Stage an audit_log row on `db` without committing.

    Callers are expected to commit alongside whatever primary write this
    entry documents, so the two land in the same transaction.
    """
    entry = AuditLog(
        action=action,
        actor_user_id=actor_user_id,
        actor_patient_id=actor_patient_id,
        attempted_identifier=attempted_identifier,
        target_type=target_type,
        target_id=target_id,
        ip_address=ip_address,
        extra_data=extra_data,
    )
    db.add(entry)
    return entry
