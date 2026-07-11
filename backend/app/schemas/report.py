import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.report import ReportPeriodType


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    period_type: ReportPeriodType
    period_start: datetime
    period_end: datetime
    question: str | None
    title: str
    content: str
    created_at: datetime


class AskQuestionIn(BaseModel):
    question: str
