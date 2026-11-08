import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    doc_type: str = Field(pattern="^(vector|raster|cad|report|other)$")
    reason: str | None = None


class DocRevisionCreate(BaseModel):
    change_reason: str = Field(min_length=1)


class DocLinkCreate(BaseModel):
    part_number: str
    link_type: str = Field(pattern="^(referenced-by|owned-by)$")


class DocTransitionRequest(BaseModel):
    to_status: str = Field(pattern="^(draft|review|released|obsolete)$")
    reason: str = Field(min_length=1)


class DocFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    mime_type: str
    is_original: bool
    preview_file_id: uuid.UUID | None
    has_derivative: bool = False


class DocRevisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    revision: str
    status: str
    change_reason: str
    created_at: datetime
    files: list[DocFileResponse] = []


class DocLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    part_id: uuid.UUID
    link_type: str


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    doc_number: str
    doc_type: str
    title: str
    revisions: list[DocRevisionResponse] = []
    links: list[DocLinkResponse] = []


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    doc_number: str
    title: str
    doc_type: str
