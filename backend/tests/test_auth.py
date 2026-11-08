from tests.conftest import login


def test_login_ok_and_me(client):
    headers = login(client, "editor")
    r = client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["role"] == "editor"


def test_login_wrong_password(client):
    r = client.post("/api/v1/auth/login", json={"email": "editor@example.com", "password": "nope"})
    assert r.status_code == 401


def test_refresh_via_cookie(client):
    r = client.post(
        "/api/v1/auth/login", json={"email": "viewer@example.com", "password": "viewer-pw"}
    )
    assert r.status_code == 200
    cookie = r.cookies.get("refresh_token")
    assert cookie
    r2 = client.post("/api/v1/auth/refresh", cookies={"refresh_token": cookie})
    assert r2.status_code == 200
    assert r2.json()["access_token"]


def test_unauthenticated_rejected(client):
    r = client.get("/api/v1/parts")
    assert r.status_code == 401


def test_viewer_cannot_create_part(client, viewer):
    r = client.post(
        "/api/v1/parts?direct=true",
        json={"name": "x", "class_code": "MECH"},
        headers=viewer,
    )
    assert r.status_code == 403


def test_admin_can_create_user(client, admin):
    r = client.post(
        "/api/v1/auth/users",
        json={"email": "new@example.com", "password": "pw12345", "role": "editor"},
        headers=admin,
    )
    assert r.status_code == 200
    assert r.json()["role"] == "editor"


def test_editor_cannot_create_user(client, editor):
    r = client.post(
        "/api/v1/auth/users",
        json={"email": "new@example.com", "password": "pw12345", "role": "viewer"},
        headers=editor,
    )
    assert r.status_code == 403
