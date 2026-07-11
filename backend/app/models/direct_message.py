import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DirectMessage(Base):
    __tablename__ = "direct_messages"
    __table_args__ = (
        CheckConstraint(
            "(sender_user_id IS NOT NULL) != (sender_patient_id IS NOT NULL)",
            name="ck_direct_messages_exactly_one_sender",
        ),
        UniqueConstraint("sequence", name="uq_direct_messages_sequence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # A patient has exactly one owning student, so the patient_id alone is
    # the thread key -- no separate "conversation" entity is needed.
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True
    )
    sender_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    sender_patient_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id"), nullable=True, index=True
    )

    body: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Same transaction-timestamp-tie fix as Notification.sequence -- messages
    # sent within one transaction would otherwise tie on created_at.
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False)

    # Messages are immutable/append-only, like audit_log -- created_at only,
    # not the mutable-record TimestampMixin (no updated_at, no edit endpoint).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
