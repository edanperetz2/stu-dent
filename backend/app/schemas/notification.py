import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.notification import NotificationType


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    notification_type: NotificationType
    message: str
    related_appointment_id: uuid.UUID | None
    read_at: datetime | None
    created_at: datetime


class UnreadCountOut(BaseModel):
    count: int
