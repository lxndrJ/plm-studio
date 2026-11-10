"""M11 backend: list pagination/filters, CSV/JSON export, revision attribute
updates, BOM-explosion + ECR reports, class attribute definitions, stats auth."""

import csv
import io
import json

import pytest

from app.core.config import get_settings
from tests.conftest import create_part, release_part


@pytest.fixture()
def fake_typst(tmp_path, monkeypatch):
    script = tmp_path / "typst"
    script.write_text('#!/bin/sh\nprintf "%%PDF-1.4 fake-typst" > "$3"\n')
    script.chmod(0o755)
    monkeypatch.setattr(get_settings(), "TYPST_BINARY", str(script))
    return script


# --- GET /parts: pagination + filters ---------------------------------------


def test_parts_pagination_and_headers(client, editor):
    for i in range(7):
        create_part(client, editor, f"Pag Teil {i}")
    r = client.get("/api/v1/parts?page=1&page_size=3", headers=editor)
    assert r.status_code == 200
    assert len(r.json()) == 3
    assert r.headers["x-total-count"] == "7"
    assert r.headers["x-page"] == "1"
    r2 = client.get("/api/v1/parts?page=3&page_size=3", headers=editor)
    assert len(r2.json()) == 1
    assert r2.json()[0]["part_number"] != r.json()[0]["part_number"]


def test_parts_filter_by_type_and_status(client, editor, approver):
    create_part(client, editor, "Normteil", part_type="part")
    asm = create_part(client, editor, "Baugruppe", part_type="assembly")
    release_part(client, editor, approver, asm["part_number"])

    r = client.get("/api/v1/parts?part_type=assembly", headers=editor)
    assert [p["name"] for p in r.json()] == ["Baugruppe"]
    r = client.get("/api/v1/parts?part_type=part", headers=editor)
    assert [p["name"] for p in r.json()] == ["Normteil"]
    r = client.get("/api/v1/parts?status=released", headers=editor)
    assert [p["part_number"] for p in r.json()] == [asm["part_number"]]
    r = client.get("/api/v1/parts?status=draft", headers=editor)
    assert all(p["part_number"] != asm["part_number"] for p in r.json())
    r = client.get("/api/v1/parts?query=Baugruppe", headers=editor)
    assert [p["name"] for p in r.json()] == ["Baugruppe"]


# --- export -------------------------------------------------------------------


def test_export_parts_csv_and_json(client, editor, approver):
    part = create_part(client, editor, "Exportteil", attributes={"material": "Alu", "weight_kg": 2})
    release_part(client, editor, approver, part["part_number"])

    r = client.get("/api/v1/export/parts?format=csv", headers=editor)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(r.text)))
    row = next(x for x in rows if x["part_number"] == part["part_number"])
    assert row["name"] == "Exportteil"
    assert row["status"] == "released"
    assert row["revision"] == "01"
    assert json.loads(row["attributes"])["material"] == "Alu"

    r = client.get("/api/v1/export/parts?format=json", headers=editor)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    row = next(x for x in data if x["part_number"] == part["part_number"])
    assert row["attributes"]["weight_kg"] == 2

    r = client.get("/api/v1/export/parts?format=xml", headers=editor)
    assert r.status_code == 422
    r = client.get("/api/v1/export/parts")
    assert r.status_code == 401


