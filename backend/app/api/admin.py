from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.deps import CurrentUser, DbSession
from app.core.errors import ConflictError, NotFoundError
from app.guardrails.permissions import require_admin
from app.models.audit import AuditLog
from app.models.confirmation import Confirmation
from app.models.numbering import NumberRange, PartClass
from app.models.part import Part
from app.models.user import User
from app.schemas.admin import (
    HealthResponse,
    NumberRangeCreate,
    NumberRangeResponse,
    PartClassCreate,
    PartClassResponse,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/health", response_model=HealthResponse, include_in_schema=False)
def health(db: DbSession):
    db_ok = "ok"
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        db_ok = "error"
    return HealthResponse(status="ok" if db_ok == "ok" else "degraded", database=db_ok)


@router.get(
    "/number-ranges",
    response_model=list[NumberRangeResponse],
    dependencies=[Depends(require_admin)],
)
def list_number_ranges(db: DbSession):
    return list(db.execute(select(NumberRange).order_by(NumberRange.code)).scalars())


@router.post(
    "/number-ranges",
    response_model=NumberRangeResponse,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
def create_number_range(body: NumberRangeCreate, db: DbSession):
    if db.execute(select(NumberRange).where(NumberRange.code == body.code)).scalar_one_or_none():
        raise ConflictError(f"number range '{body.code}' already exists", code="range_exists")
    rng = NumberRange(code=body.code, prefix=body.prefix, width=body.width, next_number=1)
    db.add(rng)
    db.commit()
    db.refresh(rng)
    return NumberRangeResponse.model_validate(rng)


@router.get("/part-classes", response_model=list[PartClassResponse])
def list_part_classes(db: DbSession):
    from app.models.numbering import ClassAttribute
    from app.schemas.admin import ClassAttributeResponse

    classes = list(db.execute(select(PartClass).order_by(PartClass.code)).scalars())
    defs = db.execute(select(ClassAttribute)).scalars().all()
    by_class: dict = {}
    for d in defs:
        by_class.setdefault(d.class_id, []).append(ClassAttributeResponse.model_validate(d))
    return [
        PartClassResponse(
            id=c.id,
            code=c.code,
            name=c.name,
            default_attributes=c.default_attributes,
            parent_id=c.parent_id,
            attributes=by_class.get(c.id, []),
        )
        for c in classes
    ]


@router.post(
    "/part-classes",
    response_model=PartClassResponse,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
def create_part_class(body: PartClassCreate, db: DbSession):
    if db.execute(select(PartClass).where(PartClass.code == body.code)).scalar_one_or_none():
        raise ConflictError(f"part class '{body.code}' already exists", code="class_exists")
    parent_id = None
    if body.parent_code is not None:
        parent = db.execute(
            select(PartClass).where(PartClass.code == body.parent_code)
        ).scalar_one_or_none()
        if parent is None:
            raise NotFoundError(
                f"parent part class '{body.parent_code}' not found", code="class_not_found"
            )
        # A newly created class has no children, so it can never close a
        # cycle; no re-parenting endpoint exists (ADR 0002).
        parent_id = parent.id
    cls = PartClass(
        code=body.code,
        name=body.name,
        default_attributes=body.default_attributes,
        parent_id=parent_id,
    )
    db.add(cls)
    db.commit()
    db.refresh(cls)
    return PartClassResponse.model_validate(cls)


@router.get("/audit-log", dependencies=[Depends(require_admin)])
def audit_log(db: DbSession, limit: int = 100):
    rows = db.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)).scalars()
    return [
        {
            "id": r.id,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "action": r.action,
            "old_values": r.old_values,
            "new_values": r.new_values,
            "reason": r.reason,
            "user_id": str(r.user_id),
            "at": r.at.isoformat() if r.at else None,
        }
        for r in rows
    ]


@router.get("/stats")
def stats(db: DbSession, user: CurrentUser):
    return {
        "users": db.execute(select(func.count(User.id))).scalar_one(),
        "parts": db.execute(select(func.count(Part.id))).scalar_one(),
        "open_confirmations": db.execute(
            select(func.count(Confirmation.id)).where(Confirmation.status == "proposed")
        ).scalar_one(),
    }
