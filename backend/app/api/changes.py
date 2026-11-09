import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, DbSession
from app.guardrails import confirmations as conf_guard
from app.guardrails.permissions import require_editor
from app.models.change import Eco, Ecr
from app.models.user import User
from app.schemas.change import (
    AffectedRevisionAdd,
    AffectedRevisionResponse,
    EcoCreate,
    EcoResponse,
    EcoSummary,
    EcoTransitionRequest,
    EcoTransitionResponse,
    EcrCreate,
    EcrDetail,
    EcrSummary,
    EcrTransitionRequest,
)
from app.schemas.confirmation import ConfirmationProposed
from app.services import change_service

router = APIRouter(tags=["changes"])


def _eco_summary(db: Session, eco: Eco) -> EcoSummary:
    return EcoSummary(
        id=eco.id,
        number=eco.number,
        status=eco.status,
        ecr_number=eco.ecr.number,
        created_at=eco.created_at,
    )


def _eco_response(db: Session, eco: Eco) -> EcoResponse:
    return EcoResponse(
        **_eco_summary(db, eco).model_dump(),
        affected=[
            AffectedRevisionResponse(
                revision_id=rev.id,
                part_number=rev.part.part_number,
                revision=rev.revision,
                status=rev.status,
            )
            for rev in eco.affected_revisions
        ],
    )


def _ecr_detail(db: Session, ecr: Ecr) -> EcrDetail:
    return EcrDetail(
        id=ecr.id,
        number=ecr.number,
        description=ecr.description,
        status=ecr.status,
        created_at=ecr.created_at,
        ecos=[_eco_summary(db, eco) for eco in ecr.ecos],
    )


@router.get("/ecrs", response_model=list[EcrSummary])
def list_ecrs(db: DbSession, user: CurrentUser, status: Annotated[str | None, Query()] = None):
    return [EcrSummary.model_validate(e) for e in change_service.list_ecrs(db, status=status)]


@router.post("/ecrs", status_code=201, response_model=EcrSummary)
def create_ecr(
    body: EcrCreate,
    db: DbSession,
    user: Annotated[User, Depends(require_editor)],
    direct: Annotated[bool, Query()] = False,
):
    if not direct:
        conf = conf_guard.propose(
            db,
            user=user,
            action="create_ecr",
            payload={"description": body.description, "reason": body.reason},
            summary=f"create ECR: {body.description[:80]}",
        )
        return JSONResponse(
            status_code=202,
            content=ConfirmationProposed(confirmation_id=conf.id, summary=conf.summary).model_dump(
                mode="json"
            ),
        )
    ecr = change_service.create_ecr(db, user=user, description=body.description, reason=body.reason)
    return EcrSummary.model_validate(ecr)


@router.get("/ecrs/{number}", response_model=EcrDetail)
def get_ecr(number: str, db: DbSession, user: CurrentUser):
    return _ecr_detail(db, change_service.get_ecr_by_number(db, number))


@router.post("/ecrs/{number}/transition", response_model=EcrSummary)
def transition_ecr(
    number: str,
    body: EcrTransitionRequest,
    db: DbSession,
    user: Annotated[User, Depends(require_editor)],
    direct: Annotated[bool, Query()] = False,
):
    ecr = change_service.get_ecr_by_number(db, number)
    if not direct:
        conf = conf_guard.propose(
            db,
            user=user,
            action="transition_ecr",
            payload={"ecr_number": number, "to_status": body.to_status, "reason": body.reason},
            summary=f"transition ECR {number}: '{ecr.status}' -> '{body.to_status}'",
        )
        return JSONResponse(
            status_code=202,
            content=ConfirmationProposed(confirmation_id=conf.id, summary=conf.summary).model_dump(
                mode="json"
            ),
        )
    ecr = change_service.transition_ecr(
        db, user=user, ecr=ecr, to_status=body.to_status, reason=body.reason
    )
    return EcrSummary.model_validate(ecr)


