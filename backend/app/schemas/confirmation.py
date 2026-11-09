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


class CreateDocumentPayload(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    doc_type: str = Field(pattern="^(vector|raster|cad|report|other)$")
    reason: str | None = None


class CreateDocRevisionPayload(BaseModel):
    doc_number: str
    change_reason: str = Field(min_length=1)


class LinkDocumentPayload(BaseModel):
    doc_number: str
    part_number: str
    link_type: str = Field(pattern="^(referenced-by|owned-by)$")


class TransitionDocRevisionPayload(BaseModel):
    revision_id: str
    to_status: str = Field(pattern="^(draft|review|released|obsolete)$")
    reason: str = Field(min_length=1)


class CreateEcrPayload(BaseModel):
    description: str = Field(min_length=1, max_length=2000)
    reason: str | None = None


class TransitionEcrPayload(BaseModel):
    ecr_number: str
    to_status: str = Field(pattern="^(open|in_review|approved|rejected)$")
    reason: str = Field(min_length=1)


class CreateEcoPayload(BaseModel):
    ecr_number: str
    reason: str | None = None


class TransitionEcoPayload(BaseModel):
    eco_number: str
    to_status: str = Field(pattern="^(draft|approved|executed)$")
    reason: str = Field(min_length=1)


class EcoAddAffectedPayload(BaseModel):
    eco_number: str
    part_number: str
    revision: str | None = None
    reason: str | None = None


class CreateReportPayload(BaseModel):
    template: str = "part_sheet_v1"
    part_number: str | None = None
    ecr_number: str | None = None
    reason: str | None = None


class UpdateRevisionAttributesPayload(BaseModel):
    part_number: str
    revision_id: uuid.UUID
    attributes: dict = Field(default_factory=dict)
    reason: str | None = None


ACTION_SCHEMAS = {
    "create_part": CreatePartPayload,
    "create_revision": CreateRevisionPayload,
    "transition_revision": TransitionPayload,
    "add_bom_item": AddBomItemPayload,
    "create_document": CreateDocumentPayload,
    "create_doc_revision": CreateDocRevisionPayload,
    "link_document": LinkDocumentPayload,
    "transition_doc_revision": TransitionDocRevisionPayload,
    "create_ecr": CreateEcrPayload,
    "transition_ecr": TransitionEcrPayload,
    "create_eco": CreateEcoPayload,
    "transition_eco": TransitionEcoPayload,
    "eco_add_affected": EcoAddAffectedPayload,
    "create_report": CreateReportPayload,
    "update_revision_attributes": UpdateRevisionAttributesPayload,
}


def payload_for_action(action: str):
    if action not in ACTION_SCHEMAS:
        from app.core.errors import ValidationError

        raise ValidationError(f"unknown confirmation action '{action}'", code="unknown_action")
    return ACTION_SCHEMAS[action]


ConfirmationPayload = (
    CreatePartPayload
    | CreateRevisionPayload
    | TransitionPayload
    | AddBomItemPayload
    | CreateDocumentPayload
    | CreateDocRevisionPayload
    | LinkDocumentPayload
    | TransitionDocRevisionPayload
    | CreateEcrPayload
    | TransitionEcrPayload
    | CreateEcoPayload
    | TransitionEcoPayload
    | EcoAddAffectedPayload
    | CreateReportPayload
    | UpdateRevisionAttributesPayload
)


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
    message: str = (
        "write proposed, not yet committed; approve via POST /api/v1/confirmations/{id}/approve"
    )
