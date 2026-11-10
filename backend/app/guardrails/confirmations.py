"""Confirmation-token flow for proposed writes (agent path).

A mutating endpoint called without `direct=true` does not write; it stores a
Confirmation (status='proposed') and returns 202 + confirmation_id + summary.
The user approves via POST /api/v1/confirmations/{id}/approve, which
re-validates the payload with its Pydantic schema and re-checks the caller's
role before dispatching to the service function."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.confirmation import Confirmation
from app.models.user import User
from app.schemas.confirmation import payload_for_action
from app.services import part_service
from app.services.bom_service import (
    add_bom_item,
    get_part_by_number,
    get_revision_or_404,
    resolve_component_revision,
)


def propose(db: Session, *, user: User, action: str, payload: dict, summary: str) -> Confirmation:
    settings = get_settings()
    conf = Confirmation(
        action=action,
        summary=summary,
        payload=payload,
        status="proposed",
        created_by=user.id,
        expires_at=datetime.now(UTC) + timedelta(hours=settings.CONFIRMATION_TTL_HOURS),
    )
    db.add(conf)
    db.commit()
    db.refresh(conf)
    return conf


def _as_utc(dt: datetime) -> datetime:
    # SQLite returns naive datetimes for DateTime(timezone=True); treat as UTC
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def get_confirmation(db: Session, confirmation_id: uuid.UUID) -> Confirmation:
    conf = db.get(Confirmation, confirmation_id)
    if conf is None:
        raise NotFoundError(
            f"confirmation {confirmation_id} not found", code="confirmation_not_found"
        )
    return conf


def _execute(db: Session, user: User, conf: Confirmation) -> dict:
    schema_cls = payload_for_action(conf.action)
    payload = schema_cls.model_validate(conf.payload)
    if conf.action == "create_part":
        from app.models.numbering import PartClass

        class_id = db.execute(
            select(PartClass.id).where(PartClass.code == payload.class_code)
        ).scalar_one_or_none()
        if class_id is None:
            raise NotFoundError(
                f"part class '{payload.class_code}' not found", code="class_not_found"
            )
        part = part_service.create_part(
            db,
            user=user,
            name=payload.name,
            part_type=payload.part_type,
            class_id=class_id,
            description=payload.description,
            attributes=payload.attributes,
            reason=payload.reason,
        )
        return {"part_number": part.part_number}
    if conf.action == "create_revision":
        part = get_part_by_number(db, payload.part_number)
        rev = part_service.create_revision(
            db, user=user, part=part, change_reason=payload.change_reason
        )
        return {"part_number": part.part_number, "revision": rev.revision}
    if conf.action == "transition_revision":
        rev = get_revision_or_404(db, uuid.UUID(payload.revision_id))
        rev = part_service.transition_revision(
            db, user=user, revision=rev, to_status=payload.to_status, reason=payload.reason
        )
        return {"revision_id": str(rev.id), "status": rev.status}
    if conf.action == "create_document":
        from app.services import document_service

        doc = document_service.create_document(
            db, user=user, title=payload.title, doc_type=payload.doc_type, reason=payload.reason
        )
        return {"doc_number": doc.doc_number}
    if conf.action == "create_doc_revision":
        from app.services import document_service

        doc = document_service.get_document(db, payload.doc_number)
        rev = document_service.create_doc_revision(
            db, user=user, doc=doc, change_reason=payload.change_reason
        )
        return {"doc_number": doc.doc_number, "revision": rev.revision}
    if conf.action == "link_document":
        from app.services import document_service

        doc = document_service.get_document(db, payload.doc_number)
        link = document_service.link_document(
            db, user=user, doc=doc, part_number=payload.part_number, link_type=payload.link_type
        )
        return {"link_id": str(link.id)}
    if conf.action == "transition_doc_revision":
        from app.models.document import DocRevision
        from app.services import document_service

        rev = db.get(DocRevision, uuid.UUID(payload.revision_id))
        if rev is None:
            raise NotFoundError(
                f"doc revision {payload.revision_id} not found", code="revision_not_found"
            )
        rev = document_service.transition_doc_revision(
            db, user=user, rev=rev, to_status=payload.to_status, reason=payload.reason
        )
        return {"revision_id": str(rev.id), "status": rev.status}
    if conf.action == "add_bom_item":
        parent_rev = get_revision_or_404(db, uuid.UUID(payload.parent_rev_id))
        component_rev = resolve_component_revision(
            db, payload.component_part_number, payload.component_revision
        )
        item = add_bom_item(
            db,
            parent_rev=parent_rev,
            component_rev=component_rev,
            quantity=payload.quantity,
            unit=payload.unit,
            position=payload.position,
        )
        db.commit()
        return {"bom_item_id": str(item.id)}
    if conf.action == "create_ecr":
        from app.services import change_service

        ecr = change_service.create_ecr(
            db, user=user, description=payload.description, reason=payload.reason
        )
        return {"ecr_number": ecr.number}
    if conf.action == "transition_ecr":
        from app.services import change_service

        ecr = change_service.get_ecr_by_number(db, payload.ecr_number)
        ecr = change_service.transition_ecr(
            db, user=user, ecr=ecr, to_status=payload.to_status, reason=payload.reason
        )
        return {"ecr_number": ecr.number, "status": ecr.status}
    if conf.action == "create_eco":
        from app.services import change_service

        ecr = change_service.get_ecr_by_number(db, payload.ecr_number)
        eco = change_service.create_eco(db, user=user, ecr=ecr, reason=payload.reason)
        return {"eco_number": eco.number}
    if conf.action == "transition_eco":
        from app.services import change_service

        eco = change_service.get_eco_by_number(db, payload.eco_number)
        eco, created = change_service.transition_eco(
            db, user=user, eco=eco, to_status=payload.to_status, reason=payload.reason
        )
        return {"eco_number": eco.number, "status": eco.status, "created_revisions": created}
    if conf.action == "eco_add_affected":
        from app.services import change_service

        eco = change_service.get_eco_by_number(db, payload.eco_number)
        rev = change_service.add_affected_revision(
            db,
            user=user,
            eco=eco,
            part_number=payload.part_number,
            revision=payload.revision,
            reason=payload.reason,
        )
        return {
            "eco_number": eco.number,
            "revision_id": str(rev.id),
            "part_number": payload.part_number,
        }
    if conf.action == "create_report":
        from app.services import report_service

        row = report_service.create_report_for(
            db, user=user, template=payload.template, payload=payload
        )
        return {"report_id": row.report_id, "template": row.template}
    if conf.action == "update_revision_attributes":
        rev = get_revision_or_404(db, payload.revision_id)
        rev = part_service.update_revision_attributes(
            db, user=user, rev=rev, attributes=payload.attributes, reason=payload.reason
        )
        return {"part_number": rev.part.part_number, "revision": rev.revision}
    raise ValidationError(f"unknown confirmation action '{conf.action}'", code="unknown_action")


def resolve(db: Session, *, user: User, confirmation_id: uuid.UUID, approve: bool) -> Confirmation:
    conf = get_confirmation(db, confirmation_id)
    if conf.status != "proposed":
        raise ConflictError(
            f"confirmation is already '{conf.status}'", code="confirmation_resolved"
        )
    if _as_utc(conf.expires_at) < datetime.now(UTC):
        conf.status = "expired"
        db.commit()
        raise ConflictError("confirmation expired", code="confirmation_expired")
    if not approve:
        conf.status = "rejected"
        conf.resolved_by = user.id
        conf.resolved_at = datetime.now(UTC)
        db.commit()
        db.refresh(conf)
        return conf
    result = _execute(db, user, conf)
    conf.status = "executed"
    conf.resolved_by = user.id
    conf.resolved_at = datetime.now(UTC)
    conf.payload = {**conf.payload, "_result": result}
    db.commit()
    db.refresh(conf)
    return conf
