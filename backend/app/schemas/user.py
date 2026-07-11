import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.user import PreferredTimeOfDay, RoleEnum


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: RoleEnum
    is_active: bool
    # Meaningful only when role == patient; null for student/attending/admin.
    owner_student_id: uuid.UUID | None = None
    owner_confirmed_at: datetime | None = None
    contact_phone: str | None = None
    preferred_time_of_day: PreferredTimeOfDay | None = None
