import uuid

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.user import RoleEnum


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str
    role: RoleEnum
    # Required (and only meaningful) when role == patient: the student the
    # patient is registering under. Validated further in the route (must
    # reference a real, active student).
    owner_student_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def check_owner_student_id(self) -> "RegisterIn":
        if self.role == RoleEnum.patient and self.owner_student_id is None:
            raise ValueError("owner_student_id is required when registering as a patient")
        if self.role != RoleEnum.patient and self.owner_student_id is not None:
            raise ValueError("owner_student_id is only valid when registering as a patient")
        return self


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    # Optional role hint: if provided, the account's actual role must match,
    # or the login is rejected -- lets the frontend offer a role selector at
    # login and have the backend actually enforce it, not just trust the UI.
    role: RoleEnum | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
