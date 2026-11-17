"""M14: full-text search over parts/documents (Postgres FTS with SQLite ILIKE
fallback) + BOM-diff PDF report (bom_diff_v1) via the Typst engine."""

from tests.conftest import create_part, release_part
from tests.test_bom import _add_item, _rev_id

# --- search: parts ------------------------------------------------------------


def test_parts_search_matches_description_words(client, editor):
    create_part(
        client, editor, "Gehaeuse A", description="Gehaeuse aus Aluminium fuer die Hydraulik"
    )
    create_part(client, editor, "Gehaeuse B", description="Kunststoffspritzguss")

    def q(query):
        r = client.get("/api/v1/parts", params={"query": query}, headers=editor)
        assert r.status_code == 200, r.text
        return [p["name"] for p in r.json()]

    # single word from the description
    assert q("aluminium") == ["Gehaeuse A"]
    # multi-word: all words must match (FTS AND semantics)
    assert q("aluminium hydraulik") == ["Gehaeuse A"]
    assert q("aluminium kunststoff") == []
    # part number still searchable
    hits = q(create_part(client, editor, "Spezial", description=None)["part_number"])
    assert hits == ["Spezial"]


def test_parts_search_combined_with_filters(client, editor):
    asm = create_part(client, editor, "Such-BG", part_type="assembly", description="mit Pumpe")
    create_part(client, editor, "Such-Teil", part_type="part", description="mit Pumpe")
    r = client.get(
        "/api/v1/parts", params={"query": "pumpe", "part_type": "assembly"}, headers=editor
    )
    assert [p["name"] for p in r.json()] == ["Such-BG"]
    assert asm["part_number"]


# --- search: documents --------------------------------------------------------


def _create_doc(client, editor, title, doc_type="other"):
    r = client.post(
        "/api/v1/documents?direct=true", json={"title": title, "doc_type": doc_type}, headers=editor
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_documents_search_by_title_and_number(client, editor):
    doc = _create_doc(client, editor, "Wartungsanleitung Hydraulikpumpe")
    _create_doc(client, editor, "Schaltplan Steuerung")

    def q(query):
        r = client.get("/api/v1/documents", params={"query": query}, headers=editor)
        assert r.status_code == 200, r.text
        return [d["title"] for d in r.json()]

    assert q("wartungsanleitung") == ["Wartungsanleitung Hydraulikpumpe"]
    assert q("wartung schaltplan") == []  # AND semantics across words
    assert q(doc["doc_number"]) == ["Wartungsanleitung Hydraulikpumpe"]


# --- BOM diff report ----------------------------------------------------------


def _two_released_revs_with_bom_change(client, editor, approver):
    asm = create_part(client, editor, "Diff-BG", part_type="assembly")
    c1 = create_part(client, editor, "Diff-C1")
    c2 = create_part(client, editor, "Diff-C2")
    c3 = create_part(client, editor, "Diff-C3")
    rev1 = _rev_id(client, editor, asm["part_number"], "01")
    _add_item(client, editor, rev1, c1["part_number"], qty=2, pos=1)
    _add_item(client, editor, rev1, c2["part_number"], qty=5, pos=2)
    release_part(client, editor, approver, asm["part_number"], "01")

    r = client.post(
        f"/api/v1/parts/{asm['part_number']}/revisions?direct=true",
        json={"change_reason": "BOM Aenderung"},
        headers=editor,
    )
    assert r.status_code == 201, r.text
    rev2 = r.json()["id"]
    bom_rev2 = client.get(
        f"/api/v1/bom/parts/{asm['part_number']}", params={"rev": "02"}, headers=editor
    ).json()
    item_c1 = next(i for i in bom_rev2 if i["component_part_number"] == c1["part_number"])
    item_c2 = next(i for i in bom_rev2 if i["component_part_number"] == c2["part_number"])
    client.put(f"/api/v1/bom/items/{item_c1['id']}", params={"quantity": 7}, headers=editor)
    client.delete(f"/api/v1/bom/items/{item_c2['id']}", headers=editor)
    _add_item(client, editor, rev2, c3["part_number"], qty=1, pos=3)
    release_part(client, editor, approver, asm["part_number"], "02")
    return asm, c1, c2, c3


def test_bom_diff_report_direct(client, editor, approver, fake_typst):
    asm, c1, c2, c3 = _two_released_revs_with_bom_change(client, editor, approver)
    r = client.post(
        f"/api/v1/reports/parts/{asm['part_number']}/bom-diff",
        params={"rev_a": "01", "rev_b": "02", "direct": "true"},
        json={"reason": "Vergleich 01 vs 02"},
        headers=editor,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["template"] == "bom_diff_v1"
    snap = body["content_snapshot"]
    assert snap["part_number"] == asm["part_number"]
    assert snap["rev_a"] == "01" and snap["rev_b"] == "02"
    assert any(c3["part_number"] in a["component"] for a in snap["added"])
    assert any(c2["part_number"] in a["component"] for a in snap["removed"])
    changed = next(c for c in snap["changed"] if c1["part_number"] in c["component"])
    assert changed["from"]["quantity"] == 2.0
    assert changed["to"]["quantity"] == 7.0
    # PDF rendered (fake typst) and downloadable
    assert body["pdf_available"] is True
    r = client.get(f"/api/v1/reports/{body['report_id']}/download", headers=editor)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_bom_diff_report_requires_released_revisions(client, editor, approver, fake_typst):
    asm = create_part(client, editor, "Diff-BG-draft", part_type="assembly")
    release_part(client, editor, approver, asm["part_number"], "01")
    client.post(
        f"/api/v1/parts/{asm['part_number']}/revisions?direct=true",
        json={"change_reason": "noch draft"},
        headers=editor,
    )
    r = client.post(
        f"/api/v1/reports/parts/{asm['part_number']}/bom-diff",
        params={"rev_a": "01", "rev_b": "02", "direct": "true"},
        json={},
        headers=editor,
    )
    assert r.status_code == 409
    assert r.json()["code"] == "no_released_revision"


def test_bom_diff_report_unknown_revision_404(client, editor, approver, fake_typst):
    asm, _, _, _ = _two_released_revs_with_bom_change(client, editor, approver)
    r = client.post(
        f"/api/v1/reports/parts/{asm['part_number']}/bom-diff",
        params={"rev_a": "01", "rev_b": "99", "direct": "true"},
        json={},
        headers=editor,
    )
    assert r.status_code == 404
    assert r.json()["code"] == "revision_not_found"


def test_bom_diff_report_via_confirmation(client, editor, approver, fake_typst):
    asm, _, _, _ = _two_released_revs_with_bom_change(client, editor, approver)
    r = client.post(
        f"/api/v1/reports/parts/{asm['part_number']}/bom-diff",
        params={"rev_a": "01", "rev_b": "02"},
        json={"reason": "als Vorschlag"},
        headers=editor,
    )
    assert r.status_code == 202, r.text
    conf_id = r.json()["confirmation_id"]
    r = client.post(f"/api/v1/confirmations/{conf_id}/approve", headers=approver)
    assert r.status_code == 200, r.text
    reports = client.get("/api/v1/reports", headers=editor).json()
    entry = next(x for x in reports if x["template"] == "bom_diff_v1")
    detail = client.get(f"/api/v1/reports/{entry['report_id']}", headers=editor).json()
    assert detail["content_snapshot"]["rev_a"] == "01"
    assert detail["content_snapshot"]["rev_b"] == "02"
