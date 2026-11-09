import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class EcrCreate(BaseModel):
    description: str = Field(min_length=1, max_length=2000)
    reason: str | None = None


class EcrTransitionRequest(BaseModel):
    to_status: str = Field(pattern="^(open|in_review|approved|rejected)$")
    reason: str = Field(min_length=1)


class EcoCreate(BaseModel):
    reason: str | None = None


class EcoTransitionRequest(BaseModel):
    to_status: str = Field(pattern="^(draft|approved|executed)$")
    reason: str = Field(min_length=1)


class AffectedRevisionAdd(BaseModel):
    part_number: str
    revision: str | None = None
    reason: str | None = None


class EcrSummary(BaseModel):
    id: uuid.UUID
    number: str
    description: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class EcoSummary(BaseModel):
    id: uuid.UUID
    number: str
    status: str
    ecr_number: str
    created_at: datetime


class EcrDetail(EcrSummary):
    ecos: list[EcoSummary] = []


class AffectedRevisionResponse(BaseModel):
    revision_id: uuid.UUID
    part_number: str
    revision: str
    status: str


class EcoResponse(EcoSummary):
    affected: list[AffectedRevisionResponse] = []
