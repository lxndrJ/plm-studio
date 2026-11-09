"""M9: ECO execution - 'executed' creates a successor draft revision per affected
(released) part revision, inheriting attributes + BOM; idempotent via the
workflow matrix."""

from tests.conftest import create_part, release_part
from tests.test_changes import _approve_ecr, _create_eco, _create_ecr


def _setup_released_assembly(client, editor, approver, name="Gehaeuse"):
    part = create_part(
        client,
        editor,
        name,
        part_type="assembly",
        attributes={"material": "Stahl", "weight_kg": 1.5},
    )
    comp = create_part(client, editor, f"Schraube {name}")
    revs = client.get(f"/api/v1/parts/{part['part_number']}/revisions", headers=editor).json()
    rev01 = next(r for r in revs if r["revision"] == "01")
    r = client.post(
        "/api/v1/bom/items",
        params={"parent_rev_id": rev01["id"], "direct": "true"},
        json={
            "component_part_number": comp["part_number"],
            "component_revision": "01",
            "quantity": 4,
            "unit": "Stk",
            "position": 1,
        },
        headers=editor,
    )
    assert r.status_code == 201, r.text
    release_part(client, editor, approver, part["part_number"])
    return part, comp


def _approved_eco_with_affected(client, editor, approver, part_number, revision="01"):
    ecr = _create_ecr(client, editor, description="Aenderung umsetzen")
    _approve_ecr(client, editor, approver, ecr["number"])
    eco = _create_eco(client, editor, ecr["number"])
    r = client.post(
        f"/api/v1/ecos/{eco['number']}/affected-revisions?direct=true",
        json={"part_number": part_number, "revision": revision},
        headers=editor,
    )
    assert r.status_code == 201, r.text
    r = client.post(
        f"/api/v1/ecos/{eco['number']}/transition?direct=true",
        json={"to_status": "approved", "reason": "freigeben"},
        headers=approver,
    )
    assert r.status_code == 200, r.text
    return eco


def _execute(client, approver, eco_number, direct=True):
    suffix = "?direct=true" if direct else ""
    return client.post(
        f"/api/v1/ecos/{eco_number}/transition{suffix}",
        json={"to_status": "executed", "reason": "umgesetzt"},
        headers=approver,
    )


# --- guardrail: only released revisions can be affected ---------------------


