import shutil
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.models.document import DocFile
from app.models.preview import PreviewJob
from app.services.storage import file_path, storage_dir

# served directly by the browser, no derivative needed
NATIVE_MIMES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/svg+xml",
    "application/pdf",
}

THUMB_SIZE = 512


def enqueue_preview_job(db: Session, doc_file: DocFile) -> PreviewJob | None:
    if doc_file.mime_type in ("image/svg+xml", "application/pdf"):
        return None  # browser-native, nothing to generate
    job = PreviewJob(doc_file_id=doc_file.id, status="queued")
    db.add(job)
    db.flush()
    return job


def claim_next_job(db: Session) -> PreviewJob | None:
    job = db.execute(
        select(PreviewJob).where(PreviewJob.status == "queued").order_by(PreviewJob.created_at).limit(1)
    ).scalar_one_or_none()
    if job is None:
        return None
    job.status = "processing"
    db.flush()
    return job


def _save_derivative(db: Session, original: DocFile, content: bytes, mime: str, ext: str) -> DocFile:
    file_id = uuid.uuid4()
    rel_key = f"{original.doc_rev_id}/{file_id}_preview.{ext}"
    target = storage_dir() / rel_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    derivative = DocFile(
        doc_rev_id=original.doc_rev_id,
        filename=f"{original.filename}_preview.{ext}",
        storage_key=rel_key,
        mime_type=mime,
        is_original=False,
        preview_file_id=original.id,
    )
    db.add(derivative)
    db.flush()
    original.preview_file_id = derivative.id
    return derivative


def _generate(db: Session, job: PreviewJob) -> None:
    original = db.get(DocFile, job.doc_file_id)
    if original is None:
        job.status = "failed"
        job.error = "original file missing"
        return
    src = file_path(original)
    if original.mime_type in NATIVE_MIMES and not original.mime_type.startswith("image/"):
        job.status = "done"  # browser-native, no derivative
        return
    if original.mime_type.startswith("image/"):
        from io import BytesIO

        from PIL import Image

        with Image.open(src) as img:
            img.thumbnail((THUMB_SIZE, THUMB_SIZE))
            buf = BytesIO()
            img.convert("RGB").save(buf, format="PNG")
        _save_derivative(db, original, buf.getvalue(), "image/png", "png")
        job.status = "done"
        return
    # AI/EPS/PSD and other formats: convert via Inkscape headless or Ghostscript
    if original.mime_type in ("application/postscript", "image/vnd.adobe.illustrator") and shutil.which("inkscape"):
        import subprocess

        out = storage_dir() / f"{uuid.uuid4()}_preview.png"
        subprocess.run(
            ["inkscape", str(src), "--export-type=png", f"--export-filename={out}"],
            check=True,
            capture_output=True,
        )
        _save_derivative(db, original, out.read_bytes(), "image/png", "png")
        out.unlink()
        job.status = "done"
        return
    if shutil.which("gs"):
        import subprocess

        out = storage_dir() / f"{uuid.uuid4()}_preview.png"
        subprocess.run(
            ["gs", "-dSAFER", "-dBATCH", "-dNOPAUSE", "-sDEVICE=png16m", f"-sOutputFile={out}", str(src)],
            check=True,
            capture_output=True,
        )
        _save_derivative(db, original, out.read_bytes(), "image/png", "png")
        out.unlink()
        job.status = "done"
        return
    job.status = "failed"
    job.error = f"no converter available for {original.mime_type} (need inkscape or ghostscript)"


def process_next_job(db: Session) -> PreviewJob | None:
    job = claim_next_job(db)
    if job is None:
        return None
    try:
        _generate(db, job)
    except Exception as exc:  # noqa: BLE001 - a failing converter must not kill the worker loop
        job.status = "failed"
        job.error = str(exc)[:500]
    job.processed_at = datetime.now(UTC)
    db.commit()
    return job


def preview_target(db: Session, doc_file: DocFile) -> DocFile:
    """The file to serve as preview: derivative if present, original if
    browser-native, else ConflictError (pending/failed)."""
    if doc_file.preview_file_id is not None:
        derivative = db.get(DocFile, doc_file.preview_file_id)
        if derivative is not None:
            return derivative
    if doc_file.mime_type in NATIVE_MIMES:
        return doc_file
    job = db.execute(
        select(PreviewJob).where(PreviewJob.doc_file_id == doc_file.id).order_by(PreviewJob.id.desc()).limit(1)
    ).scalar_one_or_none()
    state = job.status if job else "none"
    raise ConflictError(
        f"no preview available for {doc_file.filename} ({doc_file.mime_type}); job state: {state}",
        code="preview_not_ready",
    )