@router.get("/ecos", response_model=list[EcoSummary])
def list_ecos(db: DbSession, user: CurrentUser, status: Annotated[str | None, Query()] = None):
    return [_eco_summary(db, e) for e in change_service.list_ecos(db, status=status)]


@router.post("/ecrs/{number}/ecos", status_code=201, response_model=EcoResponse)
def create_eco(
    number: str,
    body: EcoCreate,
    db: DbSession,
    user: Annotated[User, Depends(require_editor)],
    direct: Annotated[bool, Query()] = False,
):
    ecr = change_service.get_ecr_by_number(db, number)
    if not direct:
        conf = conf_guard.propose(
            db,
            user=user,
            action="create_eco",
            payload={"ecr_number": number, "reason": body.reason},
            summary=f"create ECO for ECR {number} (ECR status: {ecr.status})",
        )
        return JSONResponse(
            status_code=202,
            content=ConfirmationProposed(confirmation_id=conf.id, summary=conf.summary).model_dump(
                mode="json"
            ),
        )
    eco = change_service.create_eco(db, user=user, ecr=ecr, reason=body.reason)
    return _eco_response(db, eco)


@router.get("/ecos/{number}", response_model=EcoResponse)
def get_eco(number: str, db: DbSession, user: CurrentUser):
    return _eco_response(db, change_service.get_eco_by_number(db, number))


@router.post("/ecos/{number}/transition", response_model=EcoTransitionResponse)
def transition_eco(
    number: str,
    body: EcoTransitionRequest,
    db: DbSession,
    user: Annotated[User, Depends(require_editor)],
    direct: Annotated[bool, Query()] = False,
):
    eco = change_service.get_eco_by_number(db, number)
    if not direct:
        conf = conf_guard.propose(
            db,
            user=user,
            action="transition_eco",
            payload={"eco_number": number, "to_status": body.to_status, "reason": body.reason},
            summary=f"transition ECO {number}: '{eco.status}' -> '{body.to_status}'",
        )
        return JSONResponse(
            status_code=202,
            content=ConfirmationProposed(confirmation_id=conf.id, summary=conf.summary).model_dump(
                mode="json"
            ),
        )
    eco, created = change_service.transition_eco(
        db, user=user, eco=eco, to_status=body.to_status, reason=body.reason
    )
    return EcoTransitionResponse(**_eco_response(db, eco).model_dump(), created_revisions=created)


@router.post(
    "/ecos/{number}/affected-revisions", status_code=201, response_model=AffectedRevisionResponse
)
def add_affected_revision(
    number: str,
    body: AffectedRevisionAdd,
    db: DbSession,
    user: Annotated[User, Depends(require_editor)],
    direct: Annotated[bool, Query()] = False,
):
    eco = change_service.get_eco_by_number(db, number)
    if not direct:
        conf = conf_guard.propose(
            db,
            user=user,
            action="eco_add_affected",
            payload={
                "eco_number": number,
                "part_number": body.part_number,
                "revision": body.revision,
                "reason": body.reason,
            },
            summary=f"add affected revision {body.part_number}"
            + (f" rev {body.revision}" if body.revision else "")
            + f" to ECO {number}",
        )
        return JSONResponse(
            status_code=202,
            content=ConfirmationProposed(confirmation_id=conf.id, summary=conf.summary).model_dump(
                mode="json"
            ),
        )
    rev = change_service.add_affected_revision(
        db,
        user=user,
        eco=eco,
        part_number=body.part_number,
        revision=body.revision,
        reason=body.reason,
    )
    return AffectedRevisionResponse(
        revision_id=rev.id,
        part_number=rev.part.part_number,
        revision=rev.revision,
        status=rev.status,
    )


@router.delete("/ecos/{number}/affected-revisions/{revision_id}", status_code=204)
def remove_affected_revision(
    number: str,
    revision_id: uuid.UUID,
    db: DbSession,
    user: Annotated[User, Depends(require_editor)],
):
    eco = change_service.get_eco_by_number(db, number)
    change_service.remove_affected_revision(db, user=user, eco=eco, revision_id=revision_id)
