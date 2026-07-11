import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.waitlist_entry import WaitlistStatus


class WaitlistEntryCreate(BaseModel):
    patient_id: uuid.UUID | None = None
    attending_id: uuid.UUID | None = None
    room_id: uuid.UUID | None = None
    equipment_id: uuid.UUID | None = None
    start_time: datetime
    end_time: datetime


class WaitlistEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_id: uuid.UUID
    patient_id: uuid.UUID
    attending_id: uuid.UUID | None
    room_id: uuid.UUID | None
    equipment_id: uuid.UUID | None
    start_time: datetime
    end_time: datetime
    status: WaitlistStatus
    notified_at: datetime | None
