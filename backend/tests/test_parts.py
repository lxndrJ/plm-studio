from tests.conftest import create_part


def test_create_part_assigns_number_and_initial_revision(client, editor):
    part = create_part(client, editor, "Gehaeuse A")
    assert part["part_number"] == "P-000001"
    assert part["part_type"] == "part"
    assert len(part["revisions"]) == 1
    assert part["revisions"][0]["revision"] == "01"
    assert part["revisions"][0]["status"] == "draft"


def test_second_part_gets_next_number(client, editor):
    create_part(client, editor, "Teil 1")
    part = create_part(client, editor, "Teil 2")
    assert part["part_number"] == "P-000002"


def test_duplicate_name_in_same_class_conflicts(client, editor):
    create_part(client, editor, "Gehaeuse A")
    r = client.post(
        "/api/v1/parts?direct=true",
        json={"name": "gehaeuse a", "class_code": "MECH"},
        headers=editor,
    )
    assert r.status_code == 409
    assert r.json()["code"] == "duplicate_part"
    assert r.json()["details"]["candidates"][0]["part_number"] == "P-000001"


def test_same_name_in_other_class_allowed(client, admin, editor):
    r = client.post(
        "/api/v1/admin/part-classes?direct=true",
        json={"code": "SW", "name": "Software"},
        headers=admin,
    )
    # part-classes endpoint has no direct flag; plain POST
    assert r.status_code in (200, 201)
    create_part(client, editor, "Gehaeuse A", class_code="MECH")
    part = create_part(client, editor, "Gehaeuse A", class_code="SW")
    assert part["part_number"] == "P-000002"


def test_unknown_class_404(client, editor):
    r = client.post(
        "/api/v1/parts?direct=true",
        json={"name": "x", "class_code": "NOPE"},
        headers=editor,
    )
    assert r.status_code == 404


def test_search_parts(client, editor):
    create_part(client, editor, "Gehaeuse A")
    create_part(client, editor, "Platine B")
    r = client.get("/api/v1/parts?query=platine", headers=editor)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["name"] == "Platine B"


def test_get_part_detail(client, editor):
    part = create_part(client, editor, "Gehaeuse A")
    r = client.get(f"/api/v1/parts/{part['part_number']}", headers=editor)
    assert r.status_code == 200
    assert r.json()["name"] == "Gehaeuse A"


def test_get_unknown_part_404(client, editor):
    r = client.get("/api/v1/parts/P-999999", headers=editor)
    assert r.status_code == 404
