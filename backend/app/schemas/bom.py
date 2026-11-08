import uuid

from pydantic import BaseModel, Field


class BomItemCreate(BaseModel):
    component_part_number: str
    component_revision: str | None = None
    quantity: float = Field(gt=0)
    unit: str = Field(default="Stk", max_length=10)
    position: int = Field(ge=1)


class BomItemResponse(BaseModel):
    id: uuid.UUID
    position: int
    quantity: float
    unit: str
    component_part_number: str
    component_revision: str
    component_status: str

    class Config:
        from_attributes = True


class WhereUsedEntry(BaseModel):
    parent_part_number: str
    parent_revision: str
    parent_status: str
    depth: int


class BomDiffResponse(BaseModel):
    part_number: str
    rev_a: str
    rev_b: str
    added: list[dict]
    removed: list[dict]
    changed: list[dict]
