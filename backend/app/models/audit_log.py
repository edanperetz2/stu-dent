import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        # Covers both of core/rate_limit.py's query shapes, run on every
        # login/registration attempt against a table that grows without
        # bound: (a) the per-(identifier, ip) check filters all four
        # columns as a full left-to-right prefix match; (b) the per-IP-only
        # check (registration's mass-flood ceiling) filters only
        # ip_address/action/created_at, skipping attempted_identifier --
        # leading with ip_address still lets that query use this index via
        # an Index Cond on ip_address with the rest applied as an in-index
        # filter, rather than a full table scan either way.
        Index(
            "ix_audit_log_ip_identifier_action_created",
            "ip_address",
            "attempted_identifier",
            "action",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    # Raw email attempted at login, kept even when it matched no account, so
    # rate limiting can key off an identifier that never resolved to a row.
    attempted_identifier: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    action: Mapped[str] = mapped_column(String, nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String, nullable=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String, nullable=True)

    # Python attribute can't be named `metadata` (reserved by DeclarativeBase);
    # the underlying column is still named `metadata` per the ERD.
    extra_data: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
