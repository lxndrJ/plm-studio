"""M10: agent conversation persistence API (/api/v1/agent/conversations)."""

import uuid


def _create_conversation(client, headers, title="Chat 1"):
    r = client.post("/api/v1/agent/conversations", json={"title": title}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_conversations_require_auth(client):
    r = client.get("/api/v1/agent/conversations")
    assert r.status_code == 401
    r = client.post("/api/v1/agent/conversations", json={"title": "x"})
    assert r.status_code == 401


def test_create_list_get_conversation(client, editor):
    conv = _create_conversation(client, editor, "Gehaeuse-Chat")
    assert conv["title"] == "Gehaeuse-Chat"
    assert conv["created_by"]

    r = client.get("/api/v1/agent/conversations", headers=editor)
    assert r.status_code == 200
    assert [c["id"] for c in r.json()] == [conv["id"]]

    r = client.get(f"/api/v1/agent/conversations/{conv['id']}", headers=editor)
    assert r.status_code == 200
    assert r.json()["messages"] == []


def test_add_messages_and_read_back(client, editor):
    conv = _create_conversation(client, editor)
    r = client.post(
        f"/api/v1/agent/conversations/{conv['id']}/messages",
        json={"role": "user", "content": {"text": "Hallo"}},
        headers=editor,
    )
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "user"
    r = client.post(
        f"/api/v1/agent/conversations/{conv['id']}/messages",
        json={"role": "assistant", "content": {"text": "Hi!", "tool_calls": []}},
        headers=editor,
    )
    assert r.status_code == 201
    detail = client.get(f"/api/v1/agent/conversations/{conv['id']}", headers=editor).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][0]["content"] == {"text": "Hallo"}


def test_message_role_is_validated(client, editor):
    conv = _create_conversation(client, editor)
    r = client.post(
        f"/api/v1/agent/conversations/{conv['id']}/messages",
        json={"role": "hacker", "content": {}},
        headers=editor,
    )
    assert r.status_code == 422


def test_conversations_are_owner_scoped(client, editor, viewer):
    conv = _create_conversation(client, editor)
    r = client.get(f"/api/v1/agent/conversations/{conv['id']}", headers=viewer)
    assert r.status_code == 404
    assert r.json()["code"] == "conversation_not_found"
    r = client.post(
        f"/api/v1/agent/conversations/{conv['id']}/messages",
        json={"role": "user", "content": {}},
        headers=viewer,
    )
    assert r.status_code == 404
    r = client.get("/api/v1/agent/conversations", headers=viewer)
    assert r.json() == []
    r = client.get(f"/api/v1/agent/conversations/{uuid.uuid4()}", headers=editor)
    assert r.status_code == 404
