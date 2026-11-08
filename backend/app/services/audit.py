import uuid

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def log_change(
    db: Session,
    *,
    entity_type: str,
    entity_id: uuid.UUID | str,
    action: str,
    user_id: uuid.UUID,
    old_values: dict | None = None,
    new_values: dict | None = None,
    reason: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        old_values=old_values,
        new_values=new_values,
        reason=reason,
        user_id=user_id,
    )
    db.add(entry)
    db.flush()
    return entry
