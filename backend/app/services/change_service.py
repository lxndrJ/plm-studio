import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models.change import Eco, Ecr
from app.models.part import PartRevision
from app.models.user import User
from app.services import audit as audit_service
from app.services import part_service
from app.services.bom_service import resolve_component_revision
from app.services.numbering import allocate_number
from app.services.workflow import assert_transition_allowed


def list_ecrs(db: Session, status: str | None = None) -> list[Ecr]:
    stmt = select(Ecr).order_by(Ecr.number)
    if status:
        stmt = stmt.where(Ecr.status == status)
    return list(db.execute(stmt).scalars())


def get_ecr_by_number(db: Session, number: str) -> Ecr:
    ecr = db.execute(select(Ecr).where(Ecr.number == number)).scalar_one_or_none()
    if ecr is None:
        raise NotFoundError(f"ECR '{number}' not found", code="ecr_not_found")
    return ecr


def create_ecr(db: Session, *, user: User, description: str, reason: str | None = None) -> Ecr:
    ecr = Ecr(number=allocate_number(db, "ECR"), description=description, status="open")
    db.add(ecr)
    db.flush()
    audit_service.log_change(
        db,
        entity_type="ecr",
        entity_id=ecr.id,
        action="create",
        user_id=user.id,
        new_values={"number": ecr.number, "status": ecr.status, "description": description},
        reason=reason,
    )
    db.commit()
    db.refresh(ecr)
    return ecr


def transition_ecr(db: Session, *, user: User, ecr: Ecr, to_status: str, reason: str) -> Ecr:
    assert_transition_allowed(
        db, entity_type="ecr", from_status=ecr.status, to_status=to_status, user_role=user.role
    )
    old = {"status": ecr.status}
    ecr.status = to_status
    audit_service.log_change(
        db,
        entity_type="ecr",
        entity_id=ecr.id,
        action="transition",
        user_id=user.id,
        old_values=old,
        new_values={"status": to_status},
        reason=reason,
    )
    db.commit()
    db.refresh(ecr)
    return ecr


def list_ecos(db: Session, status: str | None = None) -> list[Eco]:
    stmt = select(Eco).order_by(Eco.number)
    if status:
        stmt = stmt.where(Eco.status == status)
    return list(db.execute(stmt).scalars())


def get_eco_by_number(db: Session, number: str) -> Eco:
    eco = db.execute(select(Eco).where(Eco.number == number)).scalar_one_or_none()
    if eco is None:
        raise NotFoundError(f"ECO '{number}' not found", code="eco_not_found")
    return eco


def create_eco(db: Session, *, user: User, ecr: Ecr, reason: str | None = None) -> Eco:
    """An ECO implements an ECR; it can only be raised once the ECR is approved."""
    if ecr.status != "approved":
        raise ConflictError(
            f"ECR '{ecr.number}' is '{ecr.status}'; an ECO can only be created for an approved ECR",
            code="ecr_not_approved",
            details={"ecr_number": ecr.number, "ecr_status": ecr.status},
        )
    eco = Eco(number=allocate_number(db, "ECO"), ecr_id=ecr.id, status="draft")
    db.add(eco)
    db.flush()
    audit_service.log_change(
        db,
        entity_type="eco",
        entity_id=eco.id,
        action="create",
        user_id=user.id,
        new_values={"number": eco.number, "status": eco.status, "ecr_number": ecr.number},
        reason=reason,
    )
    db.commit()
    db.refresh(eco)
    return eco


