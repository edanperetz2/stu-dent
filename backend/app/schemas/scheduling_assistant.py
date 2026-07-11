import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class InterpretRequestIn(BaseModel):
    text: str


class InterpretedAppointmentOut(BaseModel):
    patient_id: uuid.UUID | None = None
    attending_id: uuid.UUID | None = None
    room_id: uuid.UUID | None = None
    equipment_id: uuid.UUID | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    notes: str | None = None
    warnings: list[str] = Field(default_factory=list)
