"""Deterministic generator for clearly separable test data (dev/demo only).

Creates the part class 'TEST' (separable via GET /parts?class_code=TEST or a
'TEST' search) with typed attributes saison/farbe/preis/groesse. ~80% single
parts (P-...) and ~20% assemblies (ASM-...) with 2-5 BOM lines each; with
--levels N the assemblies are built level by level and higher levels may
contain lower-level assemblies (multi-level BOM, where-used depth > 1). Every
record carries the name prefix 'TEST ' and a description marker. The workflow
has no 'test' status (only draft/review/released/obsolete), so class + prefix
are the separator. SKU is the part number (assigned by the number range).

Usage against a dev DB (README quickstart):
    python -m app.services.testdata --count 200
    python -m app.services.testdata --count 2000 --levels 3 --reset
"""

import argparse
import random

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.bom import BomItem
from app.models.change import eco_part_revisions
from app.models.numbering import ClassAttribute, PartClass
from app.models.part import Part, PartRevision
from app.models.user import User
from app.services import audit as audit_service
from app.services import part_service
from app.services.bom_service import add_bom_item, latest_revision, resolve_component_revision

TEST_CLASS_CODE = "TEST"
TEST_NAME_PREFIX = "TEST "
TEST_DESCRIPTION_MARKER = "TESTDATENSATZ"

SAISONS = ["Fruehling", "Sommer", "Herbst", "Winter"]
COLORS = ["rot", "blau", "gruen", "schwarz", "weiss", "gelb", "grau", "beige"]
SIZES = ["XS", "S", "M", "L", "XL"]
VARIANTS = ["Classic", "Slim", "Weit", "Sport", "Premium"]
ARTICLE_WORDS = [
    "Hemd",
    "T-Shirt",
    "Hose",
    "Jacke",
    "Kleid",
    "Pullover",
    "Schal",
    "Muetze",
    "Schuh",
    "Tasche",
    "Guertel",
    "Rock",
    "Bluse",
    "Jeans",
    "Sneaker",
    "Stiefel",
    "Cap",
    "Handschuh",
    "Socken",
    "Leggings",
    "Weste",
    "Parka",
    "Trenchcoat",
    "Polo",
]

TEST_CLASS_ATTRIBUTES = [
    ("saison", "Saison", "enum", None, False, SAISONS),
    ("farbe", "Farbe", "string", None, False, None),
    ("preis", "Preis (EUR)", "number", None, False, None),
    ("groesse", "Groesse", "enum", None, False, SIZES),
]


def ensure_test_class(db: Session) -> PartClass:
    cls = db.execute(
        select(PartClass).where(PartClass.code == TEST_CLASS_CODE)
    ).scalar_one_or_none()
    if cls is None:
        cls = PartClass(code=TEST_CLASS_CODE, name="Testdaten", default_attributes={})
        db.add(cls)
        db.flush()
    for key, label, attr_type, unit_code, required, allowed in TEST_CLASS_ATTRIBUTES:
        exists = db.execute(
            select(ClassAttribute.id).where(
                ClassAttribute.class_id == cls.id, ClassAttribute.key == key
            )
        ).scalar_one_or_none()
        if exists is None:
            db.add(
                ClassAttribute(
                    class_id=cls.id,
                    key=key,
                    label=label,
                    attr_type=attr_type,
                    unit_code=unit_code,
                    required=required,
                    allowed_values=allowed,
                )
            )
    db.commit()
    return cls


def _system_user(db: Session) -> User:
    user = db.execute(
        select(User).where(User.role == "admin").order_by(User.email)
    ).scalar_one_or_none()
    if user is None:
        user = db.execute(select(User).order_by(User.email)).scalar_one_or_none()
    if user is None:
        from app.core import security

        user = User(
            email="system@plm-studio.dev",
            password_hash=security.hash_password("system"),
            role="admin",
        )
        db.add(user)
        db.commit()
    return user


def _attributes(
    rng: random.Random, price_min: float, price_max: float, with_size: bool = False
) -> dict:
    attrs = {
        "saison": rng.choice(SAISONS),
        "farbe": rng.choice(COLORS),
        "preis": round(rng.uniform(price_min, price_max), 2),
    }
    if with_size:
        attrs["groesse"] = rng.choice(SIZES)
    return attrs


