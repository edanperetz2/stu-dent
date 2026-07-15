import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.appointment import Appointment
from app.models.mixins import TimestampMixin
from app.models.user import User


class FeedbackAuthorRole(enum.StrEnum):
    patient = "patient"
    attending = "attending"


class Feedback(TimestampMixin, Base):
    """Qualitative, post-completion feedback from a patient or attending
    about the treating student -- deliberately no rating/grade of any kind,
    just three guiding-question text fields. `student_id`/`author_role` are
    copied from the appointment at creation (immutable after) so the two
    real list queries -- "all feedback about student X" and "all feedback
    authored by user Y" -- don't need a join through `appointments`.
    """

    __tablename__ = "feedback"
    __table_args__ = (
        UniqueConstraint("appointment_id", "author_id", name="uq_feedback_appointment_author"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    appointment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("appointments.id"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    author_role: Mapped[FeedbackAuthorRole] = mapped_column(
        Enum(FeedbackAuthorRole, name="feedback_author_role_enum", native_enum=True),
        nullable=False,
    )

    went_well: Mapped[str] = mapped_column(Text, nullable=False)
    could_improve: Mapped[str] = mapped_column(Text, nullable=False)
    additional_comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    appointment: Mapped[Appointment] = relationship("Appointment", lazy="joined")
    student: Mapped[User] = relationship("User", foreign_keys=[student_id], lazy="joined")
    author: Mapped[User] = relationship("User", foreign_keys=[author_id], lazy="joined")

    @property
    def student_name(self) -> str:
        return self.student.full_name

    @property
    def author_name(self) -> str:
        return self.author.full_name

    @property
    def patient_id(self) -> uuid.UUID:
        return self.appointment.patient_id

    @property
    def patient_name(self) -> str:
        return self.appointment.patient_name

    @property
    def appointment_start_time(self):
        return self.appointment.start_time
