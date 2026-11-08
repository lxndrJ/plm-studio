from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.core.security import SYSTEM_USER_ID
from app.models import AuditLog, NumberRange, Part, PartClass, PartRevision
from app.schemas.part import PartCreate, PartRead
from app.services.numbering import next_number

router = APIRouter(prefix="/api/v1/parts")


@router.get("")
def list_parts(
    query: str | None = None,
    session: Session = Depends(get_session),
) -> list[dict[str, str]]:
    stmt = select(Part)
    if query:
        like = f"%{query.lower()}%"
        stmt = stmt.where(func.lower(Part.name).like(like))
    parts = session.execute(stmt.limit(50)).scalars().all()
    return [
        {"part_number": p.part_number, "name": p.name, "part_type": p.part_type}
        for p in parts
    ]


@router.post("", status_code=201, response_model=PartRead)
def create_part(
    payload: PartCreate, session: Session = Depends(get_session)
) -> PartRead:
    # Regel: Klassifizierung ist Pflicht
    part_class = session.execute(
        select(PartClass).where(PartClass.code == payload.class_code)
    ).scalar_one_or_none()
    if part_class is None:
        raise HTTPException(404, f"unbekannte Klasse: {payload.class_code}")

    # Regel: Duplikatpruefung vor dem Anlegen (409 = Stopp-Signal)
    duplicates = (
        session.execute(
            select(Part).where(func.lower(Part.name) == payload.name.lower())
        )
        .scalars()
        .all()
    )
    if duplicates:
        hits = ", ".join(d.part_number for d in duplicates)
        raise HTTPException(409, f"moeglicherweise existierende Artikel: {hits}")

    # Nummer kommt ausschliesslich vom Generator
    part_number = next_number(session, "ASM-" if payload.part_type == "assembly" else "P-")

    part = Part(
        part_number=part_number,
        name=payload.name,
        description=payload.description,
        part_type=payload.part_type,
        class_id=part_class.id,
        attributes=payload.attributes,
    )
    session.add(part)
    session.flush()

    revision = PartRevision(
        part_id=part.id,
        revision="01",
        status="draft",
        change_reason=payload.reason or "Neuanlage",
        created_by=UUID(SYSTEM_USER_ID),
    )
    session.add(revision)

    session.add(
        AuditLog(
            entity_type="part",
            entity_id=part.id,
            action="create",
            new_values={"part_number": part_number, "revision": "01"},
            reason=payload.reason or "Neuanlage Artikel",
            user_id=UUID(SYSTEM_USER_ID),
        )
    )
    session.commit()

    return PartRead(
        part_number=part_number,
        name=part.name,
        revision="01",
        status="draft",
        class_code=part_class.code,
    )
