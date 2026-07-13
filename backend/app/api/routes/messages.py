import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.conversation import (
    Conversation,
    ConversationKind,
    ConversationParticipant,
    Message,
)
from app.models.user import RoleEnum, User
from app.realtime.events import publish
from app.schemas.messaging import (
    ContactOut,
    GroupCreate,
    GroupSummaryOut,
    MessageCreate,
    MessageOut,
    ReadReceiptOut,
)
from app.services.audit import record_audit_log
from app.services.messaging import (
    active_admin_ids,
    admin_key,
    can_message_directly,
    create_group_conversation,
    direct_key,
    ensure_participant,
    get_or_create_conversation,
    is_participant,
    list_contacts,
    list_conversation_messages,
    list_participants,
    touch_read,
)
from app.services.patients import require_confirmed_patient
from app.services.users import active_user_filters

router = APIRouter(prefix="/messages", tags=["messages"])


def _get_active_user_or_404(db: Session, user_id: uuid.UUID) -> User:
    user = db.scalar(
        select(User).where(User.id == user_id, User.is_active.is_(True), User.deleted_at.is_(None))
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _send_message(
    db: Session,
    *,
    conversation: Conversation,
    sender: User,
    body: str,
    recipient_ids: list[uuid.UUID],
) -> Message:
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


@router.get("/contacts", response_model=list[ContactOut])
def get_contacts(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[User]:
    return list_contacts(db, current_user)


# ---- Direct (peer-to-peer) messages ----------------------------------------


def _authorized_peer(db: Session, other_user_id: uuid.UUID, current_user: User) -> User:
    other = _get_active_user_or_404(db, other_user_id)
    if not can_message_directly(current_user, other):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    return other


@router.get("/direct/{other_user_id}", response_model=list[MessageOut])
def list_direct_messages(
    other_user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Message]:
    other = _authorized_peer(db, other_user_id, current_user)
    existing = db.scalar(
        select(Conversation).where(Conversation.direct_key == direct_key(current_user.id, other.id))
    )
    if existing is None:
        return []
    return list_conversation_messages(db, existing.id)


@router.post(
    "/direct/{other_user_id}", response_model=MessageOut, status_code=status.HTTP_201_CREATED
)
def send_direct_message(
    other_user_id: uuid.UUID,
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Message:
    other = _authorized_peer(db, other_user_id, current_user)
    if current_user.role == RoleEnum.patient:
        require_confirmed_patient(current_user)

    conversation = get_or_create_conversation(
        db,
        kind=ConversationKind.direct,
        key=direct_key(current_user.id, other.id),
        participant_ids=[current_user.id, other.id],
    )
    return _send_message(
        db,
        conversation=conversation,
        sender=current_user,
        body=payload.body,
        recipient_ids=[other.id],
    )


@router.post("/direct/{other_user_id}/read", response_model=ReadReceiptOut)
def mark_direct_read(
    other_user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReadReceiptOut:
    other = _authorized_peer(db, other_user_id, current_user)
    existing = db.scalar(
        select(Conversation).where(Conversation.direct_key == direct_key(current_user.id, other.id))
    )
    if existing is None:
        return ReadReceiptOut(last_read_at=datetime.now(UTC))
    participant = touch_read(db, existing, current_user.id)
    db.commit()
    return ReadReceiptOut.model_validate(participant)


# ---- Admin shared inbox -----------------------------------------------------


@router.get("/admin", response_model=list[MessageOut])
def list_own_admin_messages(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Message]:
    if current_user.role == RoleEnum.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins use /messages/admin-inbox/{user_id}",
        )
    existing = db.scalar(
        select(Conversation).where(Conversation.direct_key == admin_key(current_user.id))
    )
    if existing is None:
        return []
    return list_conversation_messages(db, existing.id)


@router.post("/admin", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def send_own_admin_message(
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Message:
    if current_user.role == RoleEnum.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins use /messages/admin-inbox/{user_id}",
        )
    if current_user.role == RoleEnum.patient:
        require_confirmed_patient(current_user)

    conversation = get_or_create_conversation(
        db,
        kind=ConversationKind.admin,
        key=admin_key(current_user.id),
        participant_ids=[current_user.id],
    )
    recipients = active_admin_ids(db)
    return _send_message(
        db,
        conversation=conversation,
        sender=current_user,
        body=payload.body,
        recipient_ids=recipients,
    )


@router.post("/admin/read", response_model=ReadReceiptOut)
def mark_own_admin_read(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ReadReceiptOut:
    if current_user.role == RoleEnum.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not applicable to admins"
        )
    existing = db.scalar(
        select(Conversation).where(Conversation.direct_key == admin_key(current_user.id))
    )
    if existing is None:
        return ReadReceiptOut(last_read_at=datetime.now(UTC))
    participant = touch_read(db, existing, current_user.id)
    db.commit()
    return ReadReceiptOut.model_validate(participant)


@router.get("/admin-inbox/{owner_id}", response_model=list[MessageOut])
def list_admin_inbox_messages(
    owner_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Message]:
    if current_user.role != RoleEnum.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")
    _get_active_user_or_404(db, owner_id)
    existing = db.scalar(select(Conversation).where(Conversation.direct_key == admin_key(owner_id)))
    if existing is None:
        return []
    return list_conversation_messages(db, existing.id)


@router.post(
    "/admin-inbox/{owner_id}", response_model=MessageOut, status_code=status.HTTP_201_CREATED
)
def send_admin_inbox_message(
    owner_id: uuid.UUID,
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Message:
    if current_user.role != RoleEnum.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")
    owner = _get_active_user_or_404(db, owner_id)

    conversation = get_or_create_conversation(
        db, kind=ConversationKind.admin, key=admin_key(owner.id), participant_ids=[owner.id]
    )
    recipients = [owner.id, *(a for a in active_admin_ids(db) if a != current_user.id)]
    return _send_message(
        db,
        conversation=conversation,
        sender=current_user,
        body=payload.body,
        recipient_ids=recipients,
    )


@router.post("/admin-inbox/{owner_id}/read", response_model=ReadReceiptOut)
def mark_admin_inbox_read(
    owner_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReadReceiptOut:
    if current_user.role != RoleEnum.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")
    _get_active_user_or_404(db, owner_id)
    existing = db.scalar(select(Conversation).where(Conversation.direct_key == admin_key(owner_id)))
    if existing is None:
        return ReadReceiptOut(last_read_at=datetime.now(UTC))
    participant = touch_read(db, existing, current_user.id)
    db.commit()
    return ReadReceiptOut.model_validate(participant)


# ---- Group chats (students/attendings only) --------------------------------


def _require_group_creator_role(current_user: User) -> None:
    if current_user.role not in (RoleEnum.student, RoleEnum.attending):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students and attendings can start group chats",
        )


def _group_summary(db: Session, conversation: Conversation) -> GroupSummaryOut:
    participants = list_participants(db, conversation.id)
    return GroupSummaryOut(
        id=conversation.id,
        title=conversation.title or "Group chat",
        participant_ids=[p.id for p in participants],
        participant_names=[p.full_name for p in participants],
    )


@router.get("/groups", response_model=list[GroupSummaryOut])
def list_groups(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[GroupSummaryOut]:
    stmt = (
        select(Conversation)
        .join(ConversationParticipant, ConversationParticipant.conversation_id == Conversation.id)
        .where(
            ConversationParticipant.user_id == current_user.id,
            Conversation.kind == ConversationKind.group,
        )
    )
    return [_group_summary(db, conversation) for conversation in db.scalars(stmt)]


@router.post("/groups", response_model=GroupSummaryOut, status_code=status.HTTP_201_CREATED)
def create_group(
    payload: GroupCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroupSummaryOut:
    _require_group_creator_role(current_user)

    if not payload.participant_ids:
        raise HTTPException(status_code=422, detail="Select at least one other participant")

    unique_ids = set(payload.participant_ids)
    members = list(
        db.scalars(
            select(User).where(
                User.id.in_(unique_ids),
                *active_user_filters(RoleEnum.student, RoleEnum.attending),
            )
        )
    )
    if len(members) != len(unique_ids):
        raise HTTPException(
            status_code=422, detail="All participants must be active students or attendings"
        )

    all_ids = {current_user.id, *(m.id for m in members)}
    conversation = create_group_conversation(db, title=payload.title, participant_ids=list(all_ids))
    db.commit()
    return _group_summary(db, conversation)


def _get_group_or_404(db: Session, conversation_id: uuid.UUID, current_user: User) -> Conversation:
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.kind == ConversationKind.group
        )
    )
    if conversation is None or not is_participant(db, conversation_id, current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return conversation


@router.get("/groups/{conversation_id}", response_model=list[MessageOut])
def list_group_messages(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Message]:
    _get_group_or_404(db, conversation_id, current_user)
    return list_conversation_messages(db, conversation_id)


@router.post(
    "/groups/{conversation_id}", response_model=MessageOut, status_code=status.HTTP_201_CREATED
)
def send_group_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Message:
    conversation = _get_group_or_404(db, conversation_id, current_user)
    recipients = [p.id for p in list_participants(db, conversation_id)]
    return _send_message(
        db,
        conversation=conversation,
        sender=current_user,
        body=payload.body,
        recipient_ids=recipients,
    )


@router.post("/groups/{conversation_id}/read", response_model=ReadReceiptOut)
def mark_group_read(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReadReceiptOut:
    conversation = _get_group_or_404(db, conversation_id, current_user)
    participant = touch_read(db, conversation, current_user.id)
    db.commit()
    return ReadReceiptOut.model_validate(participant)
