import uuid

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class ForumCommentVote(TimestampMixin, Base):
    __tablename__ = "forum_comment_votes"
    __table_args__ = (
        CheckConstraint("value IN (1, -1)", name="ck_forum_comment_votes_value"),
        UniqueConstraint("comment_id", "student_id", name="uq_forum_comment_votes_comment_student"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("forum_comments.id"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    value: Mapped[int] = mapped_column(SmallInteger, nullable=False)
