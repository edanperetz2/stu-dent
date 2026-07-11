import uuid
from datetime import time

from pydantic import BaseModel, ConfigDict, Field


class AvailabilityWindowIn(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time


class AvailabilityWindowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    day_of_week: int
    start_time: time
    end_time: time
