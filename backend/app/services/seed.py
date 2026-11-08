from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.numbering import PartClass
from app.models.workflow import DEFAULT_TRANSITIONS, WorkflowTransition

DEFAULT_CLASSES = [
    ("MECH", "Mechanik", {"material": "", "weight_kg": None}),
    ("ELEC", "Elektronik", {"voltage_v": None}),
    ("CONS", "Consumables", {"supplier": ""}),
    ("PACK", "Verpackung", {"material": ""}),
]


def seed_workflow_transitions(db: Session) -> None:
    existing = db.execute(select(WorkflowTransition.id).limit(1)).first()
    if existing:
        return
    for entity_type, from_status, to_status, role in DEFAULT_TRANSITIONS:
        db.add(
            WorkflowTransition(
                entity_type=entity_type,
                from_status=from_status,
                to_status=to_status,
                required_role=role,
            )
        )
    db.commit()


def seed_part_classes(db: Session) -> None:
    for code, name, attrs in DEFAULT_CLASSES:
        exists = db.execute(select(PartClass.id).where(PartClass.code == code)).first()
        if not exists:
            db.add(PartClass(code=code, name=name, default_attributes=attrs))
    db.commit()


def seed_all(db: Session) -> None:
    from app.services.numbering import ensure_default_ranges

    ensure_default_ranges(db)
    seed_workflow_transitions(db)
    seed_part_classes(db)
