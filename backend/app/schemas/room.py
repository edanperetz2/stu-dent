import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class RoomUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None
    # Only meaningful alongside is_active=False -- schedules an automatic
    # reactivation instead of an indefinite one. Reactivating (is_active=True)
    # always clears it server-side, regardless of what's passed here.
    inactive_until: datetime | None = None


class RoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_active: bool
    inactive_until: datetime | None
