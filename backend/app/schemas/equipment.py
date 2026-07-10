import uuid

from pydantic import BaseModel, ConfigDict


class EquipmentCreate(BaseModel):
    name: str
    equipment_type: str | None = None


class EquipmentUpdate(BaseModel):
    name: str | None = None
    equipment_type: str | None = None
    is_active: bool | None = None


class EquipmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    equipment_type: str | None
    is_active: bool
