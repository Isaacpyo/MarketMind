"""Password hashing and JWT helpers."""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
import jwt

Role = Literal["customer", "admin"]
_ALGORITHM = "HS256"


def _prehash(password: str) -> bytes:
    # bcrypt only reads the first 72 bytes; pre-hashing keeps long passphrases fully significant.
    return base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(password), password_hash.encode("ascii"))
    except ValueError:
        return False


def create_access_token(*, user_id: str, role: Role, secret: str, ttl_minutes: int) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=ttl_minutes),
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def decode_access_token(token: str, secret: str) -> dict[str, Any]:
    """Return the token claims, raising jwt.InvalidTokenError on any problem."""
    claims: dict[str, Any] = jwt.decode(
        token, secret, algorithms=[_ALGORITHM], options={"require": ["sub", "exp", "iat"]}
    )
    return claims
