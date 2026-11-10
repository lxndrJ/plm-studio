"""M8: user management, token revocation, login rate limiting."""

import uuid

import pytest
import sqlalchemy as sa

from app.core import security
from app.guardrails import rate_limit
from app.models.audit import AuditLog
from app.models.user import User


@pytest.fixture(autouse=True)
def _reset_limiter():
    rate_limit.reset()
    yield
    rate_limit.reset()


def _user_id(db, email: str):
    return db.execute(sa.select(User.id).where(User.email == email)).scalar_one()


def _audit(db, *, entity_type: str, action: str):
    return (
        db.execute(
            sa.select(AuditLog).where(
                AuditLog.entity_type == entity_type, AuditLog.action == action
            )
        )
        .scalars()
        .all()
    )


# --- list users / me -------------------------------------------------------


def test_list_users_requires_admin(client, viewer, editor, admin):
    for h in (viewer, editor):
        r = client.get("/api/v1/auth/users", headers=h)
        assert r.status_code == 403
    r = client.get("/api/v1/auth/users", headers=admin)
    assert r.status_code == 200
    emails = {u["email"] for u in r.json()}
    assert {
        "admin@example.com",
        "editor@example.com",
        "approver@example.com",
        "viewer@example.com",
    } <= emails
    assert all(u["is_active"] is True for u in r.json())


def test_me_includes_is_active(client, editor):
    r = client.get("/api/v1/auth/me", headers=editor)
    assert r.status_code == 200
    assert r.json()["is_active"] is True


# --- admin updates users ----------------------------------------------------


def test_admin_role_change_takes_effect_immediately(client, db, admin, approver):
    uid = _user_id(db, "approver@example.com")
    r = client.patch(f"/api/v1/auth/users/{uid}", json={"role": "viewer"}, headers=admin)
    assert r.status_code == 200
    assert r.json()["role"] == "viewer"
    # role is read from the DB, not the JWT: the old token now has viewer rights
    r = client.post(
        "/api/v1/parts?direct=true", json={"name": "x", "class_code": "MECH"}, headers=approver
    )
    assert r.status_code == 403
    entries = _audit(db, entity_type="user", action="update")
    assert len(entries) == 1
    assert entries[0].entity_id == str(uid)
    assert entries[0].old_values == {"role": "approver", "is_active": True}
    assert entries[0].new_values["role"] == "viewer"


def test_admin_can_deactivate_and_reactivate_user(client, db, admin, editor):
    uid = _user_id(db, "editor@example.com")
    r = client.patch(f"/api/v1/auth/users/{uid}", json={"is_active": False}, headers=admin)
    assert r.status_code == 200
    assert r.json()["is_active"] is False
    # existing token is rejected ...
    r = client.get("/api/v1/auth/me", headers=editor)
    assert r.status_code == 401
    assert r.json()["code"] == "user_inactive"
    # ... and login is refused
    r = client.post(
        "/api/v1/auth/login", json={"email": "editor@example.com", "password": "editor-pw"}
    )
    assert r.status_code == 403
    assert r.json()["code"] == "user_inactive"
    # reactivation restores access
    r = client.patch(f"/api/v1/auth/users/{uid}", json={"is_active": True}, headers=admin)
    assert r.status_code == 200
    assert client.get("/api/v1/auth/me", headers=editor).status_code == 200


def test_admin_cannot_deactivate_or_demote_self(client, db, admin):
    uid = _user_id(db, "admin@example.com")
    r = client.patch(f"/api/v1/auth/users/{uid}", json={"is_active": False}, headers=admin)
    assert r.status_code == 409
    assert r.json()["code"] == "self_lockout"
    r = client.patch(f"/api/v1/auth/users/{uid}", json={"role": "viewer"}, headers=admin)
    assert r.status_code == 409
    assert r.json()["code"] == "self_lockout"


def test_update_user_validation(client, db, admin, editor):
    uid = _user_id(db, "editor@example.com")
    r = client.patch(f"/api/v1/auth/users/{uid}", json={"role": "superuser"}, headers=admin)
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_role"
    r = client.patch(f"/api/v1/auth/users/{uuid.uuid4()}", json={"role": "viewer"}, headers=admin)
    assert r.status_code == 404
    r = client.patch(f"/api/v1/auth/users/{uid}", json={}, headers=admin)
    assert r.status_code == 422
    r = client.patch(f"/api/v1/auth/users/{uid}", json={"role": "editor"}, headers=editor)
    assert r.status_code == 403


# --- password change / reset -------------------------------------------------


def test_change_password_invalidates_old_tokens(client, db, editor):
    r = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "wrong", "new_password": "new-pw-123"},
        headers=editor,
    )
    assert r.status_code == 401
    r = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "editor-pw", "new_password": "new-pw-123"},
        headers=editor,
    )
    assert r.status_code == 200
    # the token used for the change is invalidated as well
    r = client.get("/api/v1/auth/me", headers=editor)
    assert r.status_code == 401
    assert r.json()["code"] == "token_invalidated"
    # old password no longer works, new one does
    r = client.post(
        "/api/v1/auth/login", json={"email": "editor@example.com", "password": "editor-pw"}
    )
    assert r.status_code == 401
    r = client.post(
        "/api/v1/auth/login", json={"email": "editor@example.com", "password": "new-pw-123"}
    )
    assert r.status_code == 200
    # audit entry exists but never contains password material
    entries = _audit(db, entity_type="user", action="password_change")
    assert len(entries) == 1
    assert entries[0].old_values is None and entries[0].new_values is None