def test_export_bom_csv_and_json(client, editor):
    asm = create_part(client, editor, "Export-Baugruppe", part_type="assembly")
    comp = create_part(client, editor, "Export-Komponente")
    revs = client.get(f"/api/v1/parts/{asm['part_number']}/revisions", headers=editor).json()
    rev01 = next(x for x in revs if x["revision"] == "01")
    r = client.post(
        "/api/v1/bom/items",
        params={"parent_rev_id": rev01["id"], "direct": "true"},
        json={
            "component_part_number": comp["part_number"],
            "component_revision": "01",
            "quantity": 3,
            "unit": "Stk",
            "position": 1,
        },
        headers=editor,
    )
    assert r.status_code == 201, r.text

    r = client.get(f"/api/v1/export/bom/{asm['part_number']}?rev=01&format=csv", headers=editor)
    assert r.status_code == 200
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert len(rows) == 1
    assert rows[0]["component_part_number"] == comp["part_number"]
    assert rows[0]["quantity"] == "3"
    assert rows[0]["unit"] == "Stk"

    r = client.get(f"/api/v1/export/bom/{asm['part_number']}?format=json", headers=editor)
    assert r.status_code == 200
    assert r.json()["items"][0]["component_part_number"] == comp["part_number"]


# --- PATCH attributes on a draft revision --------------------------------------


def test_update_attributes_draft_only_and_validated(client, editor, approver, admin):
    part = create_part(client, editor, "Attr-Teil")
    revs = client.get(f"/api/v1/parts/{part['part_number']}/revisions", headers=editor).json()
    rev_id = revs[0]["id"]

    r = client.patch(
        f"/api/v1/parts/{part['part_number']}/revisions/{rev_id}/attributes?direct=true",
        json={"attributes": {"material": "Stahl", "weight_kg": 1.2}, "reason": "Initiale Werte"},
        headers=editor,
    )
    assert r.status_code == 200, r.text
    assert r.json()["attributes"]["material"] == "Stahl"

    # type validation against the class definition (weight_kg must be a number)
    r = client.patch(
        f"/api/v1/parts/{part['part_number']}/revisions/{rev_id}/attributes?direct=true",
        json={"attributes": {"weight_kg": "viel"}},
        headers=editor,
    )
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_attributes"

    # released revision is immutable
    release_part(client, editor, approver, part["part_number"])
    r = client.patch(
        f"/api/v1/parts/{part['part_number']}/revisions/{rev_id}/attributes?direct=true",
        json={"attributes": {"material": "Alu"}},
        headers=editor,
    )
    assert r.status_code == 409
    assert r.json()["code"] == "released_immutable"

    # audit entry
    log = client.get("/api/v1/admin/audit-log", headers=admin).json()
    entries = [
        e for e in log if e["entity_type"] == "part_revision" and e["action"] == "update_attributes"
    ]
    assert len(entries) == 1
    assert entries[0]["old_values"] == {}
    assert entries[0]["new_values"]["material"] == "Stahl"


def test_update_attributes_via_confirmation(client, editor, approver):
    part = create_part(client, editor, "Attr-Conf-Teil")
    rev_id = client.get(f"/api/v1/parts/{part['part_number']}/revisions", headers=editor).json()[0][
        "id"
    ]
    r = client.patch(
        f"/api/v1/parts/{part['part_number']}/revisions/{rev_id}/attributes",
        json={"attributes": {"material": "Kunststoff"}},
        headers=editor,
    )
    assert r.status_code == 202
    conf_id = r.json()["confirmation_id"]
    r = client.post(f"/api/v1/confirmations/{conf_id}/approve", headers=approver)
    assert r.status_code == 200, r.text
    rev = client.get(f"/api/v1/revisions/{rev_id}", headers=editor).json()
    assert rev["attributes"]["material"] == "Kunststoff"


# --- reports: BOM explosion + ECR ----------------------------------------------


def _released_assembly_with_component(
    client, editor, approver, asm_name="Rep-BG", comp_name="Rep-Comp"
):
    asm = create_part(client, editor, asm_name, part_type="assembly")
    comp = create_part(client, editor, comp_name)
    revs = client.get(f"/api/v1/parts/{asm['part_number']}/revisions", headers=editor).json()
    rev01 = next(x for x in revs if x["revision"] == "01")
    client.post(
        "/api/v1/bom/items",
        params={"parent_rev_id": rev01["id"], "direct": "true"},
        json={
            "component_part_number": comp["part_number"],
            "component_revision": "01",
            "quantity": 2,
            "unit": "Stk",
            "position": 1,
        },
        headers=editor,
    )
    release_part(client, editor, approver, asm["part_number"])
    release_part(client, editor, approver, comp["part_number"])
    return asm, comp


