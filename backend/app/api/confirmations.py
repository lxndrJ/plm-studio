import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.guardrails import confirmations as conf_guard
from app.guardrails.permissions import require_editor
from app.models.confirmation import Confirmation
from app.models.user import User
from app.schemas.confirmation import ConfirmationResponse

router = APIRouter(prefix="/confirmations", tags=["confirmations"])


@router.get("", response_model=list[ConfirmationResponse])
def list_confirmations(
    db: DbSession, user: CurrentUser, status: Annotated[str | None, Query()] = None
):
    stmt = select(Confirmation).order_by(Confirmation.created_at.desc())
    if status:
        stmt = stmt.where(Confirmation.status == status)
    return [ConfirmationResponse.model_validate(c) for c in db.execute(stmt).scalars()]


@router.get("/{confirmation_id}", response_model=ConfirmationResponse)
def get_confirmation(confirmation_id: uuid.UUID, db: DbSession, user: CurrentUser):
    conf = conf_guard.get_confirmation(db, confirmation_id)
    return ConfirmationResponse.model_validate(conf)


@router.post("/{confirmation_id}/approve", response_model=ConfirmationResponse)
def approve(
    confirmation_id: uuid.UUID, db: DbSession, user: Annotated[User, Depends(require_editor)]
):
    return ConfirmationResponse.model_validate(
        conf_guard.resolve(db, user=user, confirmation_id=confirmation_id, approve=True)
    )


@router.post("/{confirmation_id}/reject", response_model=ConfirmationResponse)
def reject(
    confirmation_id: uuid.UUID, db: DbSession, user: Annotated[User, Depends(require_editor)]
):
    return ConfirmationResponse.model_validate(
        conf_guard.resolve(db, user=user, confirmation_id=confirmation_id, approve=False)
    )
