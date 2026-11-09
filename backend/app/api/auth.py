import uuid
from datetime import UTC, datetime
from typing import Annotated

import jwt
from fastapi import APIRouter, Cookie, Depends, Header, Request, Response
from sqlalchemy import select

from app.core import security
from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession, require_roles
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    TooManyRequestsError,
    UnauthorizedError,
    ValidationError,
)
from app.guardrails import rate_limit, revocation
from app.models.user import ROLES, User
from app.schemas.auth import (
    ChangePasswordRequest,
    CreateUserRequest,
    LoginRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    UserUpdateRequest,
)
from app.services import audit as audit_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _login_key(body: LoginRequest, request: Request) -> str:
    client = request.client.host if request.client else "unknown"
    return f"login:{body.email.lower()}:{client}"


def _user_response(u: User) -> UserResponse:
    return UserResponse(id=str(u.id), email=u.email, role=u.role, is_active=u.is_active)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: DbSession, response: Response):
    settings = get_settings()
    key = _login_key(body, request)
    retry = rate_limit.retry_after(
        key,
        limit=settings.LOGIN_RATE_LIMIT_ATTEMPTS,
        window=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )
    if retry:
        raise TooManyRequestsError(
            f"too many failed login attempts, retry in {retry}s",
            code="rate_limited",
            headers={"Retry-After": str(retry)},
        )
    user = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    if user is None or not security.verify_password(body.password, user.password_hash):
        rate_limit.register_failure(key)
        raise UnauthorizedError("invalid credentials")
    if not user.is_active:
        raise ForbiddenError("account is deactivated", code="user_inactive")
    rate_limit.clear(key)
    access = security.create_access_token(
        user.email, user.role, security.password_fingerprint(user.password_hash)
    )
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
    jti = payload.get("jti")
    if jti is not None and revocation.is_revoked(db, jti):
        raise UnauthorizedError("token has been revoked", code="token_revoked")
    user = db.execute(select(User).where(User.email == payload.get("sub"))).scalar_one_or_none()
    if user is None:
        raise UnauthorizedError("user no longer exists")
    if not user.is_active:
        raise ForbiddenError("account is deactivated", code="user_inactive")
    if revocation.token_invalidated_by_password_change(user, payload):
        raise UnauthorizedError("token invalidated by password change", code="token_invalidated")
    access = security.create_access_token(
        user.email, user.role, security.password_fingerprint(user.password_hash)
    )
    return TokenResponse(access_token=access, role=user.role, email=user.email)


@router.post("/logout")
def logout(
    response: Response,
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
    refresh_token: Annotated[str | None, Cookie()] = None,
):
    revoked = 0
    if authorization and authorization.startswith("Bearer "):
        try:
            payload = security.decode_token(authorization.removeprefix("Bearer ").strip())
            if revocation.revoke_payload(db, payload):
                revoked += 1
        except jwt.PyJWTError:
            pass
    if refresh_token:
        try:
            payload = security.decode_token(refresh_token)
            if revocation.revoke_payload(db, payload):
                revoked += 1
        except jwt.PyJWTError:
            pass
    revocation.purge_expired(db)
    db.commit()
    response.delete_cookie("refresh_token")
    return {"status": "logged_out", "revoked_tokens": revoked}


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser):
    return _user_response(user)


@router.get(
    "/users", response_model=list[UserResponse], dependencies=[Depends(require_roles("admin"))]
)
def list_users(db: DbSession):
    return [_user_response(u) for u in db.execute(select(User).order_by(User.email)).scalars()]


@router.post("/users", response_model=UserResponse)
def create_user(
    body: CreateUserRequest,
    db: DbSession,
    admin: Annotated[User, Depends(require_roles("admin"))],
):
    if body.role not in ROLES:
        raise ValidationError(f"role must be one of {ROLES}", code="invalid_role")
    existing = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    if existing:
        raise ConflictError("user with this email already exists", code="user_exists")
    user = User(
        email=body.email, password_hash=security.hash_password(body.password), role=body.role
    )
    db.add(user)
    db.flush()
    audit_service.log_change(
        db,
        entity_type="user",
        entity_id=str(user.id),
        action="create",
        user_id=admin.id,
        new_values={"email": user.email, "role": user.role},
        reason=f"user created by {admin.email}",
    )
    db.commit()
    db.refresh(user)
    return _user_response(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: uuid.UUID,
    body: UserUpdateRequest,
    db: DbSession,
    admin: Annotated[User, Depends(require_roles("admin"))],
):
    target = db.get(User, user_id)
    if target is None:
        raise NotFoundError("user not found", code="user_not_found")
    old = {"role": target.role, "is_active": target.is_active}
    new = dict(old)
    if body.role is not None:
        if body.role not in ROLES:
            raise ValidationError(f"role must be one of {ROLES}", code="invalid_role")
        if target.id == admin.id and body.role != target.role:
            raise ConflictError("cannot change own role", code="self_lockout")
        target.role = body.role
        new["role"] = body.role
    if body.is_active is not None:
        if target.id == admin.id and body.is_active is False:
            raise ConflictError("cannot deactivate own account", code="self_lockout")
        target.is_active = body.is_active
        new["is_active"] = body.is_active
    if new == old:
        raise ValidationError("no fields to update", code="empty_update")
    audit_service.log_change(
        db,
        entity_type="user",
        entity_id=str(target.id),
        action="update",
        user_id=admin.id,
        old_values=old,
        new_values=new,
        reason=f"user updated by {admin.email}",
    )
    db.commit()
    db.refresh(target)
    return _user_response(target)


@router.post("/users/{user_id}/reset-password")
def reset_password(
    user_id: uuid.UUID,
    body: ResetPasswordRequest,
    db: DbSession,
    admin: Annotated[User, Depends(require_roles("admin"))],
):
    target = db.get(User, user_id)
    if target is None:
        raise NotFoundError("user not found", code="user_not_found")
    target.password_hash = security.hash_password(body.new_password)
    target.password_changed_at = datetime.now(UTC)
    audit_service.log_change(
        db,
        entity_type="user",
        entity_id=str(target.id),
        action="password_reset",
        user_id=admin.id,
        reason=f"password reset by {admin.email} for {target.email}",
    )
    db.commit()
    return {"status": "password_reset"}


@router.post("/change-password")
def change_password(body: ChangePasswordRequest, db: DbSession, user: CurrentUser):
    if not security.verify_password(body.old_password, user.password_hash):
        raise UnauthorizedError("invalid credentials", code="invalid_credentials")
    user.password_hash = security.hash_password(body.new_password)
    user.password_changed_at = datetime.now(UTC)
    audit_service.log_change(
        db,
        entity_type="user",
        entity_id=str(user.id),
        action="password_change",
        user_id=user.id,
        reason="self-service password change",
    )
    db.commit()
    return {"status": "password_changed"}
