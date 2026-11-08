from tests.conftest import create_part


def _rev_id(client, headers, part_number, revision="01"):
    r = client.get(f"/api/v1/parts/{part_number}", headers=headers)
    for rev in r.json()["revisions"]:
        if rev["revision"] == revision:
            return rev["id"]
    raise AssertionError(f"revision {revision} not found")


def test_create_revision_increments_label(client, editor):
    part = create_part(client, editor, "Baugruppe X", part_type="assembly")
    pn = part["part_number"]
    r = client.post(
        f"/api/v1/parts/{pn}/revisions?direct=true",
        json={"change_reason": "Gehaeuse angepasst"},
        headers=editor,
    )
    assert r.status_code == 201
    assert r.json()["revision"] == "02"
    assert r.json()["status"] == "draft"


def test_full_release_workflow(client, editor, approver):
    part = create_part(client, editor, "Teil W")
    rev = _rev_id(client, editor, part["part_number"])

    r = client.post(
        f"/api/v1/revisions/{rev}/transition?direct=true",
        json={"to_status": "review", "reason": "fertig zur Pruefung"},
        headers=editor,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "review"

    r = client.post(
        f"/api/v1/revisions/{rev}/transition?direct=true",
        json={"to_status": "released", "reason": "Freigabe durch Approver"},
        headers=approver,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "released"

    r = client.post(
        f"/api/v1/revisions/{rev}/transition?direct=true",
        json={"to_status": "obsolete", "reason": "abgeloest"},
        headers=approver,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "obsolete"


def test_invalid_transition_is_422(client, editor):
    """M5: status jump outside the matrix is rejected with 422."""
    part = create_part(client, editor, "Teil V")
    rev = _rev_id(client, editor, part["part_number"])
    r = client.post(
        f"/api/v1/revisions/{rev}/transition?direct=true",
        json={"to_status": "released", "reason": "direkt freigeben geht nicht"},
        headers=editor,
    )
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_transition"


def test_release_requires_approver_role(client, editor):
    part = create_part(client, editor, "Teil R")
    rev = _rev_id(client, editor, part["part_number"])
    client.post(
        f"/api/v1/revisions/{rev}/transition?direct=true",
        json={"to_status": "review", "reason": "review"},
        headers=editor,
    )
    r = client.post(
        f"/api/v1/revisions/{rev}/transition?direct=true",
        json={"to_status": "released", "reason": "editor darf nicht releasen"},
        headers=editor,
    )
    assert r.status_code == 403


def test_released_revision_is_immutable(client, editor, approver):
    part = create_part(client, editor, "Teil I", part_type="assembly")
    comp = create_part(client, editor, "Komponente I")
    rev = _rev_id(client, editor, part["part_number"])
    client.post(
        f"/api/v1/revisions/{rev}/transition?direct=true",
        json={"to_status": "review", "reason": "r"},
        headers=editor,
    )
    client.post(
        f"/api/v1/revisions/{rev}/transition?direct=true",
        json={"to_status": "released", "reason": "r"},
        headers=approver,
    )
    r = client.post(
        "/api/v1/bom/items",
        params={"parent_rev_id": rev, "direct": "true"},
        json={"component_part_number": comp["part_number"], "quantity": 1, "unit": "Stk", "position": 1},
        headers=editor,
    )
    assert r.status_code == 409
    assert r.json()["code"] == "released_immutable"

    r = client.put(f"/api/v1/parts/{part['part_number']}/revisions/{rev}", headers=editor)
    assert r.status_code == 409


def test_new_revision_after_release_copies_bom(client, editor, approver):
    asm = create_part(client, editor, "BG", part_type="assembly")
    comp = create_part(client, editor, "KT")
    rev1 = _rev_id(client, editor, asm["part_number"])
    client.post(
        "/api/v1/bom/items",
        params={"parent_rev_id": rev1, "direct": "true"},
        json={"component_part_number": comp["part_number"], "quantity": 2, "unit": "Stk", "position": 1},
        headers=editor,
    )
    for to, h in (("review", editor), ("released", approver)):
        client.post(
            f"/api/v1/revisions/{rev1}/transition?direct=true",
            json={"to_status": to, "reason": "x"},
            headers=h,
        )
    r = client.post(
        f"/api/v1/parts/{asm['part_number']}/revisions?direct=true",
        json={"change_reason": "neue Variante"},
        headers=editor,
    )
    r.json()["id"]
    bom = client.get(f"/api/v1/bom/parts/{asm['part_number']}?rev=02", headers=editor).json()
    assert len(bom) == 1
    assert bom[0]["component_part_number"] == comp["part_number"]
    assert bom[0]["quantity"] == 2.0
