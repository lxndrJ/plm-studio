import os
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models.document import DocFile, DocLink, DocRevision, Document
from app.models.part import Part
from app.models.user import User
from app.services import audit as audit_service
from app.services.numbering import allocate_number, next_revision_label
from app.services.preview_service import enqueue_preview_job
from app.services.storage import storage_dir


def create_document(
    db: Session,
    *,
    user: User,
    title: str,
    doc_type: str,
    reason: str | None = None,
) -> Document:
    doc_number = allocate_number(db, "DOC")
    doc = Document(doc_number=doc_number, doc_type=doc_type, title=title)
    db.add(doc)
    db.flush()
    rev = DocRevision(
        document_id=doc.id,
        revision="01",
        status="draft",
        change_reason=reason or "initial revision",
    )
    db.add(rev)
    audit_service.log_change(
        db,
        entity_type="document",
        entity_id=doc.id,
        action="create",
        user_id=user.id,
        new_values={"doc_number": doc_number, "title": title, "doc_type": doc_type},
        reason=reason,
    )
    db.commit()
    db.refresh(doc)
    return doc


def get_document(db: Session, doc_number: str) -> Document:
    doc = db.execute(select(Document).where(Document.doc_number == doc_number)).scalar_one_or_none()
    if doc is None:
        raise NotFoundError(f"document '{doc_number}' not found", code="document_not_found")
    return doc


def list_documents(db: Session, query: str | None = None, limit: int = 50) -> list[Document]:
    stmt = select(Document).order_by(Document.doc_number).limit(limit)
    if query:
        like = f"%{query}%"
        stmt = stmt.where((Document.doc_number.ilike(like)) | (Document.title.ilike(like)))
    return list(db.execute(stmt).scalars())


def get_revision(db: Session, doc: Document, revision: str) -> DocRevision:
    rev = db.execute(
        select(DocRevision).where(DocRevision.document_id == doc.id, DocRevision.revision == revision)
    ).scalar_one_or_none()
    if rev is None:
        raise NotFoundError(
            f"revision '{revision}' of document '{doc.doc_number}' not found", code="revision_not_found"
        )
    return rev


def latest_revision(db: Session, doc_id) -> DocRevision | None:
    return db.execute(
        select(DocRevision).where(DocRevision.document_id == doc_id).order_by(DocRevision.revision.desc()).limit(1)
    ).scalar_one_or_none()


def create_doc_revision(db: Session, *, user: User, doc: Document, change_reason: str) -> DocRevision:
    label = next_revision_label(db, doc.id)
    previous = latest_revision(db, doc.id)
    rev = DocRevision(document_id=doc.id, revision=label, status="draft", change_reason=change_reason)
    db.add(rev)
    db.flush()
    if previous is not None:
        # carry files over to the new revision (same storage keys, new rows);
        # derivatives are regenerated via fresh preview jobs
        for f in db.execute(select(DocFile).where(DocFile.doc_rev_id == previous.id)).scalars():
            new_file = DocFile(
                doc_rev_id=rev.id,
                filename=f.filename,
                storage_key=f.storage_key,
                mime_type=f.mime_type,
                is_original=f.is_original,
                preview_file_id=None,
            )
            db.add(new_file)
            db.flush()
            if f.is_original:
                enqueue_preview_job(db, new_file)
    audit_service.log_change(
        db,
        entity_type="doc_revision",
        entity_id=rev.id,
        action="create",
        user_id=user.id,
        new_values={"doc_number": doc.doc_number, "revision": rev.revision, "status": rev.status},
        reason=change_reason,
    )
    db.commit()
    db.refresh(rev)
    return rev


def link_document(db: Session, *, user: User, doc: Document, part_number: str, link_type: str) -> DocLink:
    part = db.execute(select(Part).where(Part.part_number == part_number)).scalar_one_or_none()
    if part is None:
        raise NotFoundError(f"part '{part_number}' not found", code="part_not_found")
    existing = db.execute(
        select(DocLink).where(DocLink.document_id == doc.id, DocLink.part_id == part.id, DocLink.link_type == link_type)
    ).scalar_one_or_none()
    if existing:
        raise ConflictError("link already exists", code="link_exists")
    link = DocLink(document_id=doc.id, part_id=part.id, link_type=link_type)
    db.add(link)
    audit_service.log_change(
        db,
        entity_type="doc_link",
        entity_id=link.id,
        action="create",
        user_id=user.id,
        new_values={"doc_number": doc.doc_number, "part_number": part_number, "link_type": link_type},
    )
    db.commit()
    db.refresh(link)
    return link


def upload_file(
    db: Session,
    *,
    user: User,
    doc: Document,
    revision: str,
    filename: str,
    content: bytes,
    mime_type: str,
) -> DocFile:
    rev = get_revision(db, doc, revision)
    if rev.status == "released":
        raise ConflictError(
            "files of a released doc revision are immutable; create a new revision first",
            code="released_immutable",
        )
    file_id = uuid.uuid4()
    rel_key = f"{doc.id}/{file_id}_{os.path.basename(filename)}"
    target = storage_dir() / rel_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    doc_file = DocFile(
        doc_rev_id=rev.id,
        filename=os.path.basename(filename),
        storage_key=rel_key,
        mime_type=mime_type,
        is_original=True,
    )
    db.add(doc_file)
    db.flush()
    enqueue_preview_job(db, doc_file)
    audit_service.log_change(
        db,
        entity_type="doc_file",
        entity_id=doc_file.id,
        action="upload",
        user_id=user.id,
        new_values={
            "doc_number": doc.doc_number,
            "revision": revision,
            "filename": doc_file.filename,
            "mime_type": mime_type,
            "bytes": len(content),
        },
    )
    db.commit()
    db.refresh(doc_file)
    return doc_file


def get_file(db: Session, file_id) -> DocFile:
    f = db.get(DocFile, file_id)
    if f is None:
        raise NotFoundError(f"doc file {file_id} not found", code="doc_file_not_found")
    return f


def transition_doc_revision(db: Session, *, user: User, rev: DocRevision, to_status: str, reason: str) -> DocRevision:
    from app.services.workflow import assert_transition_allowed

    assert_transition_allowed(
        db,
        entity_type="doc_revision",
        from_status=rev.status,
        to_status=to_status,
        user_role=user.role,
    )
    old = {"status": rev.status}
    rev.status = to_status
    audit_service.log_change(
        db,
        entity_type="doc_revision",
        entity_id=rev.id,
        action="transition",
        user_id=user.id,
        old_values=old,
        new_values={"status": to_status},
        reason=reason,
    )
    db.commit()
    db.refresh(rev)
    return rev
