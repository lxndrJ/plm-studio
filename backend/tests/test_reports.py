import pytest

from tests.conftest import create_part


@pytest.fixture()
def fake_typst(tmp_path, monkeypatch):
    script = tmp_path / "typst"
    script.write_text('#!/bin/sh\nprintf "%%PDF-1.4 fake-typst" > "$3"\n')
    script.chmod(0o755)
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "TYPST_BINARY", str(script))
    return script


def _rev_id(client, headers, part_number, revision="01"):
    r = client.get(f"/api/v1/parts/{part_number}", headers=headers)
    for rev in r.json()["revisions"]:
        if rev["revision"] == revision:
            return rev["id"]
    raise AssertionError(f"revision {revision} not found")


def _release(client, editor, approver, part_number):
    rev = _rev_id(client, editor, part_number)
    for to, h in (("review", editor), ("released", approver)):
        r = client.post(
            f"/api/v1/revisions/{rev}/transition?direct=true",
            json={"to_status": to, "reason": "freigeben"},
            headers=h,
        )
        assert r.status_code == 200, r.text


def test_create_part_report_uses_only_released_content(client, editor, approver, fake_typst, admin):
    part = create_part(
        client,
        editor,
        "Reportteil",
        attributes={"material": "Alu", "preis": 9.99, "lieferant": "ACME GmbH"},
    )
    _release(client, editor, approver, part["part_number"])

    r = client.post(
        f"/api/v1/reports/parts/{part['part_number']}?direct=true",
        json={"reason": "externes Datenblatt"},
        headers=editor,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["report_id"] == "RPT-00001"
    assert body["template"] == "part_sheet_v1"
    snap = body["content_snapshot"]
    assert snap["part"]["part_number"] == part["part_number"]
    assert snap["revision"]["status"] == "released"
    assert snap["revision"]["attributes"]["material"] == "Alu"
    assert "preis" not in snap["revision"]["attributes"]
    assert "lieferant" not in snap["revision"]["attributes"]
    assert body["pdf_available"] is True

    r = client.get(f"/api/v1/reports/{body['report_id']}/download", headers=editor)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content.startswith(b"%PDF")

    log = client.get("/api/v1/admin/audit-log", headers=admin).json()
    report_entries = [e for e in log if e["entity_type"] == "report" and e["action"] == "create"]
    assert len(report_entries) == 1
    assert report_entries[0]["new_values"]["report_id"] == "RPT-00001"


def test_report_requires_released_revision(client, editor, fake_typst):
    part = create_part(client, editor, "Noch nicht freigegeben")
    r = client.post(
        f"/api/v1/reports/parts/{part['part_number']}?direct=true",
        json={},
        headers=editor,
    )
    assert r.status_code == 409
    assert r.json()["code"] == "no_released_revision"
    assert client.get("/api/v1/reports", headers=editor).json() == []


def test_report_contains_bom_of_released_revision(client, editor, approver, fake_typst):
    asm = create_part(client, editor, "Report-BG", part_type="assembly")
    comp = create_part(client, editor, "Report-Komponente")
    rev = _rev_id(client, editor, asm["part_number"])
    r = client.post(
        "/api/v1/bom/items",
        params={"parent_rev_id": rev, "direct": "true"},
        json={
            "component_part_number": comp["part_number"],
            "quantity": 3,
            "unit": "Stk",
            "position": 1,
        },
        headers=editor,
    )
    assert r.status_code == 201, r.text
    _release(client, editor, approver, asm["part_number"])

    r = client.post(
        f"/api/v1/reports/parts/{asm['part_number']}?direct=true", json={}, headers=editor
    )
    assert r.status_code == 201, r.text
    bom = r.json()["content_snapshot"]["bom"]
    assert len(bom) == 1
    assert bom[0]["component_part_number"] == comp["part_number"]
    assert bom[0]["component_name"] == "Report-Komponente"
    assert bom[0]["quantity"] == 3.0
    assert bom[0]["unit"] == "Stk"


def test_report_via_confirmation_token(client, editor, approver, fake_typst):
    part = create_part(client, editor, "Token-Report-Teil")
    _release(client, editor, approver, part["part_number"])
    r = client.post(
        f"/api/v1/reports/parts/{part['part_number']}",
        json={"reason": "agent moechte Datenblatt"},
        headers=editor,
    )
    assert r.status_code == 202, r.text
    conf_id = r.json()["confirmation_id"]
    assert client.get("/api/v1/reports", headers=editor).json() == []

    r = client.post(f"/api/v1/confirmations/{conf_id}/approve", headers=editor)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "executed"
    reports = client.get("/api/v1/reports", headers=editor).json()
    assert len(reports) == 1
    assert reports[0]["report_id"] == "RPT-00001"


def test_list_get_and_404(client, editor, approver, fake_typst):
    r = client.get("/api/v1/reports/NOPE-1", headers=editor)
    assert r.status_code == 404
    assert r.json()["code"] == "report_not_found"

    part = create_part(client, editor, "Liste-Teil")
    _release(client, editor, approver, part["part_number"])
    r = client.post(
        f"/api/v1/reports/parts/{part['part_number']}?direct=true", json={}, headers=editor
    )
    assert r.status_code == 201, r.text
    r = client.get("/api/v1/reports", headers=editor)
    assert len(r.json()) == 1
    detail = client.get("/api/v1/reports/RPT-00001", headers=editor)
    assert detail.status_code == 200
    assert detail.json()["content_snapshot"]["part"]["part_number"] == part["part_number"]


def test_viewer_can_read_but_not_create(client, editor, approver, viewer, fake_typst):
    part = create_part(client, editor, "Viewer-Teil")
    _release(client, editor, approver, part["part_number"])
    r = client.post(
        f"/api/v1/reports/parts/{part['part_number']}?direct=true", json={}, headers=viewer
    )
    assert r.status_code == 403
    client.post(f"/api/v1/reports/parts/{part['part_number']}?direct=true", json={}, headers=editor)
    assert len(client.get("/api/v1/reports", headers=viewer).json()) == 1


def test_report_uses_latest_released_revision(client, editor, approver, fake_typst):
    part = create_part(client, editor, "Multi-Rev-Teil")
    _release(client, editor, approver, part["part_number"])
    r = client.post(
        f"/api/v1/parts/{part['part_number']}/revisions?direct=true",
        json={"change_reason": "update"},
        headers=editor,
    )
    assert r.status_code == 201
    rev2 = _rev_id(client, editor, part["part_number"], "02")
    for to, h in (("review", editor), ("released", approver)):
        r = client.post(
            f"/api/v1/revisions/{rev2}/transition?direct=true",
            json={"to_status": to, "reason": "rev 02 freigeben"},
            headers=h,
        )
        assert r.status_code == 200, r.text
    r = client.post(
        f"/api/v1/reports/parts/{part['part_number']}?direct=true", json={}, headers=editor
    )
    assert r.status_code == 201, r.text
    assert r.json()["content_snapshot"]["revision"]["revision"] == "02"
    assert r.json()["content_snapshot"]["revision"]["status"] == "released"


def test_download_missing_pdf_is_404(client, editor, approver, fake_typst):
    from app.services import report_service

    part = create_part(client, editor, "PDF-weg-Teil")
    _release(client, editor, approver, part["part_number"])
    r = client.post(
        f"/api/v1/reports/parts/{part['part_number']}?direct=true", json={}, headers=editor
    )
    assert r.status_code == 201
    report_id = r.json()["report_id"]
    assert report_service.pdf_path(report_id).exists()
    report_service.pdf_path(report_id).unlink()
    r = client.get(f"/api/v1/reports/{report_id}/download", headers=editor)
    assert r.status_code == 404
    assert r.json()["code"] == "report_file_missing"


def test_renderer_unavailable_is_503_and_creates_no_report(client, editor, approver, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "TYPST_BINARY", "/nonexistent/typst")
    part = create_part(client, editor, "Renderer-kaputt-Teil")
    _release(client, editor, approver, part["part_number"])
    r = client.post(
        f"/api/v1/reports/parts/{part['part_number']}?direct=true", json={}, headers=editor
    )
    assert r.status_code == 503
    assert r.json()["code"] == "renderer_unavailable"
    assert client.get("/api/v1/reports", headers=editor).json() == []
