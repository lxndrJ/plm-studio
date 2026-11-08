from typing import Annotated

import jwt
from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy import select

from app.core import security
from app.core.deps import CurrentUser, DbSession, require_roles
from app.core.errors import ConflictError, UnauthorizedError
from app.models.user import ROLES, User
from app.schemas.auth import CreateUserRequest, LoginRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: DbSession, response: Response):
    user = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    if user is None or not security.verify_password(body.password, user.password_hash):
        raise UnauthorizedError("invalid credentials")
    access = security.create_access_token(user.email, user.role)
    refresh = security.create_refresh_token(user.email)
    response.set_cookie(
        key="refresh_token",
        value=refresh,
        httponly=True,
        samesite="lax",
        secure=False,  # set True behind HTTPS (Caddy/Traefik in front)
        max_age=30 * 24 * 3600,
    )
    return TokenResponse(access_token=access, role=user.role, email=user.email)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    db: DbSession,
    refresh_token: Annotated[str | None, Cookie()] = None,
):
    if not refresh_token:
        raise UnauthorizedError("missing refresh cookie")
    try:
        payload = security.decode_token(refresh_token)
    except jwt.PyJWTError:
        raise UnauthorizedError("invalid or expired refresh token")
    if payload.get("type") != "refresh":
        raise UnauthorizedError("not a refresh token")
    user = db.execute(select(User).where(User.email == payload.get("sub"))).scalar_one_or_none()
    if user is None:
        raise UnauthorizedError("user no longer exists")
    access = security.create_access_token(user.email, user.role)
    return TokenResponse(access_token=access, role=user.role, email=user.email)


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("refresh_token")
    return {"status": "logged_out"}


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser):
    return UserResponse(id=str(user.id), email=user.email, role=user.role)


@router.post(
    "/users",
    response_model=UserResponse,
    dependencies=[Depends(require_roles("admin"))],
)
def create_user(body: CreateUserRequest, db: DbSession):
    from app.core.errors import ValidationError

    if body.role not in ROLES:
        raise ValidationError(f"role must be one of {ROLES}", code="invalid_role")
    existing = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    if existing:
        raise ConflictError("user with this email already exists", code="user_exists")
    user = User(email=body.email, password_hash=security.hash_password(body.password), role=body.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserResponse(id=str(user.id), email=user.email, role=user.role)