def seed_test_data(
    db: Session,
    *,
    count: int = 200,
    seed: int = 42,
    assembly_ratio: float = 0.2,
    levels: int = 1,
) -> dict:
    if count < 1:
        raise ValueError("count must be >= 1")
    if levels < 1:
        raise ValueError("levels must be >= 1")
    rng = random.Random(seed)
    cls = ensure_test_class(db)
    user = _system_user(db)
    n_assemblies = max(1, round(count * assembly_ratio)) if count >= 5 else 0
    n_parts = count - n_assemblies
    description = f"{TEST_DESCRIPTION_MARKER} (Seeder, seed={seed})"

    components: list[Part] = []
    for i in range(n_parts):
        part = part_service.create_part(
            db,
            user=user,
            name=f"{TEST_NAME_PREFIX}{rng.choice(ARTICLE_WORDS)} {rng.choice(VARIANTS)} {i + 1:04d}",
            part_type="part",
            class_id=cls.id,
            description=description,
            attributes=_attributes(rng, 4.99, 499.99, with_size=True),
            reason="Testdatensatz",
        )
        components.append(part)

    bom_lines = 0
    base = n_assemblies // levels
    rem = n_assemblies % levels
    per_level_assemblies: list[list[Part]] = []
    for lvl in range(levels):
        # pool of allowed components for this level: parts + assemblies of lower levels
        pool = components + [a for lower in per_level_assemblies for a in lower]
        n_lvl = base + (1 if lvl < rem else 0)
        lvl_assemblies: list[Part] = []
        for j in range(n_lvl):
            asm = part_service.create_part(
                db,
                user=user,
                name=f"{TEST_NAME_PREFIX}Baugruppe L{lvl + 1} {j + 1:04d}",
                part_type="assembly",
                class_id=cls.id,
                description=description,
                attributes=_attributes(rng, 49.99, 1999.99),
                reason="Testdatensatz",
            )
            parent_rev = latest_revision(db, asm.id)
            chosen = rng.sample(pool, k=min(rng.randint(2, 5), len(pool)))
            for position, comp in enumerate(chosen, start=1):
                component_rev = resolve_component_revision(db, comp.part_number, None)
                item = add_bom_item(
                    db,
                    parent_rev=parent_rev,
                    component_rev=component_rev,
                    quantity=rng.randint(1, 4),
                    unit="Stk",
                    position=position,
                )
                audit_service.log_change(
                    db,
                    entity_type="bom_item",
                    entity_id=item.id,
                    action="create",
                    user_id=user.id,
                    new_values={
                        "parent_part_number": asm.part_number,
                        "component_part_number": comp.part_number,
                        "quantity": float(item.quantity),
                        "unit": item.unit,
                        "position": position,
                    },
                    reason="Testdatensatz",
                )
                db.commit()
                bom_lines += 1
            lvl_assemblies.append(asm)
        per_level_assemblies.append(lvl_assemblies)

    return {
        "class_code": TEST_CLASS_CODE,
        "parts": n_parts,
        "assemblies": n_assemblies,
        "bom_lines": bom_lines,
        "levels": levels,
        "seed": seed,
    }


def clear_test_data(db: Session) -> int:
    """Delete all parts of the TEST class (with their revisions and BOM lines).
    Audit log stays append-only and keeps the history."""
    cls = db.execute(
        select(PartClass).where(PartClass.code == TEST_CLASS_CODE)
    ).scalar_one_or_none()
    if cls is None:
        return 0
    parts = db.execute(select(Part).where(Part.class_id == cls.id)).scalars().all()
    if not parts:
        return 0
    part_ids = [p.id for p in parts]
    rev_ids = list(
        db.execute(select(PartRevision.id).where(PartRevision.part_id.in_(part_ids))).scalars()
    )
    if rev_ids:
        db.execute(delete(BomItem).where(BomItem.parent_rev_id.in_(rev_ids)))
        db.execute(delete(BomItem).where(BomItem.component_rev_id.in_(rev_ids)))
        db.execute(
            delete(eco_part_revisions).where(eco_part_revisions.c.part_revision_id.in_(rev_ids))
        )
        db.execute(delete(PartRevision).where(PartRevision.id.in_(rev_ids)))
    user = _system_user(db)
    for part in parts:
        audit_service.log_change(
            db,
            entity_type="part",
            entity_id=part.id,
            action="delete_test_data",
            user_id=user.id,
            old_values={
                "part_number": part.part_number,
                "name": part.name,
                "class_code": TEST_CLASS_CODE,
            },
            reason="Testdaten zurueckgesetzt",
        )
    db.execute(delete(Part).where(Part.id.in_(part_ids)))
    db.commit()
    return len(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed clearly separable PLM test data (class TEST)."
    )
    parser.add_argument(
        "--count", type=int, default=200, help="total number of test articles (default 200)"
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="RNG seed for reproducible data (default 42)"
    )
    parser.add_argument(
        "--levels",
        type=int,
        default=1,
        help="BOM depth: assemblies may contain lower-level assemblies (default 1 = flat)",
    )
    parser.add_argument(
        "--reset", action="store_true", help="delete existing TEST-class data first"
    )
    args = parser.parse_args(argv)

    from app.core.db import SessionLocal, engine
    from app.models import Base
    from app.services.seed import seed_all

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_all(db)
        if args.reset:
            removed = clear_test_data(db)
            print(f"removed {removed} existing TEST parts")
        stats = seed_test_data(db, count=args.count, seed=args.seed, levels=args.levels)
        print(
            f"seeded {stats['parts']} parts + {stats['assemblies']} assemblies "
            f"({stats['bom_lines']} BOM lines, {stats['levels']} level(s)) "
            f"into class '{TEST_CLASS_CODE}' (seed={stats['seed']})"
        )
        print(f"separable via: GET /api/v1/parts?class_code={TEST_CLASS_CODE}  or  ?query=TEST")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
