import uuid

from pydantic import BaseModel, ConfigDict


class StudentPublicOut(BaseModel):
    """Minimal, public (no auth) shape for the registration-time
    "choose your student" picker -- id + name only, no email, to avoid
    leaking PII to anonymous visitors."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
