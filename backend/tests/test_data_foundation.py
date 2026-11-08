"""M1.5 data foundation: revision-scoped attributes, class hierarchy, typed
attribute definitions and units master data (ADR 0002)."""

from tests.conftest import create_part


def _rev_id(client, headers, part_number, revision="01"):
    r = client.get(f"/api/v1/parts/{part_number}", headers=headers)
    for rev in r.json()["revisions"]:
        if rev["revision"] == revision:
            return rev["id"]
    raise AssertionError(f"revision {revision} not found")


def test_attributes_live_on_revisions_not_parts(client, editor):
    part = create_part(client, editor, "Datenteil", attributes={"material": "Alu", "weight_kg": 1.5})
    assert "attributes" not in part
    detail = client.get(f"/api/v1/parts/{part['part_number']}", headers=editor).json()
    assert "attributes" not in detail
    assert detail["revisions"][0]["attributes"] == {"material": "Alu", "weight_kg": 1.5}


def test_typed_attribute_rejects_wrong_type(client, editor):
    r = client.post(
        "/api/v1/parts?direct=true",
        json={"name": "Falsch", "class_code": "MECH", "attributes": {"weight_kg": "schwer"}},
        headers=editor,
    )
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_attributes"


def test_enum_attribute_validates_allowed_values(client, editor):
    r = client.post(
        "/api/v1/parts?direct=true",
        json={"name": "Platine E", "class_code": "ELEC", "attributes": {"ip_rating": "IP99"}},
        headers=editor,
    )
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_attributes"
    part = create_part(
        client, editor, "Platine E gueltig", class_code="ELEC", attributes={"ip_rating": "IP54"}
    )
    assert part["revisions"][0]["attributes"]["ip_rating"] == "IP54"


def test_undefined_attribute_keys_pass_through(client, editor):
    part = create_part(client, editor, "Freitext", attributes={"anything": "value"})
    assert part["revisions"][0]["attributes"]["anything"] == "value"


def test_new_revision_inherits_attributes(client, editor):
    part = create_part(client, editor, "Vererbt", attributes={"material": "Stahl"})
    r = client.post(
        f"/api/v1/parts/{part['part_number']}/revisions?direct=true",
        json={"change_reason": "Nachfolger"},
        headers=editor,
    )
    assert r.status_code == 201
    assert r.json()["attributes"] == {"material": "Stahl"}


def test_bom_unit_must_exist_in_master_data(client, editor):
    asm = create_part(client, editor, "Baugruppe U", part_type="assembly")
    comp = create_part(client, editor, "Komponente U")
    rev = _rev_id(client, editor, asm["part_number"])
    r = client.post(
        "/api/v1/bom/items",
        params={"parent_rev_id": rev, "direct": "true"},
        json={"component_part_number": comp["part_number"], "quantity": 1, "unit": "pfund", "position": 1},
        headers=editor,
    )
    assert r.status_code == 422
    assert r.json()["code"] == "unknown_unit"
    r = client.post(
        "/api/v1/bom/items",
        params={"parent_rev_id": rev, "direct": "true"},
        json={"component_part_number": comp["part_number"], "quantity": 0.5, "unit": "m", "position": 1},
        headers=editor,
    )
    assert r.status_code == 201


def test_search_includes_class_subtree(client, editor):
    fas = create_part(client, editor, "Schraube FAS", class_code="FAS")
    create_part(client, editor, "Normteil MECH", class_code="MECH")
    r = client.get("/api/v1/parts?class_code=MECH", headers=editor)
    assert r.status_code == 200
    numbers = {p["part_number"] for p in r.json()}
    assert fas["part_number"] in numbers


def test_search_with_unknown_class_is_404(client, editor):
    r = client.get("/api/v1/parts?class_code=NOPE", headers=editor)
    assert r.status_code == 404
    assert r.json()["code"] == "class_not_found"


def test_admin_can_create_subclass(client, admin):
    r = client.post(
        "/api/v1/admin/part-classes",
        json={"code": "RAW", "name": "Rohmaterial", "parent_code": "MECH"},
        headers=admin,
    )
    assert r.status_code == 201
    assert r.json()["parent_id"] is not None
    r2 = client.post(
        "/api/v1/admin/part-classes",
        json={"code": "ORPHAN", "name": "Ohne Parent", "parent_code": "NOPE"},
        headers=admin,
    )
    assert r2.status_code == 404
    assert r2.json()["code"] == "class_not_found"
