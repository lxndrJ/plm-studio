import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreatePartPayload(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    part_type: str = Field(default="part", pattern="^(part|assembly)$")
    class_code: str
    attributes: dict = Field(default_factory=dict)
    reason: str | None = None


class CreateRevisionPayload(BaseModel):
    part_number: str
    change_reason: str = Field(min_length=1)


class TransitionPayload(BaseModel):
    revision_id: str
    to_status: str = Field(pattern="^(draft|review|released|obsolete)$")
    reason: str = Field(min_length=1)


class AddBomItemPayload(BaseModel):
    parent_rev_id: str
    component_part_number: str
    component_revision: str | None = None
    quantity: float = Field(gt=0)
    unit: str = Field(default="Stk", max_length=10)
    position: int = Field(ge=1)


ACTION_SCHEMAS = {
    "create_part": CreatePartPayload,
    "create_revision": CreateRevisionPayload,
    "transition_revision": TransitionPayload,
    "add_bom_item": AddBomItemPayload,
}


def payload_for_action(action: str):
    if action not in ACTION_SCHEMAS:
        from app.core.errors import ValidationError

        raise ValidationError(f"unknown confirmation action '{action}'", code="unknown_action")
    return ACTION_SCHEMAS[action]


ConfirmationPayload = CreatePartPayload | CreateRevisionPayload | TransitionPayload | AddBomItemPayload


class ConfirmationResponse(BaseModel):
    id: uuid.UUID
    action: str
    summary: str
    status: str
    payload: dict
    created_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True


class ConfirmationProposed(BaseModel):
    confirmation_id: uuid.UUID
    status: str = "proposed"
    summary: str
    message: str = "write proposed, not yet committed; approve via POST /api/v1/confirmations/{id}/approve"
