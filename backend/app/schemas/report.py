import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.report import ReportContentSource, ReportPeriodType


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    period_type: ReportPeriodType
    period_start: datetime
    period_end: datetime
    question: str | None
    title: str
    content: str
    content_source: ReportContentSource
    created_at: datetime


class AskQuestionIn(BaseModel):
    question: str = Field(min_length=1, max_length=1_000)


class GenerateReportIn(BaseModel):
    period_type: Literal["weekly", "monthly"]
    output_style: Literal["ai_narrated", "data_summary"]
