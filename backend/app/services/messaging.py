import uuid
from datetime import UTC, datetime

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.models.conversation import (
    Conversation,
    ConversationKind,
    ConversationParticipant,
    Message,
)
from app.models.user import RoleEnum, User
from app.realtime.events import publish
from app.services.audit import record_audit_log
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


def touch_unread(
    db: Session, conversation: Conversation, user_id: uuid.UUID
) -> ConversationParticipant:
    """The explicit "mark unread" counterpart to touch_read -- clears the
    high-water mark entirely rather than advancing it, so every message in
    the conversation counts as unread again (see unread_message_count).
    """
    participant = db.get(ConversationParticipant, (conversation.id, user_id))
    if participant is None:
        participant = ConversationParticipant(conversation_id=conversation.id, user_id=user_id)
        db.add(participant)
    participant.last_read_at = None
    db.flush()
    return participant


def unread_message_count(db: Session, user_id: uuid.UUID) -> int:
    """Total unread messages across every conversation `user_id` is in --
    drives the Messages nav badge. A message counts as unread if it wasn't
    sent by `user_id` and either the participant has never read the
    conversation, or it arrived after their last_read_at high-water mark.

    The shared admin inbox is a special case: `get_or_create_conversation`
    deliberately never adds any specific admin as a participant when the
    thread is first created (any active admin can pick it up, see
    can_message_directly's docstring and the admin routes) -- an admin only
    gets a real participant row once they've touched that particular
    thread via touch_read/touch_unread. Without this, a thread no admin
    has opened yet would never count as unread for anyone.
    """
    stmt = (
        select(func.count(Message.id))
        .join(
            ConversationParticipant,
            ConversationParticipant.conversation_id == Message.conversation_id,
        )
        .where(
            ConversationParticipant.user_id == user_id,
            Message.sender_id != user_id,
            or_(
                ConversationParticipant.last_read_at.is_(None),
                Message.created_at > ConversationParticipant.last_read_at,
            ),
        )
    )
    count = db.scalar(stmt) or 0

    user = db.get(User, user_id)
    if user is not None and user.role == RoleEnum.admin:
        untouched_stmt = (
            select(func.count(Message.id))
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(
                Conversation.kind == ConversationKind.admin,
                Message.sender_id != user_id,
                ~exists().where(
                    ConversationParticipant.conversation_id == Conversation.id,
                    ConversationParticipant.user_id == user_id,
                ),
            )
        )
        count += db.scalar(untouched_stmt) or 0

    return count


def list_thread_summaries(db: Session, current_user: User) -> list[dict]:
    """One entry per conversation `current_user` is meaningfully part of --
    its target-key (matching the frontend's targetKey()), the timestamp of
    the most recent message in it, and whether it currently counts as
    unread (same rule as unread_message_count, including the untouched
    shared-admin-thread case). Drives the Messages sidebar: unread threads
    first, then most-recent-activity first.
    """
    touched_ids = set(
        db.scalars(
            select(ConversationParticipant.conversation_id).where(
                ConversationParticipant.user_id == current_user.id
            )
        )
    )

    untouched_ids: set[uuid.UUID] = set()
    if current_user.role == RoleEnum.admin:
        untouched_ids = set(
            db.scalars(
                select(Conversation.id).where(
                    Conversation.kind == ConversationKind.admin,
                    ~exists().where(
                        ConversationParticipant.conversation_id == Conversation.id,
                        ConversationParticipant.user_id == current_user.id,
                    ),
                )
            )
        )

    all_ids = touched_ids | untouched_ids
    if not all_ids:
        return []

    last_message_at = dict(
        db.execute(
            select(Message.conversation_id, func.max(Message.created_at))
            .where(Message.conversation_id.in_(all_ids))
            .group_by(Message.conversation_id)
        ).all()
    )

    unread_ids = set(
        db.scalars(
            select(Message.conversation_id)
            .join(
                ConversationParticipant,
                ConversationParticipant.conversation_id == Message.conversation_id,
            )
            .where(
                ConversationParticipant.user_id == current_user.id,
                Message.sender_id != current_user.id,
                or_(
                    ConversationParticipant.last_read_at.is_(None),
                    Message.created_at > ConversationParticipant.last_read_at,
                ),
            )
            .distinct()
        )
    )
    # An untouched admin thread has never been read at all, so any message
    # in it is unread -- last_read_by_conversation has no entry for these.
    unread_ids |= {conv_id for conv_id in untouched_ids if conv_id in last_message_at}

    summaries: list[dict] = []
    for conversation in db.scalars(select(Conversation).where(Conversation.id.in_(all_ids))):
        if conversation.kind == ConversationKind.group:
            key = f"group:{conversation.id}"
        elif conversation.kind == ConversationKind.admin:
            # direct_key is already "admin:<owner_id>" (see admin_key) --
            # the owner (always non-admin) sees their own thread as
            # "admin:self", matching the frontend's targetKey() for the
            # fixed "Admin" row; any admin viewing it sees the owner's id.
            owner_id = conversation.direct_key.removeprefix("admin:")
            key = f"admin:{owner_id}" if current_user.role == RoleEnum.admin else "admin:self"
        else:
            other = next(
                (p for p in list_participants(db, conversation.id) if p.id != current_user.id),
                None,
            )
            if other is None:
                continue
            key = f"direct:{other.id}"

        summaries.append(
            {
                "target_key": key,
                "last_message_at": last_message_at.get(conversation.id),
                "has_unread": conversation.id in unread_ids,
            }
        )
    return summaries


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


def send_message(
    db: Session,
    *,
    conversation: Conversation,
    sender: User,
    body: str,
    recipient_ids: list[uuid.UUID],
) -> Message:
    """Insert a message, audit-log it, mark the sender caught up, and
    publish a realtime event to every other recipient. Commits on its own
    (like services/notifications.py::notify's callers are expected to for
    their own writes) since every current caller -- the messages routes,
    and system-triggered sends like a room/equipment deactivation notice --
    treats one message as a complete, independent unit of work.
    """
    ensure_participant(db, conversation, sender.id)

    message = Message(conversation_id=conversation.id, sender_id=sender.id, body=body)
    db.add(message)
    db.flush()

    record_audit_log(
        db,
        action="message_create",
        actor_id=sender.id,
        target_type="message",
        target_id=message.id,
    )
    touch_read(db, conversation, sender.id)

    for recipient_id in recipient_ids:
        if recipient_id == sender.id:
            continue
        publish(
            db,
            recipient_id=recipient_id,
            event={
                "event": "message",
                "conversation_id": str(conversation.id),
                "id": str(message.id),
                "body": message.body,
                "sender_id": str(sender.id),
            },
        )

    db.commit()
    db.refresh(message)
    return message
