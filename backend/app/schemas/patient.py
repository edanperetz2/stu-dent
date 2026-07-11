import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import PreferredTimeOfDay


class PatientCreate(BaseModel):
    """Student-initiated creation: the student supplies credentials
    directly, so the patient exists as a fully usable account from the
    start and the relationship is auto-confirmed (see PatientConfirm for
    the other path -- a patient self-registering via /auth/register)."""

    full_name: str
    email: EmailStr
    password: str = Field(min_length=8)
    contact_phone: str | None = None


class PatientUpdate(BaseModel):
    full_name: str | None = None
    contact_phone: str | None = None
    preferred_time_of_day: PreferredTimeOfDay | None = None


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_student_id: uuid.UUID | None
    owner_confirmed_at: datetime | None
    full_name: str
    contact_phone: str | None
    email: str
    is_active: bool
    preferred_time_of_day: PreferredTimeOfDay | None
