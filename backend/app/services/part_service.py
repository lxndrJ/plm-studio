from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models.bom import BomItem
from app.models.part import Part, PartRevision
from app.models.user import User
from app.services import audit as audit_service
from app.services.attributes import validate_attributes
from app.services.numbering import allocate_number, find_duplicate_candidates, next_revision_label


def create_part(
    db: Session,
    *,
    user: User,
    name: str,
    part_type: str,
    class_id,
    description: str | None = None,
    attributes: dict | None = None,
    reason: str | None = None,
) -> Part:
    attrs = attributes or {}
    validate_attributes(db, class_id, attrs)
    find_duplicate_candidates(db, name=name, class_id=class_id)
    part_number = allocate_number(db, "ASM" if part_type == "assembly" else "PART")
    part = Part(
        part_number=part_number,
        name=name,
        description=description,
        part_type=part_type,
        class_id=class_id,
    )
    db.add(part)
    db.flush()
    rev = PartRevision(
        part_id=part.id,
        revision="01",
        status="draft",
        change_reason=reason or "initial revision",
        attributes=attrs,
        created_by=user.id,
    )
    db.add(rev)
    db.flush()
    audit_service.log_change(
        db,
        entity_type="part",
        entity_id=part.id,
        action="create",
        user_id=user.id,
        new_values={
            "part_number": part.part_number,
            "name": part.name,
            "part_type": part.part_type,
            "class_id": str(class_id),
        },
        reason=reason,
    )
    audit_service.log_change(
        db,
        entity_type="part_revision",
        entity_id=rev.id,
        action="create",
        user_id=user.id,
        new_values={
            "part_number": part.part_number,
            "revision": rev.revision,
            "status": rev.status,
            "attributes": attrs,
        },
        reason=rev.change_reason,
    )
    db.commit()
    db.refresh(part)
    return part


def create_revision(
    db: Session,
    *,
    user: User,
    part: Part,
    change_reason: str,
    base_revision: PartRevision | None = None,
    commit: bool = True,
) -> PartRevision:
    """New revision of a part. Released revisions are immutable, so changes
    always land in a fresh draft that inherits BOM and attributes of the
    latest revision (or of base_revision, e.g. the ECO-affected revision).
    commit=False lets the caller bundle several revisions into one transaction."""
    label = next_revision_label(db, part.id)
    if base_revision is not None:
        previous = base_revision
    else:
        previous = db.execute(
            select(PartRevision)
            .where(PartRevision.part_id == part.id)
            .order_by(PartRevision.revision.desc())
            .limit(1)
        ).scalar_one_or_none()
    rev = PartRevision(
        part_id=part.id,
        revision=label,
        status="draft",
        change_reason=change_reason,
        attributes=dict(previous.attributes) if previous is not None else {},
        created_by=user.id,
    )
    db.add(rev)
    db.flush()
    if previous is not None:
        for item in db.execute(
            select(BomItem).where(BomItem.parent_rev_id == previous.id)
        ).scalars():
            db.add(
                BomItem(
                    parent_rev_id=rev.id,
                    component_rev_id=item.component_rev_id,
                    quantity=item.quantity,
                    unit=item.unit,
                    position=item.position,
                )
            )
    audit_service.log_change(
        db,
        entity_type="part_revision",
        entity_id=rev.id,
        action="create",
        user_id=user.id,
        new_values={
            "part_number": part.part_number,
            "revision": rev.revision,
            "status": rev.status,
        },
        reason=change_reason,
    )
    if commit:
        db.commit()
        db.refresh(rev)
    return rev


def transition_revision(
    db: Session,
    *,
    user: User,
    revision: PartRevision,
    to_status: str,
    reason: str,
) -> PartRevision:
    from app.services.workflow import assert_transition_allowed

    assert_transition_allowed(
        db,
        entity_type="part_revision",
        from_status=revision.status,
        to_status=to_status,
        user_role=user.role,
    )
    old = {"status": revision.status}
    revision.status = to_status
    audit_service.log_change(
        db,
        entity_type="part_revision",
        entity_id=revision.id,
        action="transition",
        user_id=user.id,
        old_values=old,
        new_values={"status": to_status},
        reason=reason,
    )
    db.commit()
    db.refresh(revision)
    return revision


def assert_revision_mutable(rev: PartRevision) -> None:
    """Defense in depth next to the Postgres trigger: released revisions are
    immutable, changes require a new revision."""
    if rev.status == "released":
        raise ConflictError(
            "released revision is immutable; create a new revision instead",
            code="released_immutable",
        )


def _class_subtree_ids(db: Session, class_code: str) -> list:
    """The class itself plus all (transitive) subclasses; cycle-safe."""
    from app.models.numbering import PartClass

    root = db.execute(select(PartClass).where(PartClass.code == class_code)).scalar_one_or_none()
    if root is None:
        raise NotFoundError(f"part class '{class_code}' not found", code="class_not_found")
    ids = {root.id}
    frontier = [root.id]
    while frontier:
        children = db.execute(
            select(PartClass.id).where(PartClass.parent_id.in_(frontier))
        ).scalars()
        new = [c for c in children if c not in ids]
        ids.update(new)
        frontier = new
    return list(ids)


def search_parts(
    db: Session, query: str | None, class_code: str | None, limit: int = 50
) -> list[Part]:
    stmt = select(Part).order_by(Part.part_number).limit(limit)
    if query:
        like = f"%{query}%"
        stmt = stmt.where((Part.part_number.ilike(like)) | (Part.name.ilike(like)))
    if class_code:
        stmt = stmt.where(Part.class_id.in_(_class_subtree_ids(db, class_code)))
    return list(db.execute(stmt).scalars())


def get_part_with_revisions(db: Session, part_number: str) -> Part:
    part = db.execute(select(Part).where(Part.part_number == part_number)).scalar_one_or_none()
    if part is None:
        raise NotFoundError(f"part '{part_number}' not found", code="part_not_found")
    return part
