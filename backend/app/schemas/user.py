import uuid

from pydantic import BaseModel, ConfigDict

from app.models.user import RoleEnum


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: RoleEnum
    is_active: bool
