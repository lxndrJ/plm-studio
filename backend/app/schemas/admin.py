import uuid

from pydantic import BaseModel, Field


class NumberRangeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20, pattern="^[A-Z0-9_]+$")
    prefix: str = Field(min_length=1, max_length=10)
    width: int = Field(default=6, ge=1, le=12)


class NumberRangeResponse(BaseModel):
    id: uuid.UUID
    code: str
    prefix: str
    width: int
    next_number: int

    class Config:
        from_attributes = True


class PartClassCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20, pattern="^[A-Z0-9_]+$")
    name: str
    default_attributes: dict = Field(default_factory=dict)
    parent_code: str | None = None


class ClassAttributeResponse(BaseModel):
    key: str
    label: str
    attr_type: str
    unit_code: str | None = None
    required: bool
    allowed_values: list | None = None

    class Config:
        from_attributes = True


class PartClassResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    default_attributes: dict
    parent_id: uuid.UUID | None = None
    attributes: list[ClassAttributeResponse] = []

    class Config:
        from_attributes = True


class HealthResponse(BaseModel):
    status: str
    database: str
