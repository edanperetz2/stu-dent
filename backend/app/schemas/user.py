import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

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
    # Resolved from owner_student_id; only populated by GET/PATCH /users/me,
    # left None everywhere else UserOut is used (e.g. admin user lists) to
    # avoid an N+1 lookup per row.
    owner_student_name: str | None = None
    owner_confirmed_at: datetime | None = None
    contact_phone: str | None = None
    preferred_time_of_day: PreferredTimeOfDay | None = None


class UserSelfUpdate(BaseModel):
    """Self-service profile update via PATCH /users/me.

    Deliberately narrow: only the two fields meaningful for a patient's own
    preferences. Full name/email/role changes go through admin endpoints,
    not self-service.
    """

    # Input-only constraint (UserOut above is a response schema -- no
    # max_length there, so a pre-existing row longer than this can't fail
    # to serialize).
    contact_phone: str | None = Field(default=None, max_length=32)
    preferred_time_of_day: PreferredTimeOfDay | None = None
