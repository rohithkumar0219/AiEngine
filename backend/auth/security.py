
import os
import hashlib
import secrets
import uuid

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import jwt

from argon2 import PasswordHasher
from argon2.exceptions import (
    VerifyMismatchError,
    VerificationError,
    InvalidHashError,
)

# ── Environment configuration ──────────────────────────────────

_BACKEND_ROOT = Path(__file__).resolve().parent.parent

for _env_file in (
    _BACKEND_ROOT / ".env",
    _BACKEND_ROOT.parent / ".env",
):
    if _env_file.is_file():
        load_dotenv(_env_file, override=False)

# ── JWT configuration ──────────────────────────────────────────

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ISSUER = os.getenv("JWT_ISSUER", "iryax-auth")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "iryax-api")
JWT_ALGORITHM = "HS256"

ACCESS_TOKEN_MINUTES = 15
REFRESH_TOKEN_DAYS = 7

# ── Password hashing ───────────────────────────────────────────

password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
)

# ── Time utilities ─────────────────────────────────────────────

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


# ── Password security ──────────────────────────────────────────

def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters.")

    if len(password) > 1024:
        raise ValueError("Password is too long.")

    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (
        VerifyMismatchError,
        VerificationError,
        InvalidHashError,
        TypeError,
    ):
        return False


# ── JWT validation and generation ──────────────────────────────

def validate_jwt_configuration() -> None:
    if len(JWT_SECRET_KEY.encode("utf-8")) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY must contain at least 32 bytes."
        )

    if not JWT_ISSUER or not JWT_AUDIENCE:
        raise RuntimeError(
            "JWT_ISSUER and JWT_AUDIENCE must be configured."
        )


def create_access_token(admin: dict[str, Any]) -> str:
    validate_jwt_configuration()

    now = utc_now()

    claims = {
        "sub": admin["id"],
        "tenant_id": admin["tenant_id"],
        "role": "tenant_admin",
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }

    return jwt.encode(
        claims,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


# ── Refresh token generation ───────────────────────────────────

def create_refresh_token() -> tuple[str, str, str]:
    """Return raw token, SHA-256 hash, and token ID."""

    raw_token = secrets.token_urlsafe(48)

    token_hash = hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()

    token_id = str(uuid.uuid4())

    return raw_token, token_hash, token_id


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()
