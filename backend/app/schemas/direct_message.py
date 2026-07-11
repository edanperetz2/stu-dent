import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DirectMessageCreate(BaseModel):
    body: str


class DirectMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    sender_user_id: uuid.UUID | None
    sender_patient_id: uuid.UUID | None
    body: str
    read_at: datetime | None
    created_at: datetime
