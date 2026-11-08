from typing import Any, Literal

from pydantic import BaseModel, Field


class PartCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = None
    part_type: Literal["part", "assembly"] = "part"
    class_code: str = Field(description="z.B. MECH, ELEC, CONS, PACK")
    attributes: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = Field(
        default=None, description="Grund fuers Anlegen (Pflicht im Audit)"
    )


class PartRead(BaseModel):
    part_number: str
    name: str
    revision: str
    status: str
    class_code: str
