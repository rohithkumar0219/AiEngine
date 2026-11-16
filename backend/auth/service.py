
import sqlite3
import uuid

from datetime import timedelta
from typing import Optional

from auth import database
from auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
    utc_now,
    utc_iso,
    REFRESH_TOKEN_DAYS,
)


def validate_admin_email(email: str) -> str:
    email = email.strip().lower()

    if len(email) > 254 or "@" not in email:
        raise ValueError("Enter a valid email address.")

    return email


def provision_admin(
    email: str,
    password: str,
    tenant_id: str,
) -> str:
    email = validate_admin_email(email)
    tenant_id = tenant_id.strip()

    if not tenant_id or len(tenant_id) > 128:
        raise ValueError("A valid tenant ID is required.")

    password_hash = hash_password(password)
    admin_id = str(uuid.uuid4())
    now = utc_iso(utc_now())

    try:
        database.create_admin(
            admin_id=admin_id,
            email=email,
            password_hash=password_hash,
            tenant_id=tenant_id,
            created_at=now,
        )
    except sqlite3.IntegrityError:
        raise ValueError(
            "An administrator with this email already exists."
        )

    database.write_audit_log(
        event="admin_provisioned",
        admin_id=admin_id,
        created_at=now,
        details="Provisioned through local CLI.",
    )

    return admin_id


def authenticate_admin(
    email: str,
    password: str,
) -> Optional[dict]:
    try:
        email = validate_admin_email(email)
    except (ValueError, AttributeError):
        return None

    admin = database.get_admin_by_email(email)

    if not admin:
        return None

    if not admin["is_active"] or admin["role"] != "tenant_admin":
        return None

    if not verify_password(password, admin["password_hash"]):
        return None

    now = utc_iso(utc_now())

    database.update_last_login(admin["id"], now)

    database.write_audit_log(
        event="admin_login",
        admin_id=admin["id"],
        created_at=now,
    )

    return admin


def issue_token_pair(admin: dict) -> dict:
    access_token = create_access_token(admin)

    raw_refresh, refresh_hash, refresh_id = create_refresh_token()

    now = utc_now()
    expires = now + timedelta(days=REFRESH_TOKEN_DAYS)

    database.store_refresh_token(
        token_id=refresh_id,
        admin_id=admin["id"],
        token_hash=refresh_hash,
        expires_at=utc_iso(expires),
        created_at=utc_iso(now),
    )

    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
        "expires_in": 900,
    }



def refresh_admin_session(raw_refresh_token: str) -> Optional[dict]:
    old_hash = hash_refresh_token(raw_refresh_token)

    now = utc_now()
    now_string = utc_iso(now)

    existing = database.get_refresh_token(old_hash)

    if not existing:
        return None

    # Reuse of a previously revoked token is suspicious.
    if existing["revoked_at"] is not None:
        database.revoke_admin_sessions_for_reuse(
            existing["admin_id"],
            now_string,
        )

        database.write_audit_log(
            event="refresh_token_reuse_detected",
            admin_id=existing["admin_id"],
            created_at=now_string,
        )
        return None

    new_raw, new_hash, new_id = create_refresh_token()

    expires = now + timedelta(days=REFRESH_TOKEN_DAYS)

    admin = database.rotate_refresh_token(
        old_token_hash=old_hash,
        new_token_id=new_id,
        new_token_hash=new_hash,
        new_expires_at=utc_iso(expires),
        now=now_string,
    )

    if not admin:
        return None

    database.write_audit_log(
        event="admin_token_refreshed",
        admin_id=admin["id"],
        created_at=now_string,
    )

    return {
        "access_token": create_access_token(admin),
        "refresh_token": new_raw,
        "token_type": "bearer",
        "expires_in": 900,
    }



def logout_admin(
    raw_refresh_token: str,
    authenticated_admin_id: str,
) -> bool:
    token = database.get_refresh_token(
        hash_refresh_token(raw_refresh_token)
    )

    if not token:
        return False

    if token["admin_id"] != authenticated_admin_id:
        return False

    now = utc_iso(utc_now())

    return database.revoke_refresh_token_by_hash(
        hash_refresh_token(raw_refresh_token),
        now,
    )

def get_active_admin(admin_id: str) -> Optional[dict]:
    admin = database.get_admin_by_id(admin_id)

    if not admin or not admin["is_active"]:
        return None

    if admin["role"] != "tenant_admin":
        return None

    return admin
