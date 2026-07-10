import uuid
from datetime import time

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, Time, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class StudentAvailability(TimestampMixin, Base):
    __tablename__ = "student_availability"
    __table_args__ = (CheckConstraint("end_time > start_time", name="ck_availability_time_order"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    # 0 = Monday ... 6 = Sunday
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
