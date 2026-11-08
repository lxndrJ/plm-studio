from decimal import Decimal

from sqlalchemy import Integer, Select, cast, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.bom import BomItem
from app.models.part import Part, PartRevision

ALLOWED_COMPONENT_STATUSES = ("draft", "released")


def assert_valid_unit(db: Session, unit: str) -> None:
    """BOM units must exist in the units master data (ADR 0002)."""
    from app.models.units import Unit

    exists = db.execute(select(Unit.code).where(Unit.code == unit)).scalar_one_or_none()
    if exists is None:
        raise ValidationError(f"unit '{unit}' is not in the units master data", code="unknown_unit")


def get_revision_or_404(db: Session, revision_id) -> PartRevision:
    rev = db.get(PartRevision, revision_id)
    if rev is None:
        raise NotFoundError(f"revision {revision_id} not found", code="revision_not_found")
    return rev


def get_part_by_number(db: Session, part_number: str) -> Part:
    part = db.execute(select(Part).where(Part.part_number == part_number)).scalar_one_or_none()
    if part is None:
        raise NotFoundError(f"part '{part_number}' not found", code="part_not_found")
    return part


def latest_revision(db: Session, part_id) -> PartRevision | None:
    return db.execute(
        select(PartRevision)
        .where(PartRevision.part_id == part_id)
        .order_by(PartRevision.revision.desc())
        .limit(1)
    ).scalar_one_or_none()


def resolve_component_revision(db: Session, part_number: str, revision: str | None) -> PartRevision:
    part = get_part_by_number(db, part_number)
    if revision is not None:
        rev = db.execute(
            select(PartRevision).where(PartRevision.part_id == part.id, PartRevision.revision == revision)
        ).scalar_one_or_none()
        if rev is None:
            raise NotFoundError(
                f"revision '{revision}' of part '{part_number}' not found", code="revision_not_found"
            )
        return rev
    released = db.execute(
        select(PartRevision)
        .where(PartRevision.part_id == part.id, PartRevision.status == "released")
        .order_by(PartRevision.revision.desc())
        .limit(1)
    ).scalar_one_or_none()
    if released is not None:
        return released
    rev = latest_revision(db, part.id)
    if rev is None:
        raise NotFoundError(f"part '{part_number}' has no revisions", code="revision_not_found")
    return rev


def add_bom_item(
    db: Session,
    *,
    parent_rev: PartRevision,
    component_rev: PartRevision,
    quantity: float,
    unit: str,
    position: int,
) -> BomItem:
    if parent_rev.status != "draft":
        raise ConflictError(
            f"BOM of a '{parent_rev.status}' revision is immutable; create a new revision first",
            code="released_immutable",
        )
    if component_rev.status not in ALLOWED_COMPONENT_STATUSES:
        raise ValidationError(
            f"component revision status must be one of {ALLOWED_COMPONENT_STATUSES}, got '{component_rev.status}'",
            code="invalid_component_status",
        )
    if parent_rev.id == component_rev.id:
        raise ValidationError("a revision cannot be its own component", code="bom_self_reference")
    assert_valid_unit(db, unit)
    item = BomItem(
        parent_rev_id=parent_rev.id,
        component_rev_id=component_rev.id,
        quantity=Decimal(str(quantity)),
        unit=unit,
        position=position,
    )
    db.add(item)
    db.flush()
    return item


def get_bom(db: Session, parent_rev_id) -> list[BomItem]:
    return list(
        db.execute(
            select(BomItem)
            .where(BomItem.parent_rev_id == parent_rev_id)
            .order_by(BomItem.position)
        ).scalars()
    )


def where_used(db: Session, part_number: str) -> list[dict]:
    """Recursive where-used: all (parent revision, depth) that directly or
    transitively contain the given part, via a recursive CTE over bom_items."""
    part = get_part_by_number(db, part_number)

    base = (
        select(
            BomItem.parent_rev_id.label("parent_rev_id"),
            BomItem.component_rev_id.label("child_rev_id"),
            PartRevision.part_id.label("child_part_id"),
            cast(1, Integer).label("depth"),
        )
        .join(PartRevision, PartRevision.id == BomItem.component_rev_id)
        .where(PartRevision.part_id == part.id)
    )
    cte = base.cte("wu", recursive=True)
    recursive = (
        select(
            BomItem.parent_rev_id.label("parent_rev_id"),
            cte.c.child_rev_id.label("child_rev_id"),
            cte.c.child_part_id.label("child_part_id"),
            (cte.c.depth + 1).label("depth"),
        )
        .join(cte, BomItem.component_rev_id == cte.c.parent_rev_id)
    )
    wu = cte.union_all(recursive)

    stmt: Select = (
        select(
            wu.c.parent_rev_id,
            wu.c.depth,
            PartRevision.part_id.label("parent_part_id"),
            Part.part_number.label("parent_part_number"),
            PartRevision.revision.label("parent_revision"),
            PartRevision.status.label("parent_status"),
        )
        .join(PartRevision, PartRevision.id == wu.c.parent_rev_id)
        .join(Part, Part.id == PartRevision.part_id)
        .order_by(wu.c.depth, Part.part_number)
    )
    rows = db.execute(stmt).all()
    return [
        {
            "parent_part_number": r.parent_part_number,
            "parent_revision": r.parent_revision,
            "parent_status": r.parent_status,
            "parent_rev_id": str(r.parent_rev_id),
            "depth": r.depth,
        }
        for r in rows
    ]


def bom_diff(db: Session, parent_part_number: str, rev_a: str, rev_b: str) -> dict:
    parent = get_part_by_number(db, parent_part_number)

    def items_for(rev_label: str) -> dict:
        rev = db.execute(
            select(PartRevision).where(PartRevision.part_id == parent.id, PartRevision.revision == rev_label)
        ).scalar_one_or_none()
        if rev is None:
            raise NotFoundError(
                f"revision '{rev_label}' of part '{parent_part_number}' not found", code="revision_not_found"
            )
        out = {}
        for item in get_bom(db, rev.id):
            comp = db.get(PartRevision, item.component_rev_id)
            comp_part = db.get(Part, comp.part_id)
            out[(comp_part.part_number, comp.revision)] = {
                "quantity": float(item.quantity),
                "unit": item.unit,
                "position": item.position,
            }
        return out

    a, b = items_for(rev_a), items_for(rev_b)
    added = {k: v for k, v in b.items() if k not in a}
    removed = {k: v for k, v in a.items() if k not in b}
    changed = {
        k: {"from": a[k], "to": b[k]}
        for k in a.keys() & b.keys()
        if a[k]["quantity"] != b[k]["quantity"] or a[k]["unit"] != b[k]["unit"] or a[k]["position"] != b[k]["position"]
    }
    return {
        "part_number": parent_part_number,
        "rev_a": rev_a,
        "rev_b": rev_b,
        "added": [{"component": f"{k[0]} rev {k[1]}", **v} for k, v in added.items()],
        "removed": [{"component": f"{k[0]} rev {k[1]}", **v} for k, v in removed.items()],
        "changed": [
            {"component": f"{k[0]} rev {k[1]}", **v} for k, v in changed.items()
        ],
    }