def transition_eco(
    db: Session, *, user: User, eco: Eco, to_status: str, reason: str
) -> tuple[Eco, list[dict]]:
    """Workflow transition of an ECO. `approved -> executed` additionally creates
    one successor draft revision per affected (released) part revision, inheriting
    attributes and BOM; everything in one transaction. Returns (eco, created).
    Re-execution is impossible: the workflow matrix has no executed -> executed row."""
    assert_transition_allowed(
        db, entity_type="eco", from_status=eco.status, to_status=to_status, user_role=user.role
    )
    created: list[dict] = []
    if to_status == "executed":
        ecr = eco.ecr
        for rev in eco.affected_revisions:
            change_reason = f"ECO {eco.number} (ECR {ecr.number}): {ecr.description}"
            new_rev = part_service.create_revision(
                db,
                user=user,
                part=rev.part,
                change_reason=change_reason,
                base_revision=rev,
                commit=False,
            )
            created.append(
                {
                    "part_number": rev.part.part_number,
                    "revision": new_rev.revision,
                    "revision_id": str(new_rev.id),
                    "status": new_rev.status,
                }
            )
    old = {"status": eco.status}
    eco.status = to_status
    audit_service.log_change(
        db,
        entity_type="eco",
        entity_id=eco.id,
        action="transition",
        user_id=user.id,
        old_values=old,
        new_values={"status": to_status},
        reason=reason,
    )
    if created:
        audit_service.log_change(
            db,
            entity_type="eco",
            entity_id=eco.id,
            action="execute",
            user_id=user.id,
            new_values={"eco_number": eco.number, "created_revisions": created},
            reason=reason,
        )
    db.commit()
    db.refresh(eco)
    return eco, created


def _assert_eco_draft(eco: Eco) -> None:
    if eco.status != "draft":
        raise ConflictError(
            f"ECO '{eco.number}' is '{eco.status}'; affected revisions can only be changed in draft",
            code="eco_not_draft",
            details={"eco_number": eco.number, "eco_status": eco.status},
        )


def add_affected_revision(
    db: Session,
    *,
    user: User,
    eco: Eco,
    part_number: str,
    revision: str | None = None,
    reason: str | None = None,
) -> PartRevision:
    _assert_eco_draft(eco)
    rev = resolve_component_revision(db, part_number, revision)
    if rev.status != "released":
        raise ConflictError(
            f"only released revisions can be affected by an ECO "
            f"(got '{rev.status}' for {part_number} rev {rev.revision})",
            code="affected_not_released",
            details={
                "eco_number": eco.number,
                "part_number": part_number,
                "revision": rev.revision,
                "status": rev.status,
            },
        )
    if any(r.id == rev.id for r in eco.affected_revisions):
        raise ConflictError(
            f"revision {rev.revision} of '{part_number}' is already affected by ECO '{eco.number}'",
            code="duplicate_affected_revision",
            details={
                "eco_number": eco.number,
                "part_number": part_number,
                "revision": rev.revision,
            },
        )
    eco.affected_revisions.append(rev)
    db.flush()
    audit_service.log_change(
        db,
        entity_type="eco",
        entity_id=eco.id,
        action="add_affected_revision",
        user_id=user.id,
        new_values={
            "eco_number": eco.number,
            "part_number": part_number,
            "revision": rev.revision,
            "revision_id": str(rev.id),
        },
        reason=reason,
    )
    db.commit()
    db.refresh(rev)
    return rev


def remove_affected_revision(
    db: Session, *, user: User, eco: Eco, revision_id: uuid.UUID, reason: str | None = None
) -> None:
    _assert_eco_draft(eco)
    rev = next((r for r in eco.affected_revisions if r.id == revision_id), None)
    if rev is None:
        raise NotFoundError(
            f"revision {revision_id} is not affected by ECO '{eco.number}'",
            code="affected_revision_not_found",
        )
    part_number = rev.part.part_number
    eco.affected_revisions.remove(rev)
    audit_service.log_change(
        db,
        entity_type="eco",
        entity_id=eco.id,
        action="remove_affected_revision",
        user_id=user.id,
        old_values={
            "eco_number": eco.number,
            "part_number": part_number,
            "revision": rev.revision,
            "revision_id": str(rev.id),
        },
        reason=reason,
    )
    db.commit()
