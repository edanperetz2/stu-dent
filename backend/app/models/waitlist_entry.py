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
    Index,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.appointment import Appointment
from app.models.equipment import Equipment
from app.models.mixins import TimestampMixin
from app.models.room import Room
from app.models.user import User


class WaitlistStatus(enum.StrEnum):
    active = "active"
    booked = "booked"
    cancelled = "cancelled"


class WaitlistEntry(TimestampMixin, Base):
    """A record of a real appointment request that failed because something
    was unavailable -- never a speculative "I'd like a slot sometime"
    entry. `conflict_resource_types` is exactly what
    services/scheduling.py::find_conflicts found blocking this exact
    request at creation time; services/waitlist.py's auto-promotion logic
    re-runs that same check on every appointment cancellation and, once
    every original blocker is clear, builds a real Appointment from these
    same fields rather than just notifying the user to try again.
    """

    __tablename__ = "waitlist_entries"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_waitlist_entries_time_order"),
        UniqueConstraint("sequence", name="uq_waitlist_entries_sequence"),
        # Backs recheck_waitlist_for_freed_slot's hot query (status='active'
        # AND start_time < :end AND end_time > :start), which runs on every
        # cancel/reject/expiry -- previously an unindexed full scan + sort.
        Index("ix_waitlist_entries_status_start_time", "status", "start_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Same transaction-timestamp-tie fix as Message.sequence: entries
    # created within one transaction can share an identical created_at, so
    # first-come-first-served promotion ordering (see
    # services/waitlist.py::recheck_waitlist_after_cancellation) sorts by
    # this DB-generated, always-monotonic counter instead.
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False)

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

    # The exact requested slot -- not a broad window. If it's ever promoted
    # to a real Appointment, these values are copied over verbatim.
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Same meaning as Appointment.student_confirmed_at, captured at
    # creation time using the same rule create_appointment uses (set for a
    # student-made request, left null for a patient-made one) -- lets
    # auto-promotion hand off to recompute_status() for a correct derived
    # status instead of fabricating a confirmation nobody gave.
    student_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Which resource types were actually blocking this exact request when
    # it was submitted -- e.g. ["attending", "room"]. Drives the "why is
    # this here" display; re-derived (not blindly trusted) on every
    # creation via find_conflicts.
    conflict_resource_types: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)

    status: Mapped[WaitlistStatus] = mapped_column(
        Enum(WaitlistStatus, name="waitlist_status_enum", native_enum=True),
        nullable=False,
        default=WaitlistStatus.active,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resulting_appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("appointments.id"), nullable=True
    )

    student: Mapped[User] = relationship("User", foreign_keys=[student_id], lazy="joined")
    patient: Mapped[User] = relationship("User", foreign_keys=[patient_id], lazy="joined")
    attending: Mapped[User | None] = relationship(
        "User", foreign_keys=[attending_id], lazy="joined"
    )
    room: Mapped[Room | None] = relationship("Room", lazy="joined")
    equipment: Mapped[Equipment | None] = relationship("Equipment", lazy="joined")
    resulting_appointment: Mapped[Appointment | None] = relationship(
        "Appointment", foreign_keys=[resulting_appointment_id], lazy="joined"
    )

    @property
    def student_name(self) -> str:
        return self.student.full_name

    @property
    def patient_name(self) -> str:
        return self.patient.full_name

    @property
    def attending_name(self) -> str | None:
        return self.attending.full_name if self.attending else None

    @property
    def room_name(self) -> str | None:
        return self.room.name if self.room else None

    @property
    def equipment_name(self) -> str | None:
        return self.equipment.name if self.equipment else None
