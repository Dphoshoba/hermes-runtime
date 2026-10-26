"""Container startup ordering and fail-closed SQLite backup verification."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy.engine import URL

from scripts import container_entrypoint
from scripts.verify_sqlite_backup import BackupVerificationError, verify_backup


def _sqlite_url(path: Path) -> str:
    return URL.create("sqlite", database=str(path)).render_as_string(
        hide_password=False,
    )


def _create_database(path: Path) -> None:
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE backup_fixture (id INTEGER PRIMARY KEY)")


def test_startup_verifies_backup_then_migrates_then_execs_uvicorn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = "sqlite:///caller-configured.db"
    calls: list[tuple[str, list[str]]] = []
    migration_process = Mock()

    def run(command: list[str], *, cwd: Path, check: bool) -> Mock:
        calls.append(("run", command))
        assert cwd == container_entrypoint.APP_ROOT
        assert check is True
        assert os.environ["EVOSIA_DATABASE_URL"] == database_url
        return migration_process

    def execvp(file: str, args: list[str]) -> None:
        calls.append(("exec", [file, *args[1:]]))

    monkeypatch.setenv("EVOSIA_ENV", "production")
    monkeypatch.setenv("EVOSIA_DATABASE_URL", database_url)
    monkeypatch.setenv("PORT", "9123")
    monkeypatch.setattr(container_entrypoint.subprocess, "run", run)
    monkeypatch.setattr(container_entrypoint.os, "execvp", execvp)

    container_entrypoint.main()

    assert calls == [
        (
            "run",
            [
                sys.executable,
                str(Path(container_entrypoint.__file__).with_name(
                    "verify_sqlite_backup.py",
                )),
            ],
        ),
        (
            "run",
            [
                sys.executable,
                "-m",
                "alembic",
                "-c",
                "enterprise/alembic.ini",
                "upgrade",
                "head",
            ],
        ),
        (
            "exec",
            [
                "uvicorn",
                "enterprise.app:app",
                "--host",
                "0.0.0.0",
                "--port",
                "9123",
            ],
        ),
    ]


def test_uvicorn_does_not_start_when_migration_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[list[str]] = []
    execvp = Mock()

    def run(command: list[str], *, cwd: Path, check: bool) -> Mock:
        commands.append(command)
        if command[1:3] == ["-m", "alembic"]:
            raise subprocess.CalledProcessError(1, command)
        return Mock()

    monkeypatch.setenv("EVOSIA_ENV", "production")
    monkeypatch.setenv("EVOSIA_DATABASE_URL", "sqlite:///review.db")
    monkeypatch.setattr(container_entrypoint.subprocess, "run", run)
    monkeypatch.setattr(container_entrypoint.os, "execvp", execvp)

    with pytest.raises(subprocess.CalledProcessError):
        container_entrypoint.main()

    assert len(commands) == 2
    execvp.assert_not_called()


def test_migration_does_not_start_when_backup_verification_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = Mock(side_effect=subprocess.CalledProcessError(1, ["verify-backup"]))
    execvp = Mock()
    monkeypatch.setenv("EVOSIA_ENV", "production")
    monkeypatch.setattr(container_entrypoint.subprocess, "run", run)
    monkeypatch.setattr(container_entrypoint.os, "execvp", execvp)

    with pytest.raises(subprocess.CalledProcessError):
        container_entrypoint.main()

    run.assert_called_once()
    execvp.assert_not_called()


def test_backup_verification_uses_configured_database_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "configured.db"
    backup = tmp_path / "configured.backup.db"
    _create_database(database)
    _create_database(backup)
    monkeypatch.setenv("EVOSIA_DATABASE_URL", _sqlite_url(database))
    monkeypatch.setenv("EVOSIA_SQLITE_BACKUP_PATH", str(backup))

    verify_backup()


def test_backup_verification_allows_a_fresh_database_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "not-created-yet.db"
    backup = tmp_path / "fresh-install.backup.db"
    _create_database(backup)
    monkeypatch.setenv("EVOSIA_DATABASE_URL", _sqlite_url(database))
    monkeypatch.setenv("EVOSIA_SQLITE_BACKUP_PATH", str(backup))

    verify_backup()

    assert not database.exists()


@pytest.mark.parametrize("bad_backup", ["missing", "corrupt", "same_as_database"])
def test_backup_verification_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bad_backup: str,
) -> None:
    database = tmp_path / "configured.db"
    backup = tmp_path / "configured.backup.db"
    _create_database(database)

    if bad_backup == "corrupt":
        backup.write_bytes(b"not a sqlite database")
        backup_path = backup
    elif bad_backup == "same_as_database":
        backup_path = database
    else:
        backup_path = tmp_path / "missing.backup.db"

    monkeypatch.setenv("EVOSIA_DATABASE_URL", _sqlite_url(database))
    monkeypatch.setenv("EVOSIA_SQLITE_BACKUP_PATH", str(backup_path))

    with pytest.raises(BackupVerificationError):
        verify_backup()


def test_railway_config_has_no_predeploy_volume_operation() -> None:
    railway_config = Path(__file__).resolve().parents[1] / "railway.toml"
    content = railway_config.read_text(encoding="utf-8")
    assert not any(
        line.lstrip().startswith("preDeployCommand")
        for line in content.splitlines()
    )

    dockerfile = (railway_config.parent / "Dockerfile").read_text(encoding="utf-8")
    assert 'ENTRYPOINT ["python", "/app/scripts/container_entrypoint.py"]' in dockerfile
