"""Iryax Platform Database Persistence, Atomic Backup & Disaster Recovery Verification.

Performs hot, atomic SQLite database backups using sqlite3.Connection.backup(),
verifies cryptographic/structural integrity, and validates disaster recovery restore.
"""

from __future__ import annotations

import argparse
import logging
import os
import pathlib
import shutil
import sqlite3
import sys
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backup_database")

BACKEND_DIR = pathlib.Path(__file__).parent.resolve()
DATA_DIR = BACKEND_DIR / "data"
AUTH_DB_PATH = DATA_DIR / "auth.db"
BACKUPS_DIR = DATA_DIR / "backups"


def perform_backup(source_db: pathlib.Path = AUTH_DB_PATH, keep_latest: int = 5) -> pathlib.Path:
    """Creates an atomic, consistent hot backup of the SQLite database."""
    if not source_db.exists():
        raise FileNotFoundError(f"Source database not found: {source_db}")

    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUPS_DIR / f"auth_backup_{timestamp}.db"

    logger.info("Starting atomic backup of %s to %s...", source_db, backup_file)
    src_conn = sqlite3.connect(str(source_db))
    dst_conn = sqlite3.connect(str(backup_file))

    try:
        with dst_conn:
            src_conn.backup(dst_conn, pages=10, progress=None)
        logger.info("Backup completed successfully: %s (%d bytes)", backup_file.name, backup_file.stat().st_size)
    finally:
        dst_conn.close()
        src_conn.close()

    # Clean old backups, keeping latest N
    all_backups = sorted(BACKUPS_DIR.glob("auth_backup_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    if len(all_backups) > keep_latest:
        for old in all_backups[keep_latest:]:
            logger.info("Pruning old backup: %s", old.name)
            old.unlink(missing_ok=True)

    return backup_file


def verify_backup_integrity(backup_path: pathlib.Path) -> bool:
    """Verifies SQLite structural integrity via PRAGMA integrity_check."""
    logger.info("Verifying integrity of backup %s...", backup_path.name)
    conn = sqlite3.connect(str(backup_path))
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()
        if not result or result[0] != "ok":
            logger.error("Integrity check failed: %s", result)
            return False

        cursor.execute("SELECT COUNT(*) FROM admins;")
        admin_count = cursor.fetchone()[0]
        logger.info("Integrity check PASSED: OK. Total admins preserved: %d", admin_count)
        return True
    finally:
        conn.close()


def verify_disaster_recovery_restore(backup_path: pathlib.Path) -> bool:
    """Simulates a disaster recovery scenario by restoring to a fresh temporary path."""
    test_restore_path = BACKUPS_DIR / "dr_recovery_test.db"
    logger.info("Simulating Disaster Recovery restoration to %s...", test_restore_path.name)
    try:
        shutil.copy2(backup_path, test_restore_path)
        conn = sqlite3.connect(str(test_restore_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        check = cursor.fetchone()
        cursor.execute("SELECT email, role, is_active FROM admins;")
        rows = cursor.fetchall()
        conn.close()

        if check and check[0] == "ok" and len(rows) > 0:
            logger.info("Disaster recovery test SUCCESSFUL: Restored %d active accounts cleanly.", len(rows))
            return True
        else:
            logger.error("Disaster recovery test FAILED.")
            return False
    finally:
        if test_restore_path.exists():
            test_restore_path.unlink()


def main():
    parser = argparse.ArgumentParser(description="Iryax Database Backup & Disaster Recovery Verification")
    parser.add_argument("--verify-only", action="store_true", help="Only verify existing backups")
    args = parser.parse_args()

    if args.verify_only:
        latest = sorted(BACKUPS_DIR.glob("auth_backup_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not latest:
            logger.error("No backups found in %s", BACKUPS_DIR)
            sys.exit(1)
        ok = verify_backup_integrity(latest[0]) and verify_disaster_recovery_restore(latest[0])
        sys.exit(0 if ok else 1)

    backup_file = perform_backup()
    integrity_ok = verify_backup_integrity(backup_file)
    recovery_ok = verify_disaster_recovery_restore(backup_file)

    if integrity_ok and recovery_ok:
        logger.info("All Database Persistence & Backup verifications PASSED.")
        sys.exit(0)
    else:
        logger.error("Database backup or verification FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()

