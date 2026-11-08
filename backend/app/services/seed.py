from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.numbering import ClassAttribute, PartClass
from app.models.units import Unit
from app.models.workflow import DEFAULT_TRANSITIONS, WorkflowTransition

# (code, name, default_attributes, parent_code)
DEFAULT_CLASSES = [
    ("MECH", "Mechanik", {"material": "", "weight_kg": None}, None),
    ("ELEC", "Elektronik", {"voltage_v": None}, None),
    ("CONS", "Consumables", {"supplier": ""}, None),
    ("PACK", "Verpackung", {"material": ""}, None),
    ("FAS", "Fastening technology", {}, "MECH"),
    ("PCB", "Leiterplatten", {}, "ELEC"),
]

DEFAULT_UNITS = [
    ("Stk", "Stueck", "count"),
    ("m", "Meter", "length"),
    ("mm", "Millimeter", "length"),
    ("kg", "Kilogramm", "mass"),
    ("g", "Gramm", "mass"),
    ("l", "Liter", "volume"),
    ("s", "Sekunde", "time"),
]

# (class_code, key, label, attr_type, unit_code, required, allowed_values)
DEFAULT_CLASS_ATTRIBUTES = [
    ("MECH", "material", "Material", "string", None, False, None),
    ("MECH", "weight_kg", "Gewicht", "number", "kg", False, None),
    ("ELEC", "voltage_v", "Nennspannung", "number", None, False, None),
    ("ELEC", "ip_rating", "Schutzart", "enum", None, False, ["IP20", "IP54", "IP65", "IP67"]),
    ("CONS", "supplier", "Lieferant", "string", None, False, None),
    ("PACK", "material", "Material", "string", None, False, None),
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


def seed_units(db: Session) -> None:
    for code, name, dimension in DEFAULT_UNITS:
        exists = db.execute(select(Unit.code).where(Unit.code == code)).first()
        if not exists:
            db.add(Unit(code=code, name=name, dimension=dimension))
    db.commit()


def seed_part_classes(db: Session) -> None:
    ids_by_code = dict(db.execute(select(PartClass.code, PartClass.id)).fetchall())
    for code, name, attrs, parent_code in DEFAULT_CLASSES:
        exists = db.execute(select(PartClass.id).where(PartClass.code == code)).first()
        if not exists:
            cls = PartClass(
                code=code,
                name=name,
                default_attributes=attrs,
                parent_id=ids_by_code.get(parent_code) if parent_code else None,
            )
            db.add(cls)
            db.flush()
            ids_by_code[code] = cls.id
    db.commit()


def seed_class_attributes(db: Session) -> None:
    ids_by_code = dict(db.execute(select(PartClass.code, PartClass.id)).fetchall())
    for cls_code, key, label, attr_type, unit_code, required, allowed in DEFAULT_CLASS_ATTRIBUTES:
        class_id = ids_by_code.get(cls_code)
        if class_id is None:
            continue
        exists = db.execute(
            select(ClassAttribute.id).where(ClassAttribute.class_id == class_id, ClassAttribute.key == key)
        ).first()
        if not exists:
            db.add(
                ClassAttribute(
                    class_id=class_id,
                    key=key,
                    label=label,
                    attr_type=attr_type,
                    unit_code=unit_code,
                    required=required,
                    allowed_values=allowed,
                )
            )
    db.commit()


def seed_all(db: Session) -> None:
    from app.services.numbering import ensure_default_ranges

    ensure_default_ranges(db)
    seed_workflow_transitions(db)
    seed_units(db)
    seed_part_classes(db)
    seed_class_attributes(db)
