from typing import Annotated

import jwt
from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.models.user import User

ROLE_RANK = {"viewer": 1, "editor": 2, "approver": 3, "admin": 4}

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        raise UnauthorizedError("invalid or expired token")
    if payload.get("type") != "access":
        raise UnauthorizedError("not an access token")
    user = db.query(User).filter(User.email == payload.get("sub")).first()
    if user is None:
        raise UnauthorizedError("user no longer exists")
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
