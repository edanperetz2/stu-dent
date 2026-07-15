import uuid
from typing import Literal

from pydantic import BaseModel

ConflictResourceType = Literal["student", "patient", "attending", "room", "equipment"]


class ConflictReason(BaseModel):
    """One resource/person that was actually blocking a requested time --
    computed by services/scheduling.py::find_conflicts, never guessed from
    a raw database constraint violation.
    """

    resource_type: ConflictResourceType
    resource_id: uuid.UUID
    resource_name: str