def test_bom_explosion_report(client, editor, approver, fake_typst):
    asm, comp = _released_assembly_with_component(client, editor, approver)
    r = client.post(
        f"/api/v1/reports/parts/{asm['part_number']}/bom?direct=true",
        json={"reason": "Stueckliste"},
        headers=editor,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["template"] == "bom_explosion_v1"
    snap = body["content_snapshot"]
    assert snap["part"]["part_number"] == asm["part_number"]
    assert any(
        line["component_part_number"] == comp["part_number"] and line["level"] == 1
        for line in snap["lines"]
    )
    # download works (fake typst wrote a file)
    r = client.get(f"/api/v1/reports/{body['report_id']}/download", headers=editor)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_bom_report_requires_released(client, editor, fake_typst):
    part = create_part(client, editor, "Nicht freigegeben")
    r = client.post(
        f"/api/v1/reports/parts/{part['part_number']}/bom?direct=true",
        json={},
        headers=editor,
    )
    assert r.status_code == 409
    assert r.json()["code"] == "no_released_revision"


def test_ecr_report(client, editor, approver, fake_typst):
    from tests.test_changes import _approve_ecr, _create_eco, _create_ecr

    asm, _ = _released_assembly_with_component(client, editor, approver)
    ecr = _create_ecr(client, editor, description="Gehaeuse aendern")
    _approve_ecr(client, editor, approver, ecr["number"])
    eco = _create_eco(client, editor, ecr["number"])
    client.post(
        f"/api/v1/ecos/{eco['number']}/affected-revisions?direct=true",
        json={"part_number": asm["part_number"], "revision": "01"},
        headers=editor,
    )

    r = client.post(
        f"/api/v1/reports/ecrs/{ecr['number']}?direct=true",
        json={"reason": "Aenderungsbericht"},
        headers=approver,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["template"] == "ecr_v1"
    snap = body["content_snapshot"]
    assert snap["ecr"]["number"] == ecr["number"]
    assert snap["ecr"]["status"] == "approved"
    assert snap["ecos"][0]["number"] == eco["number"]
    assert snap["ecos"][0]["affected"][0]["part_number"] == asm["part_number"]

    # via confirmation token
    r = client.post(
        f"/api/v1/reports/ecrs/{ecr['number']}",
        json={"reason": "nochmal"},
        headers=approver,
    )
    assert r.status_code == 202
    r = client.post(
        f"/api/v1/confirmations/{r.json()['confirmation_id']}/approve", headers=approver
    )
    assert r.status_code == 200


def test_ecr_report_unknown_ecr_404(client, editor, fake_typst):
    r = client.post("/api/v1/reports/ecrs/ECR-99999?direct=true", json={}, headers=editor)
    assert r.status_code == 404


# --- class attribute definitions for the UI -------------------------------------


def test_part_classes_include_typed_attributes(client, editor):
    r = client.get("/api/v1/admin/part-classes", headers=editor)
    assert r.status_code == 200
    mech = next(c for c in r.json() if c["code"] == "MECH")
    attrs = {a["key"]: a for a in mech["attributes"]}
    assert attrs["material"]["attr_type"] == "string"
    assert attrs["weight_kg"]["attr_type"] == "number"
    assert attrs["weight_kg"]["unit_code"] == "kg"
    elec = next(c for c in r.json() if c["code"] == "ELEC")
    ip = next(a for a in elec["attributes"] if a["key"] == "ip_rating")
    assert ip["attr_type"] == "enum"
    assert "IP65" in ip["allowed_values"]


def test_stats_requires_auth(client):
    r = client.get("/api/v1/admin/stats")
    assert r.status_code == 401
