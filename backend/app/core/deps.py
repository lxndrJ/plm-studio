from typing import Annotated

import jwt
from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.guardrails.revocation import is_revoked, token_invalidated_by_password_change
from app.models.user import User

ROLE_RANK = {"viewer": 1, "editor": 2, "approver": 3, "admin": 4}

DbSession = Annotated[Session, Depends(get_db)]


def decode_access_payload(db: DbSession, token: str) -> dict:
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        raise UnauthorizedError("invalid or expired token")
    if payload.get("type") != "access":
        raise UnauthorizedError("not an access token")
    jti = payload.get("jti")
    if jti is not None and is_revoked(db, jti):
        raise UnauthorizedError("token has been revoked", code="token_revoked")
    return payload


def get_current_user(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_access_payload(db, token)
    user = db.query(User).filter(User.email == payload.get("sub")).first()
    if user is None:
        raise UnauthorizedError("user no longer exists")
    if not user.is_active:
        raise UnauthorizedError("account is deactivated", code="user_inactive")
    if token_invalidated_by_password_change(user, payload):
        raise UnauthorizedError("token invalidated by password change", code="token_invalidated")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: str):
    def checker(user: CurrentUser) -> User:
        if ROLE_RANK.get(user.role, 0) < min(ROLE_RANK.get(r, 99) for r in roles):
            raise ForbiddenError(
                f"role '{user.role}' not sufficient, requires one of: {', '.join(roles)}",
                code="insufficient_role",
            )
        return user

    return checker


def role_allows(user_role: str, required_role: str) -> bool:
    return ROLE_RANK.get(user_role, 0) >= ROLE_RANK.get(required_role, 99)