def test_admin_reset_password(client, db, admin, editor):
    uid = _user_id(db, "editor@example.com")
    r = client.post(
        f"/api/v1/auth/users/{uid}/reset-password",
        json={"new_password": "reset-pw-9"},
        headers=admin,
    )
    assert r.status_code == 200
    r = client.get("/api/v1/auth/me", headers=editor)
    assert r.status_code == 401
    assert r.json()["code"] == "token_invalidated"
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "editor@example.com", "password": "editor-pw"}
        ).status_code
        == 401
    )
    r = client.post(
        "/api/v1/auth/login", json={"email": "editor@example.com", "password": "reset-pw-9"}
    )
    assert r.status_code == 200
    # non-admin cannot reset (fresh token with the new password)
    editor2 = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.post(
        f"/api/v1/auth/users/{uid}/reset-password",
        json={"new_password": "reset-pw-9"},
        headers=editor2,
    )
    assert r.status_code == 403
    assert len(_audit(db, entity_type="user", action="password_reset")) == 1


def test_create_user_writes_audit_without_password(client, db, admin):
    r = client.post(
        "/api/v1/auth/users",
        json={"email": "audit@example.com", "password": "pw12345", "role": "viewer"},
        headers=admin,
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is True
    entries = _audit(db, entity_type="user", action="create")
    assert len(entries) == 1
    assert entries[0].new_values["email"] == "audit@example.com"
    assert "password" not in str(entries[0].new_values)


# --- logout revokes tokens ----------------------------------------------------


def test_logout_revokes_access_and_refresh_token(client):
    r = client.post(
        "/api/v1/auth/login", json={"email": "viewer@example.com", "password": "viewer-pw"}
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    refresh_cookie = r.cookies.get("refresh_token")
    assert refresh_cookie
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/parts", headers=headers).status_code == 200
    r = client.post(
        "/api/v1/auth/logout", headers=headers, cookies={"refresh_token": refresh_cookie}
    )
    assert r.status_code == 200
    r = client.get("/api/v1/parts", headers=headers)
    assert r.status_code == 401
    assert r.json()["code"] == "token_revoked"
    r = client.post("/api/v1/auth/refresh", cookies={"refresh_token": refresh_cookie})
    assert r.status_code == 401
    assert r.json()["code"] == "token_revoked"


def test_logout_without_tokens_still_works(client):
    r = client.post("/api/v1/auth/logout")
    assert r.status_code == 200


# --- login rate limiting -------------------------------------------------------


def test_login_rate_limited_after_failures_then_recovers(client, monkeypatch):
    email = "viewer@example.com"
    for _ in range(5):
        r = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
        assert r.status_code == 401
    # even the correct password is refused while limited
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "viewer-pw"})
    assert r.status_code == 429
    assert r.json()["code"] == "rate_limited"
    assert int(r.headers["retry-after"]) >= 1
    # after the window passes, login works again
    future = rate_limit._now() + 120
    monkeypatch.setattr(rate_limit, "_now", lambda: future)
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "viewer-pw"})
    assert r.status_code == 200


def test_successful_login_clears_failure_counter(client):
    email = "approver@example.com"
    for _ in range(4):
        client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "approver-pw"})
    assert r.status_code == 200
    for _ in range(4):
        client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "approver-pw"})
    assert r.status_code == 200


def test_rate_limit_is_scoped_per_email(client):
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"email": "viewer@example.com", "password": "wrong"})
    r = client.post("/api/v1/auth/login", json={"email": "viewer@example.com", "password": "x"})
    assert r.status_code == 429
    # a different email is not affected
    r = client.post(
        "/api/v1/auth/login", json={"email": "editor@example.com", "password": "editor-pw"}
    )
    assert r.status_code == 200


# --- M10: agent service account bootstrap --------------------------------------


def test_bootstrap_agent_user_creates_editor_when_configured(db):
    from app.core.config import Settings
    from app.main import bootstrap_agent_user

    s = Settings(PLM_AGENT_EMAIL="agent@example.com", PLM_AGENT_PASSWORD="agent-pw-1")
    u = bootstrap_agent_user(db, s)
    assert u is not None
    assert u.role == "editor"  # never approver: the agent must not self-approve
    assert u.is_active is True
    # idempotent
    again = bootstrap_agent_user(db, s)
    assert again.id == u.id
    count = db.execute(
        sa.select(sa.func.count(User.id)).where(User.email == "agent@example.com")
    ).scalar_one()
    assert count == 1
    # login works with the configured password
    assert security.verify_password("agent-pw-1", u.password_hash)


def test_bootstrap_agent_user_noop_without_env(db):
    from app.core.config import Settings
    from app.main import bootstrap_agent_user

    assert bootstrap_agent_user(db, Settings(PLM_AGENT_EMAIL="", PLM_AGENT_PASSWORD="")) is None
