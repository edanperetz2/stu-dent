import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Text,
    Uuid,
    func,
    literal_column,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class AppointmentStatus(enum.StrEnum):
    proposed = "proposed"
    awaiting_confirmation = "awaiting_confirmation"
    confirmed = "confirmed"
    cancelled = "cancelled"
    completed = "completed"
    no_show = "no_show"
    rescheduling_requested = "rescheduling_requested"


# Statuses that represent a real (non-cancelled, non-terminal-freed) hold on a
# resource. `proposed` is non-binding (a patient's request the student hasn't
# accepted yet); completed/no_show/cancelled free the slot. Only these three
# participate in the double-booking exclusion constraints below.
_ACTIVE_STATUSES = (
    AppointmentStatus.awaiting_confirmation,
    AppointmentStatus.confirmed,
    AppointmentStatus.rescheduling_requested,
)
_ACTIVE_STATUSES_SQL = ", ".join(f"'{s.value}'" for s in _ACTIVE_STATUSES)


def _time_range():
    return func.tstzrange(literal_column("start_time"), literal_column("end_time"))


class Appointment(TimestampMixin, Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_appointments_time_order"),
        ExcludeConstraint(
            ("student_id", "="),
            (_time_range(), "&&"),
            using="gist",
            where=text(f"status IN ({_ACTIVE_STATUSES_SQL})"),
            name="ex_appointments_student_overlap",
        ),
        ExcludeConstraint(
            ("patient_id", "="),
            (_time_range(), "&&"),
            using="gist",
            where=text(f"status IN ({_ACTIVE_STATUSES_SQL})"),
            name="ex_appointments_patient_overlap",
        ),
        ExcludeConstraint(
            ("attending_id", "="),
            (_time_range(), "&&"),
            using="gist",
            where=text(f"attending_id IS NOT NULL AND status IN ({_ACTIVE_STATUSES_SQL})"),
            name="ex_appointments_attending_overlap",
        ),
        ExcludeConstraint(
            ("room_id", "="),
            (_time_range(), "&&"),
            using="gist",
            where=text(f"room_id IS NOT NULL AND status IN ({_ACTIVE_STATUSES_SQL})"),
            name="ex_appointments_room_overlap",
        ),
        ExcludeConstraint(
            ("equipment_id", "="),
            (_time_range(), "&&"),
            using="gist",
            where=text(f"equipment_id IS NOT NULL AND status IN ({_ACTIVE_STATUSES_SQL})"),
            name="ex_appointments_equipment_overlap",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    attending_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    room_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rooms.id"), nullable=True, index=True
    )
    equipment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("equipment.id"), nullable=True, index=True
    )

    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    # Indexed: jobs/expiry.py filters on this every worker poll, against a
    # table that only grows (soft-delete convention, terminal rows never
    # removed).
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus, name="appointment_status_enum", native_enum=True),
        nullable=False,
        default=AppointmentStatus.proposed,
    )

    # Two independent confirmation gates, not new enum states: whichever
    # party must sign off (owning student for a patient-initiated request,
    # assigned attending for a supervised procedure) fills in their
    # timestamp; `services/scheduling.py::recompute_status` derives `status`
    # from these rather than routes setting status directly.
    student_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attending_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Set once a reminder job has sent a reminder, so it never re-sends.
    reminder_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
