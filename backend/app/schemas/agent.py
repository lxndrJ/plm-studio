import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class MessageCreate(BaseModel):
    role: Literal["user", "assistant", "tool", "system"]
    content: dict = Field(default_factory=dict)


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: dict
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    id: uuid.UUID
    title: str
    created_by: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationDetail(ConversationResponse):
    messages: list[MessageResponse] = []