def test_add_affected_requires_released_revision(client, editor, approver):
    part = create_part(client, editor, "Teil R")
    ecr = _create_ecr(client, editor)
    _approve_ecr(client, editor, approver, ecr["number"])
    eco = _create_eco(client, editor, ecr["number"])
    r = client.post(
        f"/api/v1/ecos/{eco['number']}/affected-revisions?direct=true",
        json={"part_number": part["part_number"], "revision": "01"},
        headers=editor,
    )
    assert r.status_code == 409
    assert r.json()["code"] == "affected_not_released"

    release_part(client, editor, approver, part["part_number"])
    r = client.post(
        f"/api/v1/ecos/{eco['number']}/affected-revisions?direct=true",
        json={"part_number": part["part_number"], "revision": "01"},
        headers=editor,
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "released"


# --- execution creates successor revisions -----------------------------------


def test_eco_executed_creates_successor_with_inherited_attributes_and_bom(
    client, db, editor, approver, admin
):
    part, comp = _setup_released_assembly(client, editor, approver)
    eco = _approved_eco_with_affected(client, editor, approver, part["part_number"])

    r = _execute(client, approver, eco["number"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "executed"
    assert len(body["created_revisions"]) == 1
    created = body["created_revisions"][0]
    assert created["part_number"] == part["part_number"]
    assert created["revision"] == "02"
    assert created["status"] == "draft"

    revs = client.get(f"/api/v1/parts/{part['part_number']}/revisions", headers=editor).json()
    assert [x["revision"] for x in revs] == ["01", "02"]
    rev2 = next(x for x in revs if x["revision"] == "02")
    assert rev2["status"] == "draft"
    assert rev2["attributes"] == {"material": "Stahl", "weight_kg": 1.5}
    assert eco["number"] in rev2["change_reason"]

    # BOM inherited into the successor, old revision untouched
    bom2 = client.get(f"/api/v1/bom/parts/{part['part_number']}?rev=02", headers=editor).json()
    assert len(bom2) == 1
    assert bom2[0]["component_part_number"] == comp["part_number"]
    assert float(bom2[0]["quantity"]) == 4
    bom1 = client.get(f"/api/v1/bom/parts/{part['part_number']}?rev=01", headers=editor).json()
    assert len(bom1) == 1
    rev1 = next(x for x in revs if x["revision"] == "01")
    assert rev1["status"] == "released"

    # audit: eco execute + part_revision create
    log = client.get("/api/v1/admin/audit-log", headers=admin).json()
    execute_entries = [e for e in log if e["entity_type"] == "eco" and e["action"] == "execute"]
    assert len(execute_entries) == 1
    assert execute_entries[0]["new_values"]["created_revisions"][0]["revision"] == "02"
    create_entries = [
        e for e in log if e["entity_type"] == "part_revision" and e["action"] == "create"
    ]
    assert any(e["new_values"]["revision"] == "02" for e in create_entries)


def test_eco_executed_creates_one_successor_per_affected_part(client, editor, approver):
    part_a, _ = _setup_released_assembly(client, editor, approver, "Baugruppe A")
    part_b, _ = _setup_released_assembly(client, editor, approver, "Baugruppe B")
    ecr = _create_ecr(client, editor)
    _approve_ecr(client, editor, approver, ecr["number"])
    eco = _create_eco(client, editor, ecr["number"])
    for p in (part_a, part_b):
        r = client.post(
            f"/api/v1/ecos/{eco['number']}/affected-revisions?direct=true",
            json={"part_number": p["part_number"], "revision": "01"},
            headers=editor,
        )
        assert r.status_code == 201, r.text
    client.post(
        f"/api/v1/ecos/{eco['number']}/transition?direct=true",
        json={"to_status": "approved", "reason": "ok"},
        headers=approver,
    )
    r = _execute(client, approver, eco["number"])
    assert r.status_code == 200, r.text
    created = {c["part_number"]: c["revision"] for c in r.json()["created_revisions"]}
    assert created == {part_a["part_number"]: "02", part_b["part_number"]: "02"}


def test_eco_cannot_be_executed_twice(client, editor, approver):
    part, _ = _setup_released_assembly(client, editor, approver)
    eco = _approved_eco_with_affected(client, editor, approver, part["part_number"])
    r = _execute(client, approver, eco["number"])
    assert r.status_code == 200, r.text
    r = _execute(client, approver, eco["number"])
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_transition"
    # still exactly one successor
    revs = client.get(f"/api/v1/parts/{part['part_number']}/revisions", headers=editor).json()
    assert [x["revision"] for x in revs] == ["01", "02"]


def test_eco_executed_via_confirmation_token_creates_revisions(client, editor, approver):
    part, _ = _setup_released_assembly(client, editor, approver)
    eco = _approved_eco_with_affected(client, editor, approver, part["part_number"])
    r = _execute(client, approver, eco["number"], direct=False)
    assert r.status_code == 202
    conf_id = r.json()["confirmation_id"]
    r = client.post(f"/api/v1/confirmations/{conf_id}/approve", headers=approver)
    assert r.status_code == 200, r.text
    revs = client.get(f"/api/v1/parts/{part['part_number']}/revisions", headers=editor).json()
    assert [x["revision"] for x in revs] == ["01", "02"]
    eco_detail = client.get(f"/api/v1/ecos/{eco['number']}", headers=editor).json()
    assert eco_detail["status"] == "executed"


def test_successor_is_draft_and_mutable_old_stays_immutable(client, editor, approver):
    part, comp = _setup_released_assembly(client, editor, approver)
    eco = _approved_eco_with_affected(client, editor, approver, part["part_number"])
    _execute(client, approver, eco["number"])
    revs = client.get(f"/api/v1/parts/{part['part_number']}/revisions", headers=editor).json()
    rev1 = next(x for x in revs if x["revision"] == "01")
    rev2 = next(x for x in revs if x["revision"] == "02")
    # BOM change on the released revision is rejected ...
    r = client.post(
        "/api/v1/bom/items",
        params={"parent_rev_id": rev1["id"], "direct": "true"},
        json={
            "component_part_number": comp["part_number"],
            "component_revision": "01",
            "quantity": 1,
            "unit": "Stk",
            "position": 2,
        },
        headers=editor,
    )
    assert r.status_code == 409
    assert r.json()["code"] == "released_immutable"
    # ... but works on the new draft successor
    r = client.post(
        "/api/v1/bom/items",
        params={"parent_rev_id": rev2["id"], "direct": "true"},
        json={
            "component_part_number": comp["part_number"],
            "component_revision": "01",
            "quantity": 1,
            "unit": "Stk",
            "position": 2,
        },
        headers=editor,
    )
    assert r.status_code == 201, r.text
