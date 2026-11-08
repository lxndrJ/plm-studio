import io

from PIL import Image

from app.services.preview_service import process_next_job
from tests.conftest import create_part


def _png_bytes(size=(64, 64), color=(200, 30, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _create_doc(client, headers, title="Drawing A", doc_type="vector"):
    r = client.post(
        "/api/v1/documents?direct=true",
        json={"title": title, "doc_type": doc_type},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def _upload(client, headers, doc_number, filename, content, mime, revision="01"):
    r = client.post(
        f"/api/v1/documents/{doc_number}/revisions/{revision}/files",
        files={"file": (filename, content, mime)},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_create_document_gets_number_and_initial_revision(client, editor):
    doc = _create_doc(client, editor)
    assert doc["doc_number"] == "DOC-000001"
    assert doc["revisions"][0]["revision"] == "01"
    assert doc["revisions"][0]["status"] == "draft"


def test_document_confirmation_flow(client, editor):
    r = client.post(
        "/api/v1/documents",
        json={"title": "Spec X", "doc_type": "report"},
        headers=editor,
    )
    assert r.status_code == 202
    conf_id = r.json()["confirmation_id"]
    assert client.get("/api/v1/documents?query=Spec", headers=editor).json() == []
    client.post(f"/api/v1/confirmations/{conf_id}/approve", headers=editor)
    docs = client.get("/api/v1/documents?query=Spec", headers=editor).json()
    assert len(docs) == 1
    assert docs[0]["doc_number"] == "DOC-000001"


def test_upload_and_download_original_byte_identical(client, editor, db):
    doc = _create_doc(client, editor, doc_type="raster")
    content = _png_bytes()
    f = _upload(client, editor, doc["doc_number"], "part.png", content, "image/png")
    assert f["is_original"] is True
    assert f["filename"] == "part.png"

    r = client.get(f"/api/v1/doc-files/{f['id']}/download", headers=editor)
    assert r.status_code == 200
    assert r.content == content  # original byte-identical


def test_image_preview_generates_derivative_without_manual_step(client, editor, db):
    """M4: JPG/PNG preview works without a manual step; original untouched."""
    doc = _create_doc(client, editor, doc_type="raster")
    content = _png_bytes(size=(1024, 1024))
    f = _upload(client, editor, doc["doc_number"], "big.png", content, "image/png")

    job = process_next_job(db)
    assert job is not None and job.status == "done"

    r = client.get(f"/api/v1/doc-files/{f['id']}/preview", headers=editor)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/png")
    # derivative is a thumbnail, original stays byte-identical
    assert len(r.content) != len(content)
    orig = client.get(f"/api/v1/doc-files/{f['id']}/download", headers=editor)
    assert orig.content == content

    meta = client.get(f"/api/v1/doc-files/{f['id']}", headers=editor).json()
    assert meta["has_derivative"] is True


def test_svg_preview_is_native_no_job_needed(client, editor, db):
    doc = _create_doc(client, editor, doc_type="vector")
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>'
    f = _upload(client, editor, doc["doc_number"], "logo.svg", svg, "image/svg+xml")
    r = client.get(f"/api/v1/doc-files/{f['id']}/preview", headers=editor)
    assert r.status_code == 200
    assert r.content == svg  # served natively
    assert process_next_job(db) is None  # no job was queued


def test_ai_upload_without_converter_fails_gracefully(client, editor, db):
    doc = _create_doc(client, editor, doc_type="vector")
    f = _upload(client, editor, doc["doc_number"], "logo.ai", b"%!PS-Adobe", "application/postscript")
    job = process_next_job(db)
    assert job.status in ("failed", "done")  # depends on converter availability
    if job.status == "failed":
        r = client.get(f"/api/v1/doc-files/{f['id']}/preview", headers=editor)
        assert r.status_code == 409
        assert r.json()["code"] == "preview_not_ready"


def test_original_file_is_immutable_via_api(client, editor):
    doc = _create_doc(client, editor, doc_type="raster")
    f = _upload(client, editor, doc["doc_number"], "part.png", _png_bytes(), "image/png")
    for method in ("put", "delete", "patch"):
        r = getattr(client, method)(f"/api/v1/doc-files/{f['id']}", headers=editor)
        assert r.status_code == 405


def test_upload_to_released_doc_revision_rejected(client, editor, approver):
    doc = _create_doc(client, editor)
    rev_id = doc["revisions"][0]["id"]
    client.post(
        f"/api/v1/doc-revisions/{rev_id}/transition?direct=true",
        json={"to_status": "review", "reason": "r"},
        headers=editor,
    )
    client.post(
        f"/api/v1/doc-revisions/{rev_id}/transition?direct=true",
        json={"to_status": "released", "reason": "r"},
        headers=approver,
    )
    r = client.post(
        f"/api/v1/documents/{doc['doc_number']}/revisions/01/files",
        files={"file": ("x.png", _png_bytes(), "image/png")},
        headers=editor,
    )
    assert r.status_code == 409
    assert r.json()["code"] == "released_immutable"


def test_invalid_doc_transition_is_422(client, editor):
    doc = _create_doc(client, editor)
    rev_id = doc["revisions"][0]["id"]
    r = client.post(
        f"/api/v1/doc-revisions/{rev_id}/transition?direct=true",
        json={"to_status": "released", "reason": "skip review"},
        headers=editor,
    )
    assert r.status_code == 422


def test_link_document_to_part(client, editor):
    part = create_part(client, editor, "Gehaeuse B")
    doc = _create_doc(client, editor)
    r = client.post(
        f"/api/v1/documents/{doc['doc_number']}/links?direct=true",
        json={"part_number": part["part_number"], "link_type": "referenced-by"},
        headers=editor,
    )
    assert r.status_code == 201
    detail = client.get(f"/api/v1/documents/{doc['doc_number']}", headers=editor).json()
    assert detail["links"][0]["part_id"] == part["id"]

    r2 = client.post(
        f"/api/v1/documents/{doc['doc_number']}/links?direct=true",
        json={"part_number": part["part_number"], "link_type": "referenced-by"},
        headers=editor,
    )
    assert r2.status_code == 409

    r3 = client.post(
        f"/api/v1/documents/{doc['doc_number']}/links?direct=true",
        json={"part_number": "P-999999", "link_type": "owned-by"},
        headers=editor,
    )
    assert r3.status_code == 404


def test_viewer_cannot_upload(client, editor, viewer):
    doc = _create_doc(client, editor, doc_type="raster")
    r = client.post(
        f"/api/v1/documents/{doc['doc_number']}/revisions/01/files",
        files={"file": ("x.png", _png_bytes(), "image/png")},
        headers=viewer,
    )
    assert r.status_code == 403


def test_document_actions_in_audit_log(client, editor, admin):
    doc = _create_doc(client, editor)
    _upload(client, editor, doc["doc_number"], "part.png", _png_bytes(), "image/png")
    log = client.get("/api/v1/admin/audit-log", headers=admin).json()
    actions = {(e["entity_type"], e["action"]) for e in log}
    assert ("document", "create") in actions
    assert ("doc_file", "upload") in actions
