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


class PartClassResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    default_attributes: dict

    class Config:
        from_attributes = True


class HealthResponse(BaseModel):
    status: str
    database: str
