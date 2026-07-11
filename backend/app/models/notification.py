import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class NotificationType(enum.StrEnum):
    appointment_reminder = "appointment_reminder"
    appointment_expired = "appointment_expired"
    waitlist_slot_available = "waitlist_slot_available"


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "(recipient_user_id IS NOT NULL) != (recipient_patient_id IS NOT NULL)",
            name="ck_notifications_exactly_one_recipient",
        ),
        UniqueConstraint("sequence", name="uq_notifications_sequence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Postgres's now()/CURRENT_TIMESTAMP is the transaction start time, so
    # several notifications inserted in one transaction (e.g. one
    # cancellation matching multiple waitlist entries) share the same
    # created_at. This monotonic sequence breaks ties for "newest first"
    # ordering; it's not the primary key so routes still address rows by
    # the UUID `id`.
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False)

    recipient_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    recipient_patient_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id"), nullable=True, index=True
    )

    notification_type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type_enum", native_enum=True),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    related_appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("appointments.id"), nullable=True, index=True
    )

    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
