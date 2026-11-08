import os
import tempfile

os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(tempfile.mkdtemp(prefix="plm-test-"), "test.db"))
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "admin-pw")
os.environ.setdefault("STORAGE_DIR", tempfile.mkdtemp(prefix="plm-storage-"))

import pytest
from fastapi.testclient import TestClient

from app.core import security
from app.core.db import SessionLocal, engine
from app.main import app
from app.models import Base
from app.models.user import User
from app.services.seed import seed_all

USERS = {
    "admin": ("admin@example.com", "admin-pw", "admin"),
    "editor": ("editor@example.com", "editor-pw", "editor"),
    "approver": ("approver@example.com", "approver-pw", "approver"),
    "viewer": ("viewer@example.com", "viewer-pw", "viewer"),
}


def _reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_all(db)
        for email, password, role in USERS.values():
            db.add(User(email=email, password_hash=security.hash_password(password), role=role))
        db.commit()
    finally:
        db.close()


@pytest.fixture()
def client():
    _reset_db()
    with TestClient(app) as c:
        yield c
    _reset_db()


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def login(client, key: str) -> dict:
    email, password, _ = USERS[key]
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def admin(client):
    return login(client, "admin")


@pytest.fixture()
def editor(client):
    return login(client, "editor")


@pytest.fixture()
def approver(client):
    return login(client, "approver")


@pytest.fixture()
def viewer(client):
    return login(client, "viewer")


def create_part(client, headers, name, class_code="MECH", part_type="part", **extra):
    payload = {"name": name, "class_code": class_code, "part_type": part_type, **extra}
    r = client.post("/api/v1/parts?direct=true", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()
