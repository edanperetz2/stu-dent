import uuid

from pydantic import BaseModel, ConfigDict


class RoomCreate(BaseModel):
    name: str


class RoomUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class RoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_active: bool
