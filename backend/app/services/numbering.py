from sqlalchemy import select

from app.core.errors import ConflictError, NotFoundError
from app.models.numbering import NumberRange


def allocate_number(db, code: str) -> str:
    """Atomically take the next number of a range and format it as
    '<prefix><zero-padded number>' (prefix already contains the separator,
    e.g. 'P-' -> 'P-000001'). UPDATE ... RETURNING makes the increment
    race-free even with concurrent requests."""
    from sqlalchemy import update

    stmt = (
        update(NumberRange)
        .where(NumberRange.code == code)
        .values(next_number=NumberRange.next_number + 1)
        .returning(NumberRange.prefix, NumberRange.width, NumberRange.next_number - 1)
    )
    row = db.execute(stmt).first()
    if row is None:
        raise NotFoundError(f"number range '{code}' does not exist", code="number_range_missing")
    prefix, width, number = row
    return f"{prefix}{number:0{width}d}"


def get_range(db, code: str) -> NumberRange:
    rng = db.execute(select(NumberRange).where(NumberRange.code == code)).scalar_one_or_none()
    if rng is None:
        raise NotFoundError(f"number range '{code}' does not exist", code="number_range_missing")
    return rng


def ensure_default_ranges(db) -> None:
    # prefixes per docs/number-ranges.md
    defaults = [
        ("PART", "P-", 6),
        ("ASM", "ASM-", 6),
        ("DOC", "DOC-", 6),
        ("ECR", "ECR-", 5),
        ("ECO", "ECO-", 5),
        ("RPT", "RPT-", 5),
    ]
    for code, prefix, width in defaults:
        exists = db.execute(select(NumberRange.id).where(NumberRange.code == code)).first()
        if not exists:
            db.add(NumberRange(code=code, prefix=prefix, width=width, next_number=1))
    db.commit()


def next_revision_label(db, part_id) -> str:
    """Sequential, zero-padded revision labels per part: 01, 02, 03 ..."""
    from sqlalchemy import func, select

    from app.models.part import PartRevision

    max_rev = db.execute(
        select(func.max(PartRevision.revision)).where(PartRevision.part_id == part_id)
    ).scalar_one()
    if max_rev is None:
        return "01"
    return f"{int(max_rev) + 1:02d}"


def find_duplicate_candidates(db, *, name: str, class_id, exclude_part_id=None) -> list:
    """Case/diacritic-insensitive name match within the same class."""
    from sqlalchemy import func, select

    from app.models.part import Part

    normalized = func.lower(func.trim(name))
    stmt = select(Part).where(Part.class_id == class_id, normalized == func.lower(func.trim(Part.name)))
    if exclude_part_id is not None:
        stmt = stmt.where(Part.id != exclude_part_id)
    rows = db.execute(stmt).scalars().all()
    if rows:
        raise ConflictError(
            "duplicate candidate(s) found: identical name in the same class",
            code="duplicate_part",
            details={"candidates": [{"part_number": p.part_number, "name": p.name} for p in rows]},
        )
    return []
