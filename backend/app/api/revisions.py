import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.core.deps import CurrentUser, DbSession
from app.guardrails import confirmations as conf_guard
from app.guardrails.permissions import require_editor
from app.models.user import User
from app.schemas.confirmation import ConfirmationProposed
from app.schemas.part import PartRevisionCreate, RevisionResponse, TransitionRequest
from app.services import part_service
from app.services.bom_service import get_part_by_number, get_revision_or_404

router = APIRouter(tags=["revisions"])


@router.post("/parts/{part_number}/revisions", status_code=201)
def create_revision(
    part_number: str,
    body: PartRevisionCreate,
    db: DbSession,
    user: Annotated[User, Depends(require_editor)],
    direct: Annotated[bool, Query()] = False,
):
    if not direct:
        conf = conf_guard.propose(
            db,
            user=user,
            action="create_revision",
            payload={"part_number": part_number, "change_reason": body.change_reason},
            summary=f"create new revision of '{part_number}' (reason: {body.change_reason})",
        )
        return JSONResponse(status_code=202, content=ConfirmationProposed(confirmation_id=conf.id, summary=conf.summary).model_dump(mode="json"))
    part = get_part_by_number(db, part_number)
    rev = part_service.create_revision(db, user=user, part=part, change_reason=body.change_reason)
    return RevisionResponse.model_validate(rev)


@router.post("/revisions/{revision_id}/transition")
def transition(
    revision_id: uuid.UUID,
    body: TransitionRequest,
    db: DbSession,
    user: Annotated[User, Depends(require_editor)],
    direct: Annotated[bool, Query()] = False,
):
    rev = get_revision_or_404(db, revision_id)
    if not direct:
        conf = conf_guard.propose(
            db,
            user=user,
            action="transition_revision",
            payload={
                "revision_id": str(revision_id),
                "to_status": body.to_status,
                "reason": body.reason,
            },
            summary=f"transition revision {rev.part.part_number} rev {rev.revision}: '{rev.status}' -> '{body.to_status}'",
        )
        return JSONResponse(status_code=202, content=ConfirmationProposed(confirmation_id=conf.id, summary=conf.summary).model_dump(mode="json"))
    rev = part_service.transition_revision(
        db, user=user, revision=rev, to_status=body.to_status, reason=body.reason
    )
    return RevisionResponse.model_validate(rev)


@router.get("/revisions/{revision_id}", response_model=RevisionResponse)
def get_revision(revision_id: uuid.UUID, db: DbSession, user: CurrentUser):
    return RevisionResponse.model_validate(get_revision_or_404(db, revision_id))
