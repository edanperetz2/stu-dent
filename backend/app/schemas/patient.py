import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.patient import PreferredTimeOfDay


class PatientCreate(BaseModel):
    full_name: str
    contact_phone: str | None = None


class PatientUpdate(BaseModel):
    full_name: str | None = None
    contact_phone: str | None = None
    preferred_time_of_day: PreferredTimeOfDay | None = None


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_student_id: uuid.UUID
    full_name: str
    contact_phone: str | None
    email: str | None
    is_active: bool
    preferred_time_of_day: PreferredTimeOfDay | None


class PatientCredentialsIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class PatientLoginIn(BaseModel):
    email: EmailStr
    password: str
