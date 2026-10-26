"""C3 — Alembic migration safety tests.

Verifies:
- Alembic targets the authoritative database URL from the environment.
- upgrade head succeeds on a fresh database.
- upgrade head is idempotent.
- The resulting schema is usable by the current ORM.
- Existing representative schema can be upgraded safely (after stamp).
- No destructive reset strategy is used.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ENTERPRISE_DIR = _REPO_ROOT / "enterprise"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from enterprise.database import Base, get_engine
from enterprise.models import User, Repository, Finding  # noqa: F401
from enterprise.app import validate_review_schema

_EXPECTED_TABLES = {
    "users",
    "repositories",
    "journal_events",
    "findings",
    "missions",
    "reports",
    "scan_jobs",
    "scan_history",
    "finding_adjudications",
    "agent_jobs",
    "agent_job_idempotency_keys",
    "device_projects",
}


def _run_alembic(db_url: str, *args: str) -> subprocess.CompletedProcess:
    """Run alembic with the given arguments against the database URL."""
    env = os.environ.copy()
    env["EVOSIA_DATABASE_URL"] = db_url
    env["PYTHONPATH"] = str(_REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini"] + list(args),
        cwd=str(_ENTERPRISE_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _run_upgrade(db_url: str) -> None:
    """Run ``alembic upgrade head`` and assert success."""
    result = _run_alembic(db_url, "upgrade", "head")
    assert result.returncode == 0, (
        f"alembic upgrade failed (rc={result.returncode}):\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def _run_stamp(db_url: str) -> None:
    """Run ``alembic stamp head`` (mark all migrations applied)."""
    result = _run_alembic(db_url, "stamp", "head")
    assert result.returncode == 0, (
        f"alembic stamp failed (rc={result.returncode}):\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def _get_table_names(db_url: str) -> set[str]:
    """Return the set of table names in the database."""
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    engine = create_engine(db_url, connect_args=connect_args, poolclass=StaticPool)
    try:
        with engine.connect() as conn:
            return set(inspect(conn).get_table_names())
    finally:
        engine.dispose()


def _has_alembic_version(db_url: str) -> bool:
    """Check whether the alembic_version table exists."""
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    engine = create_engine(db_url, connect_args=connect_args, poolclass=StaticPool)
    try:
        with engine.connect() as conn:
            return "alembic_version" in set(inspect(conn).get_table_names())
    finally:
        engine.dispose()


class TestAlembicConfig:
    """Verify Alembic resolves the authoritative database URL."""

    def test_env_var_overrides_ini(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        db_url = f"sqlite:///{db_path}"
        _run_upgrade(db_url)
        assert db_path.exists(), "Database file was not created"


class TestFreshDatabaseMigration:
    """Verify upgrade head succeeds on a fresh database."""

    def test_fresh_sqlite_upgrade(self, tmp_path: Path) -> None:
        db_path = tmp_path / "fresh.db"
        db_url = f"sqlite:///{db_path}"
        _run_upgrade(db_url)

        tables = _get_table_names(db_url)
        assert _EXPECTED_TABLES.issubset(tables), f"Missing tables: {_EXPECTED_TABLES - tables}"
        assert _has_alembic_version(db_url), "alembic_version table not created"
        with create_engine(db_url).connect() as conn:
            repository_columns = {
                column["name"] for column in inspect(conn).get_columns("repositories")
            }
            assert "owner_user_id" in repository_columns
            active_index = next(
                index for index in inspect(conn).get_indexes("agent_jobs")
                if index["name"] == "uq_agent_jobs_one_active_per_project"
            )
            assert active_index["unique"]


class TestComputerReviewMigrationCompatibility:
    def test_existing_pending_status_remains_compatible_with_old_agent(
        self, tmp_path: Path,
    ) -> None:
        db_url = f"sqlite:///{tmp_path / 'legacy_pending.db'}"
        result = _run_alembic(db_url, "upgrade", "008_agent_job_truncation")
        assert result.returncode == 0, result.stderr
        engine = create_engine(db_url)
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO users (id, email, name, hashed_password) "
                "VALUES ('user-1', 'legacy@example.test', 'Legacy', 'hash')"
            ))
            conn.execute(text(
                "INSERT INTO devices "
                "(id, device_id, device_name, platform, agent_version, user_id, status) "
                "VALUES ('device-1', 'device-1', 'Legacy', 'windows', '0.1', "
                "'user-1', 'active')"
            ))
            conn.execute(text(
                "INSERT INTO device_projects "
                "(id, device_id, user_id, display_name, status, authority) "
                "VALUES ('project-1', 'device-1', 'user-1', 'Legacy', 'active', "
                "'REVIEW_ONLY')"
            ))
            conn.execute(text(
                "INSERT INTO agent_jobs "
                "(id, user_id, device_id, device_project_id, operation_type, status, truncated) "
                "VALUES ('job-1', 'user-1', 'device-1', 'project-1', "
                "'PROJECT_SCAN', 'PENDING', 0)"
            ))
        engine.dispose()

        _run_upgrade(db_url)
        engine = create_engine(db_url)
        with engine.connect() as conn:
            status_value = conn.execute(
                text("SELECT status FROM agent_jobs WHERE id = 'job-1'")
            ).scalar_one()
            assert status_value == "PENDING"
        engine.dispose()

    def test_duplicate_active_reviews_fail_before_schema_changes(
        self, tmp_path: Path,
    ) -> None:
        db_url = f"sqlite:///{tmp_path / 'active_duplicates.db'}"
        result = _run_alembic(db_url, "upgrade", "008_agent_job_truncation")
        assert result.returncode == 0, result.stderr

        engine = create_engine(db_url)
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO users (id, email, name, hashed_password) "
                "VALUES ('user-1', 'duplicates@example.test', 'Duplicates', 'hash')"
            ))
            conn.execute(text(
                "INSERT INTO devices "
                "(id, device_id, device_name, platform, agent_version, user_id) "
                "VALUES ('device-1', 'device-1', 'Legacy', 'windows', '0.1', 'user-1')"
            ))
            conn.execute(text(
                "INSERT INTO device_projects "
                "(id, device_id, user_id, display_name) "
                "VALUES ('project-1', 'device-1', 'user-1', 'Legacy')"
            ))
            conn.execute(text(
                "INSERT INTO agent_jobs "
                "(id, user_id, device_id, device_project_id, operation_type, status) "
                "VALUES ('job-1', 'user-1', 'device-1', 'project-1', "
                "'PROJECT_SCAN', 'PENDING'), "
                "('job-2', 'user-1', 'device-1', 'project-1', "
                "'PROJECT_SCAN', 'STARTED')"
            ))
        engine.dispose()

        result = _run_alembic(db_url, "upgrade", "head")
        assert result.returncode != 0
        assert "Cannot enforce one active review per project" in result.stderr
        engine = create_engine(db_url)
        with engine.connect() as conn:
            assert conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == "008_agent_job_truncation"
            columns = {column["name"] for column in inspect(conn).get_columns("agent_jobs")}
            assert "idempotency_key" not in columns
            assert "agent_job_idempotency_keys" not in inspect(conn).get_table_names()
        engine.dispose()

    def test_old_database_without_new_columns_fails_startup_guard(
        self, tmp_path: Path,
    ) -> None:
        engine = create_engine(f"sqlite:///{tmp_path / 'old_schema.db'}")
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE agent_jobs (id VARCHAR(36) PRIMARY KEY)"))
        with pytest.raises(RuntimeError, match="required Computer Review migrations"):
            validate_review_schema(engine)
        engine.dispose()

    def test_downgrade_refuses_to_drop_persisted_review_evidence(
        self, tmp_path: Path,
    ) -> None:
        db_url = f"sqlite:///{tmp_path / 'downgrade_guard.db'}"
        _run_upgrade(db_url)
        engine = create_engine(db_url)
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO users (id, email, name, hashed_password) "
                "VALUES ('user-1', 'evidence@example.test', 'Evidence', 'hash')"
            ))
            conn.execute(text(
                "INSERT INTO devices "
                "(id, device_id, device_name, platform, agent_version, user_id, status) "
                "VALUES ('device-1', 'device-1', 'Evidence', 'windows', '0.1', "
                "'user-1', 'active')"
            ))
            conn.execute(text(
                "INSERT INTO device_projects "
                "(id, device_id, user_id, display_name, status, authority) "
                "VALUES ('project-1', 'device-1', 'user-1', 'Evidence', 'active', "
                "'REVIEW_ONLY')"
            ))
            conn.execute(text(
                "INSERT INTO agent_jobs "
                "(id, user_id, device_id, device_project_id, operation_type, status, "
                "truncated, evidence, coverage) "
                "VALUES ('job-1', 'user-1', 'device-1', 'project-1', "
                "'PROJECT_SCAN', 'COMPLETED', 0, '{}', '{}')"
            ))
        engine.dispose()

        result = _run_alembic(db_url, "downgrade", "008_agent_job_truncation")
        assert result.returncode != 0
        assert "Cannot downgrade Computer Review evidence" in result.stderr
        engine = create_engine(db_url)
        with engine.connect() as conn:
            assert conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == "010_repository_ownership"
            assert "owner_user_id" in {
                column["name"] for column in inspect(conn).get_columns("repositories")
            }
        engine.dispose()


class TestMigrationIdempotence:
    """Verify upgrade head is idempotent."""

    def test_repeated_upgrade(self, tmp_path: Path) -> None:
        db_path = tmp_path / "idempotent.db"
        db_url = f"sqlite:///{db_path}"

        _run_upgrade(db_url)
        tables_before = _get_table_names(db_url)

        _run_upgrade(db_url)
        tables_after = _get_table_names(db_url)
        assert tables_before == tables_after, "Schema changed on second upgrade"


class TestSchemaUsability:
    """Verify the resulting schema is usable by the current ORM."""

    def test_orm_models_load(self, tmp_path: Path) -> None:
        db_path = tmp_path / "orm_test.db"
        db_url = f"sqlite:///{db_path}"

        _run_upgrade(db_url)

        engine = get_engine(db_url)
        with Session(engine) as session:
            session.query(User).count()
            session.query(Repository).count()
            session.query(Finding).count()


class TestExistingSchemaStamp:
    """Verify an existing database created by create_all() can be stamped.

    Production scenario: database was created by Base.metadata.create_all()
    before Alembic was integrated. The schema matches the ORM models (which
    is what create_all produces), so we stamp the alembic_version to the
    current head. After stamping, upgrade is a no-op.
    """

    def test_stamp_existing_database(self, tmp_path: Path) -> None:
        """Stamp an existing create_all() database so future upgrades are safe."""
        db_path = tmp_path / "existing.db"
        db_url = f"sqlite:///{db_path}"

        # 1. Create database using create_all (the current startup path)
        engine = create_engine(db_url, poolclass=StaticPool)
        Base.metadata.create_all(bind=engine)
        engine.dispose()

        tables_before = _get_table_names(db_url)
        assert _EXPECTED_TABLES.issubset(tables_before), (
            f"create_all did not produce expected tables: {_EXPECTED_TABLES - tables_before}"
        )
        assert not _has_alembic_version(db_url), "alembic_version should not exist yet"

        # 2. Stamp — marks all migrations as applied without running them
        _run_stamp(db_url)
        assert _has_alembic_version(db_url), "alembic_version should exist after stamp"

        # 3. Upgrade should now be a no-op (no "table already exists" error)
        _run_upgrade(db_url)

        # 4. Schema is unchanged (except for the alembic_version tracking table)
        tables_after = _get_table_names(db_url)
        assert tables_after - {"alembic_version"} == tables_before, (
            "Schema changed after stamp + upgrade"
        )
