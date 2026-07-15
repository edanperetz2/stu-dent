import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.appointment import AppointmentStatus
from app.models.waitlist_entry import WaitlistStatus
from app.schemas.scheduling import ConflictReason


class WaitlistEntryOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    patient_id: uuid.UUID
    attending_id: uuid.UUID | None
    room_id: uuid.UUID | None
    equipment_id: uuid.UUID | None
    start_time: datetime
    end_time: datetime
    notes: str | None
    status: WaitlistStatus
    resolved_at: datetime | None
    resulting_appointment_id: uuid.UUID | None
    # The resulting appointment's status can keep progressing (e.g.
    # awaiting_confirmation -> confirmed) after auto-promotion, so this is
    # resolved fresh on every read rather than frozen at promotion time.
    resulting_appointment_status: AppointmentStatus | None
    # What was actually blocking this exact request -- see
    # WaitlistEntry.conflict_resource_types.
    conflicts: list[ConflictReason]
    student_name: str
    patient_name: str
    attending_name: str | None
    room_name: str | None
    equipment_name: str | None
