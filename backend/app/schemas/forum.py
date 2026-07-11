import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ForumPostCreate(BaseModel):
    title: str
    body: str


class ForumPostUpdate(BaseModel):
    title: str | None = None
    body: str | None = None


class ForumPostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    author_student_id: uuid.UUID
    title: str
    body: str
    score: int
    created_at: datetime
    updated_at: datetime


class ForumCommentCreate(BaseModel):
    body: str


class ForumCommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    post_id: uuid.UUID
    author_student_id: uuid.UUID
    body: str
    score: int
    created_at: datetime
    updated_at: datetime


class VoteIn(BaseModel):
    value: Literal[1, -1]
