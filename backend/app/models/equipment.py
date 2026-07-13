import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class Equipment(TimestampMixin, Base):
    __tablename__ = "equipment"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    equipment_type: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Set alongside is_active=False for a scheduled (rather than indefinite)
    # deactivation; jobs/reactivation.py flips is_active back to True and
    # clears this once it passes. Null for an indefinite deactivation (or
    # while active).
    inactive_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
