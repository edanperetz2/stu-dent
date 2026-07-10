import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class PatientCreate(BaseModel):
    full_name: str
    contact_phone: str | None = None


class PatientUpdate(BaseModel):
    full_name: str | None = None
    contact_phone: str | None = None


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_student_id: uuid.UUID
    full_name: str
    contact_phone: str | None
    email: str | None
    is_active: bool


class PatientCredentialsIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class PatientLoginIn(BaseModel):
    email: EmailStr
    password: str
