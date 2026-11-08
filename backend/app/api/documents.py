import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.core.deps import CurrentUser, DbSession
from app.guardrails import confirmations as conf_guard
from app.guardrails.permissions import require_editor
from app.models.document import DocFile
from app.models.user import User
from app.schemas.confirmation import ConfirmationProposed
from app.schemas.document import (
    DocFileResponse,
    DocLinkCreate,
    DocLinkResponse,
    DocRevisionCreate,
    DocRevisionResponse,
    DocTransitionRequest,
    DocumentCreate,
    DocumentResponse,
    DocumentSummary,
)
from app.services import document_service, preview_service
from app.services.storage import file_path

router = APIRouter(tags=["documents"])


def _file_response(db: DbSession, f: DocFile) -> "DocFileResponse":
    from app.schemas.document import DocFileResponse

    return DocFileResponse(
        id=f.id,
        filename=f.filename,
        mime_type=f.mime_type,
        is_original=f.is_original,
        preview_file_id=f.preview_file_id,
        has_derivative=f.preview_file_id is not None,
    )


@router.get("/documents", response_model=list[DocumentSummary])
def list_documents(db: DbSession, user: CurrentUser, query: Annotated[str | None, Query()] = None):
    return document_service.list_documents(db, query=query)


@router.post("/documents", status_code=201)
def create_document(
    body: DocumentCreate,
    db: DbSession,
    user: Annotated[User, Depends(require_editor)],
    direct: Annotated[bool, Query()] = False,
):
    if not direct:
        conf = conf_guard.propose(
            db,
            user=user,
            action="create_document",
            payload={"title": body.title, "doc_type": body.doc_type, "reason": body.reason},
            summary=f"create document '{body.title}' (type={body.doc_type})",
        )
        return JSONResponse(
            status_code=202,
            content=ConfirmationProposed(confirmation_id=conf.id, summary=conf.summary).model_dump(mode="json"),
        )
    doc = document_service.create_document(db, user=user, title=body.title, doc_type=body.doc_type, reason=body.reason)
    return DocumentResponse.model_validate(doc)


@router.get("/documents/{doc_number}", response_model=DocumentResponse)
def get_document(doc_number: str, db: DbSession, user: CurrentUser):
    return DocumentResponse.model_validate(document_service.get_document(db, doc_number))


@router.post("/documents/{doc_number}/revisions", status_code=201)
def create_revision(
    doc_number: str,
    body: DocRevisionCreate,
    db: DbSession,
    user: Annotated[User, Depends(require_editor)],
    direct: Annotated[bool, Query()] = False,
):
    doc = document_service.get_document(db, doc_number)
    if not direct:
        conf = conf_guard.propose(
            db,
            user=user,
            action="create_doc_revision",
            payload={"doc_number": doc_number, "change_reason": body.change_reason},
            summary=f"create new revision of document '{doc_number}'",
        )
        return JSONResponse(
            status_code=202,
            content=ConfirmationProposed(confirmation_id=conf.id, summary=conf.summary).model_dump(mode="json"),
        )
    rev = document_service.create_doc_revision(db, user=user, doc=doc, change_reason=body.change_reason)
    return DocRevisionResponse.model_validate(rev)


@router.post("/documents/{doc_number}/links", status_code=201)
def link_document(
    doc_number: str,
    body: DocLinkCreate,
    db: DbSession,
    user: Annotated[User, Depends(require_editor)],
    direct: Annotated[bool, Query()] = False,
):
    doc = document_service.get_document(db, doc_number)
    if not direct:
        conf = conf_guard.propose(
            db,
            user=user,
            action="link_document",
            payload={"doc_number": doc_number, "part_number": body.part_number, "link_type": body.link_type},
            summary=f"link document '{doc_number}' to part '{body.part_number}' ({body.link_type})",
        )
        return JSONResponse(
            status_code=202,
            content=ConfirmationProposed(confirmation_id=conf.id, summary=conf.summary).model_dump(mode="json"),
        )
    link = document_service.link_document(db, user=user, doc=doc, part_number=body.part_number, link_type=body.link_type)
    return DocLinkResponse.model_validate(link)


@router.post("/documents/{doc_number}/revisions/{revision}/files", status_code=201)
async def upload_file(
    doc_number: str,
    revision: str,
    db: DbSession,
    user: Annotated[User, Depends(require_editor)],
    file: Annotated[UploadFile, File()],
):
    # uploads are direct-only (binary payload cannot ride a JSON confirmation);
    # the agent proposes metadata operations, the UI uploads files
    doc = document_service.get_document(db, doc_number)
    content = await file.read()
    doc_file = document_service.upload_file(
        db,
        user=user,
        doc=doc,
        revision=revision,
        filename=file.filename or "file",
        content=content,
        mime_type=file.content_type or "application/octet-stream",
    )
    return _file_response(db, doc_file)


@router.get("/doc-files/{file_id}/download")
def download_file(file_id: uuid.UUID, db: DbSession, user: CurrentUser):
    f = document_service.get_file(db, file_id)
    path = file_path(f)
    return FileResponse(path, media_type=f.mime_type, filename=f.filename)


@router.get("/doc-files/{file_id}/preview")
def preview_file(file_id: uuid.UUID, db: DbSession, user: CurrentUser):
    f = document_service.get_file(db, file_id)
    target = preview_service.preview_target(db, f)
    path = file_path(target)
    return FileResponse(path, media_type=target.mime_type, filename=target.filename)


@router.get("/doc-files/{file_id}", response_model=DocFileResponse)
def get_file(file_id: uuid.UUID, db: DbSession, user: CurrentUser):
    return _file_response(db, document_service.get_file(db, file_id))


@router.post("/doc-revisions/{revision_id}/transition")
def transition_doc_revision(
    revision_id: uuid.UUID,
    body: DocTransitionRequest,
    db: DbSession,
    user: Annotated[User, Depends(require_editor)],
    direct: Annotated[bool, Query()] = False,
):
    from app.core.errors import NotFoundError
    from app.models.document import DocRevision

    rev = db.get(DocRevision, revision_id)
    if rev is None:
        raise NotFoundError(f"doc revision {revision_id} not found", code="revision_not_found")
    if not direct:
        conf = conf_guard.propose(
            db,
            user=user,
            action="transition_doc_revision",
            payload={"revision_id": str(revision_id), "to_status": body.to_status, "reason": body.reason},
            summary=f"transition doc revision {revision_id}: '{rev.status}' -> '{body.to_status}'",
        )
        return JSONResponse(
            status_code=202,
            content=ConfirmationProposed(confirmation_id=conf.id, summary=conf.summary).model_dump(mode="json"),
        )
    rev = document_service.transition_doc_revision(db, user=user, rev=rev, to_status=body.to_status, reason=body.reason)
    return DocRevisionResponse.model_validate(rev)
