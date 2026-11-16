
import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, Iterator, Any

BACKEND_DIR = Path(__file__).resolve().parent.parent

DATABASE_PATH = Path(
    os.getenv(
        "AUTH_DATABASE_PATH",
        str(BACKEND_DIR / "data" / "auth.db"),
    )
).expanduser().resolve()


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Open a SQLite connection with safe defaults."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=10,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    """Create authentication tables and indexes."""
    with get_connection() as connection:
        connection.execute("PRAGMA journal_mode = WAL")

        connection.executescript("""
            CREATE TABLE IF NOT EXISTS admins (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role = 'tenant_admin'),
                is_active INTEGER NOT NULL DEFAULT 1
                    CHECK (is_active IN (0, 1)),
                created_at TEXT NOT NULL,
                last_login_at TEXT
            );

            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id TEXT PRIMARY KEY,
                admin_id TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                revoked_at TEXT,
                replaced_by TEXT,
                FOREIGN KEY (admin_id)
                    REFERENCES admins(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS
                idx_refresh_tokens_admin
                ON refresh_tokens(admin_id);

            CREATE INDEX IF NOT EXISTS
                idx_refresh_tokens_expiry
                ON refresh_tokens(expires_at);

            CREATE TABLE IF NOT EXISTS auth_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id TEXT,
                event TEXT NOT NULL,
                ip_address TEXT,
                details TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (admin_id)
                    REFERENCES admins(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS
                idx_auth_audit_admin
                ON auth_audit_logs(admin_id, created_at);
        """)


def create_admin(
    admin_id: str,
    email: str,
    password_hash: str,
    tenant_id: str,
    created_at: str,
) -> None:
    """Create a provisioned TENANT_ADMIN account."""
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO admins (
                id, email, password_hash, tenant_id,
                role, is_active, created_at
            )
            VALUES (?, ?, ?, ?, 'tenant_admin', 1, ?)
            """,
            (
                admin_id,
                email.strip().lower(),
                password_hash,
                tenant_id,
                created_at,
            ),
        )


def get_admin_by_email(email: str) -> Optional[dict[str, Any]]:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM admins WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()

    return dict(row) if row else None


def get_admin_by_id(admin_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM admins WHERE id = ?",
            (admin_id,),
        ).fetchone()

    return dict(row) if row else None


def update_last_login(admin_id: str, timestamp: str) -> None:
    with get_connection() as connection:
        connection.execute(
            "UPDATE admins SET last_login_at = ? WHERE id = ?",
            (timestamp, admin_id),
        )


def store_refresh_token(
    token_id: str,
    admin_id: str,
    token_hash: str,
    expires_at: str,
    created_at: str,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO refresh_tokens (
                id, admin_id, token_hash, expires_at, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (token_id, admin_id, token_hash, expires_at, created_at),
        )


def get_refresh_token(token_hash: str) -> Optional[dict[str, Any]]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT * FROM refresh_tokens
            WHERE token_hash = ?
            """,
            (token_hash,),
        ).fetchone()

    return dict(row) if row else None


def revoke_refresh_token(
    token_id: str,
    revoked_at: str,
    replaced_by: Optional[str] = None,
) -> bool:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE refresh_tokens
            SET revoked_at = ?, replaced_by = ?
            WHERE id = ? AND revoked_at IS NULL
            """,
            (revoked_at, replaced_by, token_id),
        )

    return cursor.rowcount == 1


def revoke_all_admin_refresh_tokens(
    admin_id: str,
    revoked_at: str,
) -> int:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE refresh_tokens
            SET revoked_at = ?
            WHERE admin_id = ? AND revoked_at IS NULL
            """,
            (revoked_at, admin_id),
        )

    return cursor.rowcount


def write_audit_log(
    event: str,
    created_at: str,
    admin_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[str] = None,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO auth_audit_logs (
                admin_id, event, ip_address, details, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (admin_id, event, ip_address, details, created_at),
        )



def rotate_refresh_token(
    old_token_hash: str,
    new_token_id: str,
    new_token_hash: str,
    new_expires_at: str,
    now: str,
) -> Optional[dict]:
    """
    Atomically consume an existing refresh token and issue its replacement.
    A refresh token can only be used once.
    """
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")

        row = connection.execute(
            """
            SELECT
                rt.id AS token_id,
                rt.admin_id,
                rt.expires_at,
                rt.revoked_at,
                a.email,
                a.tenant_id,
                a.role,
                a.is_active
            FROM refresh_tokens rt
            JOIN admins a ON a.id = rt.admin_id
            WHERE rt.token_hash = ?
            """,
            (old_token_hash,),
        ).fetchone()

        if not row:
            return None

        if row["revoked_at"] is not None:
            return None

        if row["expires_at"] <= now or not row["is_active"]:
            return None

        cursor = connection.execute(
            """
            UPDATE refresh_tokens
            SET revoked_at = ?, replaced_by = ?
            WHERE id = ? AND revoked_at IS NULL
            """,
            (now, new_token_id, row["token_id"]),
        )

        if cursor.rowcount != 1:
            return None

        connection.execute(
            """
            INSERT INTO refresh_tokens (
                id, admin_id, token_hash, expires_at, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                new_token_id,
                row["admin_id"],
                new_token_hash,
                new_expires_at,
                now,
            ),
        )

        return {
            "id": row["admin_id"],
            "email": row["email"],
            "tenant_id": row["tenant_id"],
            "role": row["role"],
        }


def revoke_refresh_token_by_hash(
    token_hash: str,
    revoked_at: str,
) -> bool:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE refresh_tokens
            SET revoked_at = ?
            WHERE token_hash = ? AND revoked_at IS NULL
            """,
            (revoked_at, token_hash),
        )

    return cursor.rowcount == 1



def revoke_admin_sessions_for_reuse(
    admin_id: str,
    revoked_at: str,
) -> int:
    """Revoke all active sessions after refresh-token reuse."""
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE refresh_tokens
            SET revoked_at = ?
            WHERE admin_id = ?
              AND revoked_at IS NULL
            """,
            (revoked_at, admin_id),
        )

    return cursor.rowcount
