import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.appointment import AppointmentStatus


class AppointmentCreate(BaseModel):
    patient_id: uuid.UUID | None = None
    attending_id: uuid.UUID | None = None
    room_id: uuid.UUID | None = None
    equipment_id: uuid.UUID | None = None
    start_time: datetime
    end_time: datetime
    notes: str | None = None


class AppointmentUpdate(BaseModel):
    start_time: datetime | None = None
    end_time: datetime | None = None
    attending_id: uuid.UUID | None = None
    room_id: uuid.UUID | None = None
    equipment_id: uuid.UUID | None = None
    notes: str | None = None


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_id: uuid.UUID
    patient_id: uuid.UUID
    attending_id: uuid.UUID | None
    room_id: uuid.UUID | None
    equipment_id: uuid.UUID | None
    start_time: datetime
    end_time: datetime
    status: AppointmentStatus
    student_confirmed_at: datetime | None
    attending_approved_at: datetime | None
    notes: str | None
    # Resolved from the corresponding _id column for display -- see
    # Appointment's eager-loaded relationships/computed properties.
    student_name: str
    patient_name: str
    attending_name: str | None
    room_name: str | None
