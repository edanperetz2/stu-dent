import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.user import RoleEnum


class AdminUserUpdate(BaseModel):
    is_active: bool | None = None
    role: RoleEnum | None = None


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: uuid.UUID | None
    attempted_identifier: str | None
    action: str
    target_type: str | None
    target_id: uuid.UUID | None
    ip_address: str | None
    extra_data: dict | None
    created_at: datetime
