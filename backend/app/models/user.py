import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class RoleEnum(enum.StrEnum):
    student = "student"
    attending = "attending"
    admin = "admin"
    patient = "patient"


class PreferredTimeOfDay(enum.StrEnum):
    morning = "morning"
    afternoon = "afternoon"
    evening = "evening"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[RoleEnum] = mapped_column(
        Enum(RoleEnum, name="role_enum", native_enum=True), nullable=False
    )
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # The following four columns are meaningless for student/attending/admin
    # and populated only when role == patient. Kept on `users` rather than a
    # separate table now that patients are a role, not a distinct principal
    # type -- see CLAUDE.md for why this changed from the original design.
    owner_student_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    # Set immediately when a student creates the patient directly (they
    # vouched for it); left NULL when a patient self-registers, picking a
    # student, until that student explicitly confirms the relationship.
    # A gate timestamp, not a new enum state -- same idiom as
    # Appointment.student_confirmed_at/attending_approved_at.
    owner_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    contact_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    preferred_time_of_day: Mapped[PreferredTimeOfDay | None] = mapped_column(
        Enum(PreferredTimeOfDay, name="preferred_time_of_day_enum", native_enum=True),
        nullable=True,
    )
