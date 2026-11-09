from tests.conftest import create_part, release_part


def _create_ecr(client, headers, description="Gehaeuse aendern", **extra):
    payload = {"description": description, **extra}
    r = client.post("/api/v1/ecrs?direct=true", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _transition_ecr(client, headers, number, to_status, reason="weiter"):
    return client.post(
        f"/api/v1/ecrs/{number}/transition?direct=true",
        json={"to_status": to_status, "reason": reason},
        headers=headers,
    )


def _approve_ecr(client, editor, approver, number):
    r = _transition_ecr(client, editor, number, "in_review", "zur Pruefung")
    assert r.status_code == 200, r.text
    r = _transition_ecr(client, approver, number, "approved", "freigegeben")
    assert r.status_code == 200, r.text
    return r.json()


def _create_eco(client, headers, ecr_number, reason="umsetzen"):
    r = client.post(
        f"/api/v1/ecrs/{ecr_number}/ecos?direct=true", json={"reason": reason}, headers=headers
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_create_ecr_direct_gets_number_from_range(client, editor, admin):
    ecr = _create_ecr(client, editor, reason="initiales ECR")
    assert ecr["number"] == "ECR-00001"
    assert ecr["status"] == "open"
    assert ecr["description"] == "Gehaeuse aendern"

    second = _create_ecr(client, editor, description="Zweites ECR")
    assert second["number"] == "ECR-00002"

    log = client.get("/api/v1/admin/audit-log", headers=admin).json()
    ecr_entries = [e for e in log if e["entity_type"] == "ecr" and e["action"] == "create"]
    assert len(ecr_entries) == 2
    assert ecr_entries[0]["new_values"]["number"] in ("ECR-00001", "ECR-00002")


def test_list_and_get_ecr_with_status_filter(client, editor):
    ecr = _create_ecr(client, editor)
    _transition_ecr(client, editor, ecr["number"], "in_review")

    r = client.get("/api/v1/ecrs", headers=editor)
    assert r.status_code == 200
    assert [e["number"] for e in r.json()] == ["ECR-00001"]

    r = client.get("/api/v1/ecrs?status=open", headers=editor)
    assert r.json() == []
    r = client.get("/api/v1/ecrs?status=in_review", headers=editor)
    assert len(r.json()) == 1

    r = client.get(f"/api/v1/ecrs/{ecr['number']}", headers=editor)
    assert r.status_code == 200
    assert r.json()["status"] == "in_review"
    assert r.json()["ecos"] == []

    r = client.get("/api/v1/ecrs/ECR-99999", headers=editor)
    assert r.status_code == 404
    assert r.json()["code"] == "ecr_not_found"


def test_ecr_full_workflow_and_role_rules(client, editor, approver, viewer):
    ecr = _create_ecr(client, editor)
    n = ecr["number"]

    r = _transition_ecr(client, viewer, n, "in_review")
    assert r.status_code == 403

    r = _transition_ecr(client, editor, n, "approved")
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_transition"

    r = _transition_ecr(client, editor, n, "open")
    assert r.status_code == 422

    r = _transition_ecr(client, editor, n, "in_review")
    assert r.status_code == 200
    assert r.json()["status"] == "in_review"

    r = _transition_ecr(client, editor, n, "approved")
    assert r.status_code == 403
    assert r.json()["code"] == "insufficient_role_for_transition"

    r = _transition_ecr(client, approver, n, "approved")
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    r = _transition_ecr(client, approver, n, "rejected")
    assert r.status_code == 422


def test_ecr_reject_path(client, editor, approver):
    ecr = _create_ecr(client, editor)
    _transition_ecr(client, editor, ecr["number"], "in_review")
    r = _transition_ecr(client, approver, ecr["number"], "rejected", "nicht wirtschaftlich")
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"


def test_create_ecr_via_confirmation_token(client, editor):
    r = client.post(
        "/api/v1/ecrs", json={"description": "agent ECR", "reason": "vorgelegt"}, headers=editor
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "proposed"
    conf_id = body["confirmation_id"]

    r = client.get(f"/api/v1/confirmations/{conf_id}", headers=editor)
    assert r.json()["status"] == "proposed"
    assert client.get("/api/v1/ecrs", headers=editor).json() == []

    r = client.post(f"/api/v1/confirmations/{conf_id}/approve", headers=editor)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "executed"

    ecrs = client.get("/api/v1/ecrs", headers=editor).json()
    assert len(ecrs) == 1
    assert ecrs[0]["description"] == "agent ECR"
    assert ecrs[0]["number"] == "ECR-00001"


def test_proposed_ecr_transition_executes_on_approve(client, editor, approver):
    ecr = _create_ecr(client, editor)
    r = client.post(
        f"/api/v1/ecrs/{ecr['number']}/transition",
        json={"to_status": "in_review", "reason": "agent schlaegt review vor"},
        headers=editor,
    )
    assert r.status_code == 202
    conf_id = r.json()["confirmation_id"]
    assert client.get(f"/api/v1/ecrs/{ecr['number']}", headers=editor).json()["status"] == "open"

    r = client.post(f"/api/v1/confirmations/{conf_id}/approve", headers=editor)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "executed"
    assert (
        client.get(f"/api/v1/ecrs/{ecr['number']}", headers=editor).json()["status"] == "in_review"
    )


def test_eco_requires_approved_ecr(client, editor, approver):
    ecr = _create_ecr(client, editor)
    r = client.post(f"/api/v1/ecrs/{ecr['number']}/ecos?direct=true", json={}, headers=editor)
    assert r.status_code == 409
    assert r.json()["code"] == "ecr_not_approved"

    _approve_ecr(client, editor, approver, ecr["number"])
    eco = _create_eco(client, editor, ecr["number"])
    assert eco["number"] == "ECO-00001"
    assert eco["status"] == "draft"
    assert eco["ecr_number"] == ecr["number"]
    assert eco["affected"] == []

    detail = client.get(f"/api/v1/ecrs/{ecr['number']}", headers=editor).json()
    assert [e["number"] for e in detail["ecos"]] == ["ECO-00001"]


def test_eco_via_confirmation_token(client, editor, approver):
    ecr = _create_ecr(client, editor)
    _approve_ecr(client, editor, approver, ecr["number"])
    r = client.post(
        f"/api/v1/ecrs/{ecr['number']}/ecos", json={"reason": "agent ECO"}, headers=editor
    )
    assert r.status_code == 202
    conf_id = r.json()["confirmation_id"]
    r = client.post(f"/api/v1/confirmations/{conf_id}/approve", headers=editor)
    assert r.status_code == 200
    ecos = client.get("/api/v1/ecos", headers=editor).json()
    assert len(ecos) == 1
    assert ecos[0]["number"] == "ECO-00001"


def test_eco_affected_revisions_add_list_remove(client, editor, approver):
    part = create_part(client, editor, "Betroffener Teil")
    release_part(client, editor, approver, part["part_number"])
    ecr = _create_ecr(client, editor)
    _approve_ecr(client, editor, approver, ecr["number"])
    eco = _create_eco(client, editor, ecr["number"])
    n = eco["number"]

    r = client.post(
        f"/api/v1/ecos/{n}/affected-revisions?direct=true",
        json={"part_number": part["part_number"], "revision": "01", "reason": "betroffen"},
        headers=editor,
    )
    assert r.status_code == 201, r.text
    entry = r.json()
    assert entry["part_number"] == part["part_number"]
    assert entry["revision"] == "01"
    assert entry["status"] == "released"

    r = client.post(
        f"/api/v1/ecos/{n}/affected-revisions?direct=true",
        json={"part_number": part["part_number"], "revision": "01"},
        headers=editor,
    )
    assert r.status_code == 409
    assert r.json()["code"] == "duplicate_affected_revision"

    r = client.post(
        f"/api/v1/ecos/{n}/affected-revisions?direct=true",
        json={"part_number": "P-999999"},
        headers=editor,
    )
    assert r.status_code == 404
    assert r.json()["code"] == "part_not_found"

    eco_detail = client.get(f"/api/v1/ecos/{n}", headers=editor).json()
    assert len(eco_detail["affected"]) == 1
    assert eco_detail["affected"][0]["revision_id"] == entry["revision_id"]

    r = client.delete(f"/api/v1/ecos/{n}/affected-revisions/{entry['revision_id']}", headers=editor)
    assert r.status_code == 204
    assert client.get(f"/api/v1/ecos/{n}", headers=editor).json()["affected"] == []

    r = client.delete(f"/api/v1/ecos/{n}/affected-revisions/{entry['revision_id']}", headers=editor)
    assert r.status_code == 404
    assert r.json()["code"] == "affected_revision_not_found"


def test_eco_affected_revisions_locked_after_approval(client, editor, approver):
    part = create_part(client, editor, "Teil L")
    release_part(client, editor, approver, part["part_number"])
    ecr = _create_ecr(client, editor)
    _approve_ecr(client, editor, approver, ecr["number"])
    eco = _create_eco(client, editor, ecr["number"])
    n = eco["number"]
    client.post(
        f"/api/v1/ecos/{n}/affected-revisions?direct=true",
        json={"part_number": part["part_number"]},
        headers=editor,
    )
    r = client.post(
        f"/api/v1/ecos/{n}/transition?direct=true",
        json={"to_status": "approved", "reason": "freigeben"},
        headers=approver,
    )
    assert r.status_code == 200

    r = client.post(
        f"/api/v1/ecos/{n}/affected-revisions?direct=true",
        json={"part_number": part["part_number"], "revision": "01"},
        headers=editor,
    )
    assert r.status_code == 409
    assert r.json()["code"] == "eco_not_draft"


def test_eco_transition_workflow(client, editor, approver, viewer):
    ecr = _create_ecr(client, editor)
    _approve_ecr(client, editor, approver, ecr["number"])
    eco = _create_eco(client, editor, ecr["number"])
    n = eco["number"]

    r = client.post(
        f"/api/v1/ecos/{n}/transition?direct=true",
        json={"to_status": "executed", "reason": "ueberspringen"},
        headers=approver,
    )
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_transition"

    r = client.post(
        f"/api/v1/ecos/{n}/transition?direct=true",
        json={"to_status": "approved", "reason": "editor darf nicht"},
        headers=editor,
    )
    assert r.status_code == 403

    r = client.post(
        f"/api/v1/ecos/{n}/transition?direct=true",
        json={"to_status": "approved", "reason": "ok"},
        headers=approver,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    r = client.post(
        f"/api/v1/ecos/{n}/transition?direct=true",
        json={"to_status": "executed", "reason": "umgesetzt"},
        headers=approver,
    )
    assert r.status_code == 200
    assert client.get(f"/api/v1/ecos/{n}", headers=viewer).json()["status"] == "executed"


def test_eco_transition_via_confirmation_token(client, editor, approver):
    ecr = _create_ecr(client, editor)
    _approve_ecr(client, editor, approver, ecr["number"])
    eco = _create_eco(client, editor, ecr["number"])
    r = client.post(
        f"/api/v1/ecos/{eco['number']}/transition",
        json={"to_status": "approved", "reason": "agent schlaegt vor"},
        headers=approver,
    )
    assert r.status_code == 202
    conf_id = r.json()["confirmation_id"]
    r = client.post(f"/api/v1/confirmations/{conf_id}/approve", headers=approver)
    assert r.status_code == 200
    assert (
        client.get(f"/api/v1/ecos/{eco['number']}", headers=editor).json()["status"] == "approved"
    )


def test_eco_add_affected_via_confirmation_token(client, editor, approver):
    part = create_part(client, editor, "Teil C")
    release_part(client, editor, approver, part["part_number"])
    ecr = _create_ecr(client, editor)
    _approve_ecr(client, editor, approver, ecr["number"])
    eco = _create_eco(client, editor, ecr["number"])
    r = client.post(
        f"/api/v1/ecos/{eco['number']}/affected-revisions",
        json={"part_number": part["part_number"], "revision": "01"},
        headers=editor,
    )
    assert r.status_code == 202
    conf_id = r.json()["confirmation_id"]
    r = client.post(f"/api/v1/confirmations/{conf_id}/approve", headers=editor)
    assert r.status_code == 200, r.text
    affected = client.get(f"/api/v1/ecos/{eco['number']}", headers=editor).json()["affected"]
    assert len(affected) == 1
    assert affected[0]["part_number"] == part["part_number"]


def test_viewer_can_read_but_not_write(client, editor, viewer):
    ecr = _create_ecr(client, editor)
    r = client.get("/api/v1/ecrs", headers=viewer)
    assert r.status_code == 200
    assert len(r.json()) == 1
    r = client.get(f"/api/v1/ecrs/{ecr['number']}", headers=viewer)
    assert r.status_code == 200

    r = client.post("/api/v1/ecrs?direct=true", json={"description": "x"}, headers=viewer)
    assert r.status_code == 403
    r = client.post(
        f"/api/v1/ecrs/{ecr['number']}/transition?direct=true",
        json={"to_status": "in_review", "reason": "x"},
        headers=viewer,
    )
    assert r.status_code == 403


def test_eco_not_found(client, editor):
    r = client.get("/api/v1/ecos/ECO-99999", headers=editor)
    assert r.status_code == 404
    assert r.json()["code"] == "eco_not_found"


def test_create_eco_unknown_ecr_is_404(client, editor):
    r = client.post("/api/v1/ecrs/ECR-99999/ecos?direct=true", json={}, headers=editor)
    assert r.status_code == 404
    assert r.json()["code"] == "ecr_not_found"


def test_proposed_create_eco_revalidates_at_approval(client, editor):
    """A confirmation proposed while the ECR is still open must fail at
    execution time (409), not silently create the ECO."""
    ecr = _create_ecr(client, editor)
    r = client.post(f"/api/v1/ecrs/{ecr['number']}/ecos", json={}, headers=editor)
    assert r.status_code == 202
    conf_id = r.json()["confirmation_id"]
    r = client.post(f"/api/v1/confirmations/{conf_id}/approve", headers=editor)
    assert r.status_code == 409
    assert r.json()["code"] == "ecr_not_approved"
    assert client.get("/api/v1/ecos", headers=editor).json() == []


def test_delete_affected_locked_after_approval(client, editor, approver):
    part = create_part(client, editor, "Teil D")
    release_part(client, editor, approver, part["part_number"])
    ecr = _create_ecr(client, editor)
    _approve_ecr(client, editor, approver, ecr["number"])
    eco = _create_eco(client, editor, ecr["number"])
    r = client.post(
        f"/api/v1/ecos/{eco['number']}/affected-revisions?direct=true",
        json={"part_number": part["part_number"]},
        headers=editor,
    )
    assert r.status_code == 201
    rev_id = r.json()["revision_id"]
    r = client.post(
        f"/api/v1/ecos/{eco['number']}/transition?direct=true",
        json={"to_status": "approved", "reason": "ok"},
        headers=approver,
    )
    assert r.status_code == 200
    r = client.delete(f"/api/v1/ecos/{eco['number']}/affected-revisions/{rev_id}", headers=editor)
    assert r.status_code == 409
    assert r.json()["code"] == "eco_not_draft"
