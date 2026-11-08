from tests.conftest import create_part


def test_proposed_write_returns_202_and_waits(client, editor):
    r = client.post(
        "/api/v1/parts",
        json={"name": "Vorschlag-Teil", "class_code": "MECH"},
        headers=editor,
    )
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "proposed"
    conf_id = body["confirmation_id"]

    listing = client.get("/api/v1/parts?query=Vorschlag", headers=editor).json()
    assert listing == []

    conf = client.get(f"/api/v1/confirmations/{conf_id}", headers=editor).json()
    assert conf["status"] == "proposed"
    assert conf["action"] == "create_part"

    r2 = client.post(f"/api/v1/confirmations/{conf_id}/approve", headers=editor)
    assert r2.status_code == 200
    assert r2.json()["status"] == "executed"

    listing = client.get("/api/v1/parts?query=Vorschlag", headers=editor).json()
    assert len(listing) == 1
    assert listing[0]["part_number"] == "P-000001"


def test_reject_leaves_no_trace_in_parts(client, editor):
    r = client.post(
        "/api/v1/parts",
        json={"name": "Abgelehnt", "class_code": "MECH"},
        headers=editor,
    )
    conf_id = r.json()["confirmation_id"]
    r2 = client.post(f"/api/v1/confirmations/{conf_id}/reject", headers=editor)
    assert r2.json()["status"] == "rejected"
    assert client.get("/api/v1/parts?query=Abgelehnt", headers=editor).json() == []


def test_double_approve_conflicts(client, editor):
    r = client.post(
        "/api/v1/parts",
        json={"name": "Nur Einmal", "class_code": "MECH"},
        headers=editor,
    )
    conf_id = r.json()["confirmation_id"]
    client.post(f"/api/v1/confirmations/{conf_id}/approve", headers=editor)
    r2 = client.post(f"/api/v1/confirmations/{conf_id}/approve", headers=editor)
    assert r2.status_code == 409


def test_viewer_cannot_approve(client, editor, viewer):
    r = client.post(
        "/api/v1/parts",
        json={"name": "Viewer Test", "class_code": "MECH"},
        headers=editor,
    )
    conf_id = r.json()["confirmation_id"]
    r2 = client.post(f"/api/v1/confirmations/{conf_id}/approve", headers=viewer)
    assert r2.status_code == 403


def test_confirmed_write_lands_in_audit_log(client, editor, admin):
    create_part(client, editor, "Direkt", )
    r = client.post(
        "/api/v1/parts",
        json={"name": "Per Token", "class_code": "MECH"},
        headers=editor,
    )
    conf_id = r.json()["confirmation_id"]
    client.post(f"/api/v1/confirmations/{conf_id}/approve", headers=editor)
    log = client.get("/api/v1/admin/audit-log", headers=admin).json()
    actions = {(e["entity_type"], e["action"]) for e in log}
    assert ("part", "create") in actions
    assert ("part_revision", "create") in actions
