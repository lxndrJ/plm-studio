"""M-logs: GET /admin/logs exposes the in-memory ring buffer (admin only)."""

import logging


def test_admin_logs_requires_admin(client, viewer, admin):
    assert client.get("/api/v1/admin/logs").status_code == 401
    assert client.get("/api/v1/admin/logs", headers=viewer).status_code == 403


def test_admin_logs_returns_ring_buffer_and_filters_level(client, admin):
    logging.getLogger("test.logs").warning("log-marker-abc")
    r = client.get("/api/v1/admin/logs?lines=50&level=INFO", headers=admin)
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "api"
    messages = [line["message"] for line in body["logs"]]
    assert "log-marker-abc" in messages
    # newest first
    assert body["logs"][0]["ts"] >= body["logs"][-1]["ts"]
    r = client.get("/api/v1/admin/logs?lines=50&level=ERROR", headers=admin)
    assert "log-marker-abc" not in [line["message"] for line in r.json()["logs"]]
