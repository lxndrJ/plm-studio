"""Token revocation (denylist by jti) plus password-change invalidation.

Logout puts the token's jti into revoked_tokens; every authenticated request
checks it. A password change/reset instead bumps users.password_changed_at and
all tokens issued before that (iat < password_changed_at) are rejected, which
invalidates every session of that user at once. Expired denylist rows are
purged opportunistically on logout.
"""

from datetime import UTC, datetime

import jwt
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core import security
from app.models.revoked_token import RevokedToken
from app.models.user import User


def is_revoked(db: Session, jti: str) -> bool:
    return (
        db.execute(select(RevokedToken.id).where(RevokedToken.jti == jti)).scalar_one_or_none()
        is not None
    )


def revoke_payload(db: Session, payload: dict) -> bool:
    """Denylist the payload's jti; returns True if a new row was added."""
    jti = payload.get("jti")
    if not jti or is_revoked(db, jti):
        return False
    user = db.execute(select(User).where(User.email == payload.get("sub"))).scalar_one_or_none()
    db.add(
        RevokedToken(
            jti=jti,
            token_type=payload.get("type", "access"),
            user_id=user.id if user else None,
            expires_at=datetime.fromtimestamp(payload["exp"], UTC),
        )
    )
    return True


def revoke_bearer(db: Session, authorization: str | None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        return
    try:
        payload = security.decode_token(authorization.removeprefix("Bearer ").strip())
    except jwt.PyJWTError:
        return
    revoke_payload(db, payload)


def purge_expired(db: Session) -> None:
    db.execute(delete(RevokedToken).where(RevokedToken.expires_at < datetime.now(UTC)))


def token_invalidated_by_password_change(user: User, payload: dict) -> bool:
    pwd = payload.get("pwd")
    if pwd is None:
        return False  # token predates the fingerprint claim (deploy grace period)
    return pwd != security.password_fingerprint(user.password_hash)
