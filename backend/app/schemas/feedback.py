import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.feedback import FeedbackAuthorRole


class FeedbackCreate(BaseModel):
    went_well: str = Field(min_length=1)
    could_improve: str = Field(min_length=1)
    additional_comments: str | None = None


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    appointment_id: uuid.UUID
    student_id: uuid.UUID
    author_id: uuid.UUID
    author_role: FeedbackAuthorRole
    went_well: str
    could_improve: str
    additional_comments: str | None
    created_at: datetime
    # Resolved for display, same convention as AppointmentOut/WaitlistEntryOut.
    # patient_id lets a student group their received feedback by patient
    # without relying on the (non-unique) display name.
    student_name: str
    author_name: str
    patient_id: uuid.UUID
    patient_name: str
    appointment_start_time: datetime


class PendingFeedbackOut(BaseModel):
    appointment_id: uuid.UUID
    appointment_start_time: datetime
    student_id: uuid.UUID
    student_name: str
    patient_id: uuid.UUID
    patient_name: str
