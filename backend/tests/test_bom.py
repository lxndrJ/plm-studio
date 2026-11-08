from tests.conftest import create_part


def _rev_id(client, headers, part_number, revision="01"):
    r = client.get(f"/api/v1/parts/{part_number}", headers=headers)
    for rev in r.json()["revisions"]:
        if rev["revision"] == revision:
            return rev["id"]
    raise AssertionError("revision not found")


def _add_item(client, headers, parent_rev, comp_pn, qty=1, pos=1, unit="Stk"):
    r = client.post(
        "/api/v1/bom/items",
        params={"parent_rev_id": parent_rev, "direct": "true"},
        json={
            "component_part_number": comp_pn,
            "quantity": qty,
            "unit": unit,
            "position": pos,
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def _setup_three_level(client, editor):
    leaf = create_part(client, editor, "Schraube M4")
    mid = create_part(client, editor, "Halterung", part_type="assembly")
    top = create_part(client, editor, "Gehaeuse", part_type="assembly")
    mid_rev = _rev_id(client, editor, mid["part_number"])
    top_rev = _rev_id(client, editor, top["part_number"])
    _add_item(client, editor, mid_rev, leaf["part_number"], qty=4, pos=1)
    _add_item(client, editor, top_rev, mid["part_number"], qty=2, pos=1)
    return leaf, mid, top


def test_add_and_list_bom_items(client, editor):
    asm = create_part(client, editor, "BG1", part_type="assembly")
    comp = create_part(client, editor, "KT1")
    rev = _rev_id(client, editor, asm["part_number"])
    item = _add_item(client, editor, rev, comp["part_number"], qty=3, pos=1)
    assert item["component_part_number"] == comp["part_number"]
    assert item["component_revision"] == "01"
    bom = client.get(f"/api/v1/bom/parts/{asm['part_number']}", headers=editor).json()
    assert len(bom) == 1
    assert bom[0]["quantity"] == 3.0


def test_where_used_recursive_multi_level(client, editor):
    """M3: where-used works recursively across several levels."""
    leaf, mid, top = _setup_three_level(client, editor)
    wu = client.get(f"/api/v1/bom/parts/{leaf['part_number']}/where-used", headers=editor).json()
    by_part = {e["parent_part_number"]: e["depth"] for e in wu}
    assert by_part[mid["part_number"]] == 1
    assert by_part[top["part_number"]] == 2


def test_where_used_empty_for_unused_part(client, editor):
    p = create_part(client, editor, "Einzelteil")
    wu = client.get(f"/api/v1/bom/parts/{p['part_number']}/where-used", headers=editor).json()
    assert wu == []


def test_component_must_be_draft_or_released(client, editor, approver):
    asm = create_part(client, editor, "BG2", part_type="assembly")
    comp = create_part(client, editor, "KT2")
    comp_rev = _rev_id(client, editor, comp["part_number"])
    for to, h in (("review", editor),):
        client.post(
            f"/api/v1/revisions/{comp_rev}/transition?direct=true",
            json={"to_status": to, "reason": "x"},
            headers=h,
        )
    asm_rev = _rev_id(client, editor, asm["part_number"])
    r = client.post(
        "/api/v1/bom/items",
        params={"parent_rev_id": asm_rev, "direct": "true"},
        json={"component_part_number": comp["part_number"], "quantity": 1, "position": 1},
        headers=editor,
    )
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_component_status"


def test_bom_self_reference_rejected(client, editor):
    asm = create_part(client, editor, "BG3", part_type="assembly")
    rev = _rev_id(client, editor, asm["part_number"])
    r = client.post(
        "/api/v1/bom/items",
        params={"parent_rev_id": rev, "direct": "true"},
        json={"component_part_number": asm["part_number"], "quantity": 1, "position": 1},
        headers=editor,
    )
    assert r.status_code == 422


def test_bom_diff_shows_added_removed_changed(client, editor):
    """M3: BOM diff shows quantity/ref changes between two revisions."""
    asm = create_part(client, editor, "BG4", part_type="assembly")
    c1 = create_part(client, editor, "KT-A")
    c2 = create_part(client, editor, "KT-B")
    rev1 = _rev_id(client, editor, asm["part_number"])
    _add_item(client, editor, rev1, c1["part_number"], qty=2, pos=1)
    _add_item(client, editor, rev1, c2["part_number"], qty=5, pos=2)

    r = client.post(
        f"/api/v1/parts/{asm['part_number']}/revisions?direct=true",
        json={"change_reason": "Aenderung"},
        headers=editor,
    )
    rev2 = r.json()["id"]

    bom_rev2 = client.get(f"/api/v1/bom/parts/{asm['part_number']}", params={"rev": "02"}, headers=editor).json()
    item_a_rev2 = next(i for i in bom_rev2 if i["component_part_number"] == c1["part_number"])
    item2 = next(i for i in bom_rev2 if i["component_part_number"] == c2["part_number"])
    client.put(f"/api/v1/bom/items/{item_a_rev2['id']}", params={"quantity": 7}, headers=editor)
    client.delete(f"/api/v1/bom/items/{item2['id']}", headers=editor)
    c3 = create_part(client, editor, "KT-C")
    _add_item(client, editor, rev2, c3["part_number"], qty=1, pos=3)

    diff = client.get(
        f"/api/v1/bom/parts/{asm['part_number']}/diff",
        params={"rev_a": "01", "rev_b": "02"},
        headers=editor,
    ).json()
    added = {d["component"] for d in diff["added"]}
    removed = {d["component"] for d in diff["removed"]}
    changed = {d["component"]: d for d in diff["changed"]}
    assert any(c3["part_number"] in a for a in added)
    assert any(c2["part_number"] in a for a in removed)
    assert any(c1["part_number"] in c for c in changed)
    entry = next(c for c in changed.values() if c1["part_number"] in c["component"])
    assert entry["from"]["quantity"] == 2.0
    assert entry["to"]["quantity"] == 7.0


def test_bom_item_on_released_parent_rejected(client, editor, approver):
    asm = create_part(client, editor, "BG5", part_type="assembly")
    comp = create_part(client, editor, "KT5")
    rev = _rev_id(client, editor, asm["part_number"])
    client.post(
        f"/api/v1/revisions/{rev}/transition?direct=true",
        json={"to_status": "review", "reason": "x"},
        headers=editor,
    )
    client.post(
        f"/api/v1/revisions/{rev}/transition?direct=true",
        json={"to_status": "released", "reason": "x"},
        headers=approver,
    )
    r = client.post(
        "/api/v1/bom/items",
        params={"parent_rev_id": rev, "direct": "true"},
        json={"component_part_number": comp["part_number"], "quantity": 1, "position": 1},
        headers=editor,
    )
    assert r.status_code == 409
