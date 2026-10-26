"""Verify the configured SQLite database and its pre-migration backup."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from sqlalchemy.engine import make_url


class BackupVerificationError(RuntimeError):
    """Raised when the configured database backup cannot be verified."""


def _database_path() -> Path:
    configured_url = os.environ.get("EVOSIA_DATABASE_URL")
    if not configured_url:
        raise BackupVerificationError("EVOSIA_DATABASE_URL must be set")

    try:
        url = make_url(configured_url)
    except (ValueError, TypeError) as exc:
        raise BackupVerificationError("EVOSIA_DATABASE_URL is invalid") from exc

    if url.get_backend_name() != "sqlite":
        raise BackupVerificationError(
            "The production backup gate requires a SQLite database URL"
        )

    database = url.database
    if not database or database == ":memory:":
        raise BackupVerificationError("EVOSIA_DATABASE_URL must identify a file database")

    path = Path(database).expanduser()
    try:
        return path.resolve(strict=False)
    except OSError as exc:
        raise BackupVerificationError(
            "The configured SQLite database path is invalid"
        ) from exc


def _backup_path() -> Path:
    configured_path = os.environ.get("EVOSIA_SQLITE_BACKUP_PATH")
    if not configured_path:
        raise BackupVerificationError(
            "EVOSIA_SQLITE_BACKUP_PATH must point to a verified mounted backup"
        )

    try:
        return Path(configured_path).expanduser().resolve(strict=True)
    except OSError as exc:
        raise BackupVerificationError(
            "The configured SQLite backup file is unavailable"
        ) from exc


def _verify_integrity(path: Path, label: str) -> None:
    if not path.is_file():
        raise BackupVerificationError(f"The {label} is not a regular file")

    try:
        with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=5) as db:
            result = db.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.Error as exc:
        raise BackupVerificationError(f"The {label} failed SQLite integrity verification") from exc

    if result != ("ok",):
        raise BackupVerificationError(f"The {label} failed SQLite integrity verification")


def verify_backup() -> None:
    database = _database_path()
    backup = _backup_path()
    if database == backup:
        raise BackupVerificationError(
            "The SQLite backup must be a separate file from the live database"
        )

    _verify_integrity(backup, "configured SQLite backup")


def main() -> None:
    verify_backup()
    print("SQLite backup integrity verified")


if __name__ == "__main__":
    main()
