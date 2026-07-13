import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EquipmentCreate(BaseModel):
    name: str
    equipment_type: str | None = None


class EquipmentUpdate(BaseModel):
    name: str | None = None
    equipment_type: str | None = None
    is_active: bool | None = None
    # Only meaningful alongside is_active=False -- schedules an automatic
    # reactivation instead of an indefinite one. Reactivating (is_active=True)
    # always clears it server-side, regardless of what's passed here.
    inactive_until: datetime | None = None


class EquipmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    equipment_type: str | None
    is_active: bool
    inactive_until: datetime | None
