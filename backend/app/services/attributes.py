"""Typed attribute validation against class definitions (ADR 0002).

Policy: keys without a definition pass through (hybrid model); defined keys
are validated for required, type and enum membership.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.models.numbering import ClassAttribute


def get_definitions(db: Session, class_id) -> dict[str, ClassAttribute]:
    return {
        d.key: d
        for d in db.execute(select(ClassAttribute).where(ClassAttribute.class_id == class_id)).scalars()
    }


def validate_attributes(db: Session, class_id, attributes: dict) -> None:
    definitions = get_definitions(db, class_id)
    problems: list[str] = []

    for key, definition in definitions.items():
        if definition.required and (key not in attributes or attributes[key] is None):
            problems.append(f"'{key}' is required")

    for key, value in attributes.items():
        definition = definitions.get(key)
        if definition is None or value is None:
            continue
        if definition.attr_type == "string":
            if not isinstance(value, str):
                problems.append(f"'{key}' must be a string")
        elif definition.attr_type == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                problems.append(f"'{key}' must be a number")
        elif definition.attr_type == "boolean":
            if not isinstance(value, bool):
                problems.append(f"'{key}' must be a boolean")
        elif definition.attr_type == "enum":
            allowed = definition.allowed_values or []
            if value not in allowed:
                problems.append(f"'{key}' must be one of {allowed}")

    if problems:
        raise ValidationError(
            "invalid attributes: " + "; ".join(problems),
            code="invalid_attributes",
            details={"problems": problems},
        )
