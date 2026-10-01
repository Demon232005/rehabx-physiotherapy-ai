"""Authentication and password utilities.

JWT-based auth with bcrypt password hashing. Never store plaintext passwords.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings


RESET_TOKEN_EXPIRE_MINUTES = 15


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "jti": uuid.uuid4().hex,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])


def create_password_reset_token(email: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": email,
        "iat": now,
        "exp": now + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES),
        "jti": uuid.uuid4().hex,
        "purpose": "password_reset",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def verify_password_reset_token(token: str) -> str:
    settings = get_settings()
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("purpose") != "password_reset":
        raise jwt.InvalidTokenError("Invalid token purpose")
    return str(payload["sub"])
