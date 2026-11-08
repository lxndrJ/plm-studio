import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PartCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    part_type: str = Field(default="part", pattern="^(part|assembly)$")
    class_code: str
    attributes: dict = Field(default_factory=dict)
    reason: str | None = None


class PartRevisionCreate(BaseModel):
    change_reason: str = Field(min_length=1)


class TransitionRequest(BaseModel):
    to_status: str = Field(pattern="^(draft|review|released|obsolete)$")
    reason: str = Field(min_length=1)


class RevisionResponse(BaseModel):
    id: uuid.UUID
    revision: str
    status: str
    change_reason: str
    created_at: datetime

    class Config:
        from_attributes = True


class PartResponse(BaseModel):
    id: uuid.UUID
    part_number: str
    name: str
    description: str | None
    part_type: str
    class_id: uuid.UUID
    attributes: dict
    created_at: datetime
    revisions: list[RevisionResponse] = []

    class Config:
        from_attributes = True


class PartSummary(BaseModel):
    part_number: str
    name: str
    part_type: str

    class Config:
        from_attributes = True
