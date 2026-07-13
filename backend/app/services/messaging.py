import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation import (
    Conversation,
    ConversationKind,
    ConversationParticipant,
    Message,
)
from app.models.user import RoleEnum, User
from app.services.users import active_user_filters


def direct_key(user_id_a: uuid.UUID, user_id_b: uuid.UUID) -> str:
    return "-".join(sorted([str(user_id_a), str(user_id_b)]))


def admin_key(owner_id: uuid.UUID) -> str:
    return f"admin:{owner_id}"


def can_message_directly(a: User, b: User) -> bool:
    """Whether `a` and `b` are allowed a direct (peer-to-peer) thread --
    student<->their own patient, or student<->attending in either
    direction. Never patient<->attending, never same-role pairs (group
    chat is the mechanism for multi-student/attending conversation).
    Mirrors the old DM route's authorization exactly: no confirmation gate
    here -- an unconfirmed patient can still *view* the (empty) thread
    with their pending student; only *sending* is gated separately via
    require_confirmed_patient.
    """
    roles = {a.role, b.role}
    if roles == {RoleEnum.student, RoleEnum.patient}:
        student = a if a.role == RoleEnum.student else b
        patient = a if a.role == RoleEnum.patient else b
        return patient.owner_student_id == student.id
    if roles == {RoleEnum.student, RoleEnum.attending}:
        return True
    return False


def list_contacts(db: Session, current_user: User) -> list[User]:
    """Peer-to-peer contacts for the sidebar. The shared admin inbox is
    deliberately not part of this list -- every non-admin role always has
    exactly one fixed "Admin" entry (handled by the frontend), while an
    admin instead sees every other active user here, since any of them
    could have an admin-support thread.
    """
    if current_user.role == RoleEnum.student:
        patients = db.scalars(
            select(User).where(
                User.owner_student_id == current_user.id,
                *active_user_filters(RoleEnum.patient),
            )
        )
        attendings = db.scalars(select(User).where(*active_user_filters(RoleEnum.attending)))
        return [*patients, *attendings]
    if current_user.role == RoleEnum.attending:
        return list(db.scalars(select(User).where(*active_user_filters(RoleEnum.student))))
    if current_user.role == RoleEnum.patient:
        if current_user.owner_student_id is None:
            return []
        owner = db.scalar(
            select(User).where(
                User.id == current_user.owner_student_id, *active_user_filters(RoleEnum.student)
            )
        )
        return [owner] if owner is not None else []
    # admin
    return list(
        db.scalars(
            select(User).where(
                *active_user_filters(RoleEnum.student, RoleEnum.attending, RoleEnum.patient)
            )
        )
    )


def get_or_create_conversation(
    db: Session,
    *,
    kind: ConversationKind,
    key: str,
    participant_ids: list[uuid.UUID],
    title: str | None = None,
) -> Conversation:
    conversation = db.scalar(select(Conversation).where(Conversation.direct_key == key))
    if conversation is not None:
        return conversation

    conversation = Conversation(kind=kind, direct_key=key, title=title)
    db.add(conversation)
    db.flush()
    for user_id in participant_ids:
        db.add(ConversationParticipant(conversation_id=conversation.id, user_id=user_id))
    db.flush()
    return conversation


def create_group_conversation(
    db: Session, *, title: str, participant_ids: list[uuid.UUID]
) -> Conversation:
    conversation = Conversation(kind=ConversationKind.group, title=title)
    db.add(conversation)
    db.flush()
    for user_id in set(participant_ids):
        db.add(ConversationParticipant(conversation_id=conversation.id, user_id=user_id))
    db.flush()
    return conversation


def ensure_participant(db: Session, conversation: Conversation, user_id: uuid.UUID) -> None:
    exists = db.get(ConversationParticipant, (conversation.id, user_id))
    if exists is None:
        db.add(ConversationParticipant(conversation_id=conversation.id, user_id=user_id))
        db.flush()


def touch_read(
    db: Session, conversation: Conversation, user_id: uuid.UUID
) -> ConversationParticipant:
    """Mark `user_id` caught up on `conversation` as of now. Idempotent,
    and creates the participant row if this is their first-ever visit
    (e.g. an admin opening a user's support thread for the first time).
    """
    participant = db.get(ConversationParticipant, (conversation.id, user_id))
    if participant is None:
        participant = ConversationParticipant(conversation_id=conversation.id, user_id=user_id)
        db.add(participant)
    participant.last_read_at = datetime.now(UTC)
    db.flush()
    return participant


def list_conversation_messages(db: Session, conversation_id: uuid.UUID) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.sequence.asc())
    )
    return list(db.scalars(stmt))


def list_participants(db: Session, conversation_id: uuid.UUID) -> list[User]:
    stmt = (
        select(User)
        .join(ConversationParticipant, ConversationParticipant.user_id == User.id)
        .where(ConversationParticipant.conversation_id == conversation_id)
    )
    return list(db.scalars(stmt))


def active_admin_ids(db: Session) -> list[uuid.UUID]:
    return list(db.scalars(select(User.id).where(*active_user_filters(RoleEnum.admin))))


def is_participant(db: Session, conversation_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    return db.get(ConversationParticipant, (conversation_id, user_id)) is not None
