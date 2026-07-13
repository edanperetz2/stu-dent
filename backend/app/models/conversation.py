import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import User


class ConversationKind(enum.StrEnum):
    direct = "direct"
    admin = "admin"
    group = "group"


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[ConversationKind] = mapped_column(
        Enum(ConversationKind, name="conversation_kind_enum", native_enum=True), nullable=False
    )
    # Group chats only; null for direct/admin threads.
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    # Deterministic dedup key so "get or create" never creates duplicate
    # threads for the same parties: for `direct`, the two participant IDs
    # sorted and joined; for `admin`, "admin:<owner_id>" (the shared inbox
    # is keyed by the non-admin party alone -- any active admin can see and
    # reply to it, see services/messaging.py). Null for `group` (a group
    # has no natural dedup key, and duplicates are fine -- each "New group"
    # click makes a distinct conversation).
    direct_key: Mapped[str | None] = mapped_column(String, unique=True, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("conversations.id"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), primary_key=True, index=True
    )
    # Everything in the conversation up to this timestamp is "read" by this
    # participant -- a per-participant high-water mark rather than a
    # per-message boolean, since a group conversation can have more than one
    # "other party" to read a message.
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("sequence", name="uq_messages_sequence"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # Same transaction-timestamp-tie fix as Notification.sequence/the old
    # DirectMessage.sequence -- messages sent within one transaction would
    # otherwise tie on created_at.
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False)

    # Messages are immutable/append-only, like audit_log -- created_at only,
    # no updated_at, no edit endpoint.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Eager-loaded: every message listing also needs "who sent it", so this
    # avoids an N+1 lookup per message in a conversation.
    sender: Mapped[User] = relationship("User", lazy="joined")

    @property
    def sender_name(self) -> str:
        return self.sender.full_name
