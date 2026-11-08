import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.core.deps import CurrentUser, DbSession
from app.guardrails import confirmations as conf_guard
from app.guardrails.permissions import require_editor
from app.models.bom import BomItem
from app.models.part import Part, PartRevision
from app.models.user import User
from app.schemas.bom import BomDiffResponse, BomItemCreate, BomItemResponse, WhereUsedEntry
from app.schemas.confirmation import ConfirmationProposed
from app.services import bom_service

router = APIRouter(prefix="/bom", tags=["bom"])


def _to_response(db: DbSession, item: BomItem) -> BomItemResponse:
    comp = db.get(PartRevision, item.component_rev_id)
    comp_part = db.get(Part, comp.part_id)
    return BomItemResponse(
        id=item.id,
        position=item.position,
        quantity=float(item.quantity),
        unit=item.unit,
        component_part_number=comp_part.part_number,
        component_revision=comp.revision,
        component_status=comp.status,
    )


@router.get("/parts/{part_number}", response_model=list[BomItemResponse])
def get_bom(part_number: str, db: DbSession, user: CurrentUser, rev: str | None = Query(default=None)):
    part = bom_service.get_part_by_number(db, part_number)
    if rev is not None:
        target = db_get_rev(db, part.id, rev)
    else:
        target = bom_service.latest_revision(db, part.id)
        if target is None:
            return []
    return [_to_response(db, item) for item in bom_service.get_bom(db, target.id)]


def db_get_rev(db, part_id, rev_label):
    from sqlalchemy import select

    from app.core.errors import NotFoundError

    r = db.execute(
        select(PartRevision).where(PartRevision.part_id == part_id, PartRevision.revision == rev_label)
    ).scalar_one_or_none()
    if r is None:
        raise NotFoundError(f"revision '{rev_label}' not found", code="revision_not_found")
    return r


@router.post("/items", status_code=201)
def add_item(
    body: BomItemCreate,
    db: DbSession,
    parent_rev_id: Annotated[uuid.UUID, Query(...)],
    user: Annotated[User, Depends(require_editor)],
    direct: Annotated[bool, Query()] = False,
):
    parent_rev = bom_service.get_revision_or_404(db, parent_rev_id)
    if not direct:
        conf = conf_guard.propose(
            db,
            user=user,
            action="add_bom_item",
            payload={
                "parent_rev_id": str(parent_rev_id),
                "component_part_number": body.component_part_number,
                "component_revision": body.component_revision,
                "quantity": body.quantity,
                "unit": body.unit,
                "position": body.position,
            },
            summary=(
                f"add BOM item to rev {parent_rev_id}: {body.quantity} {body.unit} "
                f"of {body.component_part_number} at position {body.position}"
            ),
        )
        return JSONResponse(status_code=202, content=ConfirmationProposed(confirmation_id=conf.id, summary=conf.summary).model_dump(mode="json"))
    component_rev = bom_service.resolve_component_revision(
        db, body.component_part_number, body.component_revision
    )
    item = bom_service.add_bom_item(
        db,
        parent_rev=parent_rev,
        component_rev=component_rev,
        quantity=body.quantity,
        unit=body.unit,
        position=body.position,
    )
    from app.services import audit as audit_service

    audit_service.log_change(
        db,
        entity_type="bom_item",
        entity_id=item.id,
        action="create",
        user_id=user.id,
        new_values={
            "parent_rev_id": str(parent_rev.id),
            "component_rev_id": str(component_rev.id),
            "quantity": float(item.quantity),
            "unit": item.unit,
            "position": item.position,
        },
    )
    db.commit()
    return _to_response(db, item)


def _check_draft(parent_rev) -> None:
    from app.core.errors import ConflictError

    if parent_rev.status != "draft":
        raise ConflictError(
            f"BOM of a '{parent_rev.status}' revision is immutable; create a new revision first",
            code="released_immutable",
        )


@router.put("/items/{item_id}", response_model=BomItemResponse)
def update_item(
    item_id: uuid.UUID,
    db: DbSession,
    user: Annotated[User, Depends(require_editor)],
    quantity: Annotated[float | None, Query(gt=0)] = None,
    unit: Annotated[str | None, Query(max_length=10)] = None,
    position: Annotated[int | None, Query(ge=1)] = None,
):
    from app.core.errors import NotFoundError
    from app.services import audit as audit_service

    item = db.get(BomItem, item_id)
    if item is None:
        raise NotFoundError(f"bom item {item_id} not found", code="bom_item_not_found")
    parent_rev = bom_service.get_revision_or_404(db, item.parent_rev_id)
    _check_draft(parent_rev)
    old = {"quantity": float(item.quantity), "unit": item.unit, "position": item.position}
    if quantity is not None:
        item.quantity = quantity
    if unit is not None:
        item.unit = unit
    if position is not None:
        item.position = position
    audit_service.log_change(
        db,
        entity_type="bom_item",
        entity_id=item.id,
        action="update",
        user_id=user.id,
        old_values=old,
        new_values={"quantity": float(item.quantity), "unit": item.unit, "position": item.position},
    )
    db.commit()
    return _to_response(db, item)


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: uuid.UUID, db: DbSession, user: Annotated[User, Depends(require_editor)]):
    from app.core.errors import NotFoundError
    from app.services import audit as audit_service

    item = db.get(BomItem, item_id)
    if item is None:
        raise NotFoundError(f"bom item {item_id} not found", code="bom_item_not_found")
    parent_rev = bom_service.get_revision_or_404(db, item.parent_rev_id)
    _check_draft(parent_rev)
    audit_service.log_change(
        db,
        entity_type="bom_item",
        entity_id=item.id,
        action="delete",
        user_id=user.id,
        old_values={
            "parent_rev_id": str(item.parent_rev_id),
            "component_rev_id": str(item.component_rev_id),
            "quantity": float(item.quantity),
            "unit": item.unit,
            "position": item.position,
        },
    )
    db.delete(item)
    db.commit()


@router.get("/parts/{part_number}/where-used", response_model=list[WhereUsedEntry])
def where_used(part_number: str, db: DbSession, user: CurrentUser):
    return bom_service.where_used(db, part_number)


@router.get("/parts/{part_number}/diff", response_model=BomDiffResponse)
def bom_diff(part_number: str, db: DbSession, user: CurrentUser, rev_a: str, rev_b: str):
    return bom_service.bom_diff(db, part_number, rev_a, rev_b)
