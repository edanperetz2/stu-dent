import uuid

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class ForumPostVote(TimestampMixin, Base):
    __tablename__ = "forum_post_votes"
    __table_args__ = (
        CheckConstraint("value IN (1, -1)", name="ck_forum_post_votes_value"),
        UniqueConstraint("post_id", "student_id", name="uq_forum_post_votes_post_student"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("forum_posts.id"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    value: Mapped[int] = mapped_column(SmallInteger, nullable=False)
