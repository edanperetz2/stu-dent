import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Text, Uuid
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
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

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
