import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ResourceBookingOut(BaseModel):
    """One busy window for a room or equipment item, combined into a single
    clinic-wide feed. Reveals which student booked it (so students/
    attendings can coordinate directly) but deliberately nothing about the
    patient or the appointment itself -- backs GET /resources/schedule,
    which any authenticated non-admin role can call. Admin doesn't need
    this: it already sees full detail via GET /appointments.
    """

    resource_kind: Literal["room", "equipment"]
    resource_id: uuid.UUID
    resource_name: str
    start_time: datetime
    end_time: datetime
    student_name: str
