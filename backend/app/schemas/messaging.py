import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import RoleEnum


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5_000)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    sender_name: str
    body: str
    created_at: datetime
    # Exposed so the frontend can page further back with `before_sequence`
    # -- created_at alone can tie within one transaction (see the model's
    # own comment), so it isn't a safe pagination cursor on its own.
    sequence: int


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    role: RoleEnum


class ReadReceiptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # None after an explicit "mark unread" -- see touch_unread.
    last_read_at: datetime | None


class GroupCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    participant_ids: list[uuid.UUID]


class GroupSummaryOut(BaseModel):
    id: uuid.UUID
    title: str
    participant_ids: list[uuid.UUID]
    participant_names: list[str]


class UnreadCountOut(BaseModel):
    count: int


class ThreadSummaryOut(BaseModel):
    # target_key matches the frontend's targetKey() exactly (direct:<id>,
    # admin:self / admin:<owner_id>, group:<id>) so it can be used directly
    # as a lookup key without any extra parsing.
    target_key: str
    last_message_at: datetime | None
    has_unread: bool
