import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.core.errors import NotFoundError
from app.guardrails import confirmations as conf_guard
from app.guardrails.permissions import require_editor
from app.models.numbering import PartClass
from app.models.user import User
from app.schemas.confirmation import ConfirmationProposed
from app.schemas.part import PartCreate, PartResponse, PartSummary
from app.services import part_service

router = APIRouter(prefix="/parts", tags=["parts"])


@router.get("", response_model=list[PartSummary])
def list_parts(
    db: DbSession,
    user: CurrentUser,
    query: Annotated[str | None, Query()] = None,
    class_code: Annotated[str | None, Query()] = None,
):
    return part_service.search_parts(db, query=query, class_code=class_code)


@router.post("", status_code=201)
def create_part(
    body: PartCreate,
    db: DbSession,
    user: Annotated[User, Depends(require_editor)],
    direct: Annotated[bool, Query(description="true = commit immediately (UI path); false = propose confirmation token (agent path)")] = False,
):
    payload = body.model_dump()
    summary = f"create part '{body.name}' (type={body.part_type}, class={body.class_code})"
    if not direct:
        conf = conf_guard.propose(db, user=user, action="create_part", payload=payload, summary=summary)
        return JSONResponse(status_code=202, content=ConfirmationProposed(confirmation_id=conf.id, summary=summary).model_dump(mode="json"))
    class_id = db.execute(select(PartClass.id).where(PartClass.code == body.class_code)).scalar_one_or_none()
    if class_id is None:
        raise NotFoundError(f"part class '{body.class_code}' not found", code="class_not_found")
    part = part_service.create_part(
        db,
        user=user,
        name=body.name,
        description=body.description,
        part_type=body.part_type,
        class_id=class_id,
        attributes=body.attributes,
        reason=body.reason,
    )
    return PartResponse.model_validate(part)


@router.get("/{part_number}", response_model=PartResponse)
def get_part(part_number: str, db: DbSession, user: CurrentUser):
    part = part_service.get_part_with_revisions(db, part_number)
    return PartResponse.model_validate(part)


@router.put("/{part_number}/revisions/{revision_id}", status_code=409)
def update_revision_blocked(part_number: str, revision_id: uuid.UUID, user: Annotated[User, Depends(require_editor)]):
    from app.core.errors import ConflictError

    raise ConflictError(
        "direct updates of revisions are not allowed; use POST /revisions/{id}/transition or create a new revision",
        code="direct_update_not_allowed",
    )


@router.get("/{part_number}/revisions", response_model=list)
def list_revisions(part_number: str, db: DbSession, user: CurrentUser):
    from app.models.part import PartRevision

    part = part_service.get_part_with_revisions(db, part_number)
    revs = db.execute(
        select(PartRevision).where(PartRevision.part_id == part.id).order_by(PartRevision.revision)
    ).scalars()
    from app.schemas.part import RevisionResponse

    return [RevisionResponse.model_validate(r) for r in revs]
