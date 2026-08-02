import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class ReportPeriodType(enum.StrEnum):
    weekly = "weekly"
    monthly = "monthly"
    ad_hoc = "ad_hoc"


class ReportContentSource(enum.StrEnum):
    ai = "ai"
    fallback_summary = "fallback_summary"
    unsupported = "unsupported"
    unavailable = "unavailable"
    # A real, supported question type was classified, but the date-range
    # phrase the model extracted (e.g. "yesterday") isn't one of the
    # handful resolve_date_range() recognizes -- distinct from `unavailable`
    # (nothing wrong with Ollama) and `unsupported` (the question itself
    # was a real, answerable type). Without this, the ad-hoc path used to
    # silently fall back to a generic 30-day window with no way for the
    # viewer to tell the answered range wasn't the one they actually asked
    # about.
    unresolved_date_range = "unresolved_date_range"


class Report(TimestampMixin, Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    recipient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    period_type: Mapped[ReportPeriodType] = mapped_column(
        Enum(ReportPeriodType, name="report_period_type_enum", native_enum=True),
        nullable=False,
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Populated only for period_type == ad_hoc -- the free-text question
    # this report answers. NULL for weekly/monthly auto-generated reports.
    question: Mapped[str | None] = mapped_column(Text, nullable=True)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # What actually produced `content` -- a real model narration, the
    # deterministic plain-English fallback (model unreachable/unusable), a
    # genuinely unsupported ad-hoc question, or the assistant being down
    # entirely when an ad-hoc question was being classified. Lets a viewer
    # tell these apart instead of only inferring it from the prose.
    content_source: Mapped[ReportContentSource] = mapped_column(
        Enum(ReportContentSource, name="report_content_source_enum", native_enum=True),
        nullable=False,
        server_default=text("'ai'"),
    )
