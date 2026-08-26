"""
Guided Summary Repository-Context Regression Test

Proves /api/guided/summary resolves the same authoritative repository as
/api/guided/review-scope when no explicit repository_id is supplied.

Root cause: summary returned null repository fields because it did not
auto-discover from ScanJob, while review-scope did. The fix adds
_scan-job-based repository resolution shared by both endpoints.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

TEST_DB_URL = "sqlite:///./test_guided_summary_repo_ctx.db"

from enterprise.app import app
from enterprise.database import Base, get_engine
from enterprise.models import (
    Finding,
    FindingAdjudication,
    Mission,
    Repository,
    ScanJob,
)


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch):
    monkeypatch.setenv("HERMES_DATABASE_URL", TEST_DB_URL)
    monkeypatch.setenv("EVOSIA_DATABASE_URL", TEST_DB_URL)
    monkeypatch.setenv("EVOSIA_JWT_SECRET", "summary-ctx-test-secret")

    import enterprise.services as _svc
    monkeypatch.setattr(_svc, "SECRET_KEY", "summary-ctx-test-secret")
    import enterprise.app as _app_mod
    monkeypatch.setattr(_app_mod, "SECRET_KEY", "summary-ctx-test-secret")
    _app_mod.engine = get_engine()
    eng = _app_mod.engine
    Base.metadata.create_all(bind=eng)
    yield
    eng.dispose()
    Base.metadata.drop_all(bind=eng)
    from enterprise.database import _ENGINES
    _ENGINES.pop(TEST_DB_URL, None)
    try:
        os.remove("./test_guided_summary_repo_ctx.db")
    except OSError:
        pass


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth(client):
    email = f"sc-ctx-{uuid.uuid4().hex[:8]}@test.com"
    password = "testpass1234"
    client.post("/api/auth/register", json={
        "email": email, "password": password, "name": "Summary Ctx Tester",
    })
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def m8_fixture(auth):
    """Seed M8-like fixture: repository, scan job, findings, adjudication, mission."""
    eng = get_engine(TEST_DB_URL)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=eng, future=True)
    session = Session()

    repo = Repository(
        name="sample_service (M8 disposable)",
        url="https://github.com/evosia/sample-service",
        status="active",
        metadata_json={
            "m8_fixture": True,
            "is_disposable": True,
            "preparation_allowed": True,
        },
    )
    session.add(repo)
    session.flush()

    scan_job = ScanJob(
        repository_id=repo.id,
        status="completed",
        scan_type="full",
        branch="main",
        commit_sha="abc123",
        started_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
        completed_at=datetime(2026, 8, 20, 0, 5, tzinfo=timezone.utc),
        findings_count=4,
        metadata_json={
            "review_scope": {
                "folders_inspected": ["src", "tests"],
                "files_inspected": 4,
                "repository_name": "sample_service (M8 disposable)",
                "exclusions": [],
            }
        },
    )
    session.add(scan_job)
    session.flush()

    f1 = Finding(
        repository_id=repo.id,
        finding_type="security",
        severity="high",
        category="security-credential",
        title="Hardcoded API key in configuration",
        description="An API key is hardcoded in config.",
        module="src/config.py",
    )
    session.add(f1)
    session.flush()

    session.add(FindingAdjudication(
        finding_id=f1.id,
        classification="ACTIONABLE",
        operator="operator:test",
        reviewed_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
    ))

    f2 = Finding(
        repository_id=repo.id,
        finding_type="maintainability",
        severity="medium",
        category="large-module",
        title="Large utility module",
        module="src/calc.py",
    )
    session.add(f2)
    session.flush()

    f3 = Finding(
        repository_id=repo.id,
        finding_type="dependency",
        severity="low",
        category="dependency-choice",
        title="Unpinned dependency choices",
        module="requirements.txt",
    )
    session.add(f3)
    session.flush()

    f4 = Finding(
        repository_id=repo.id,
        finding_type="configuration",
        severity="low",
        category="configuration-setup",
        title="Missing configuration items",
        module="src/config.py",
    )
    session.add(f4)
    session.flush()

    mission = Mission(
        mission_id="M8-SUMMARY-CTX-001",
        repository_id=repo.id,
        title="Replace hardcoded API key with env var",
        description="Replace the hardcoded key with os.environ.",
        mission_type="remediation",
        status="DRAFT",
        priority=1,
        metadata_json={"originating_finding_id": f1.id, "scope": "src/config.py"},
    )
    session.add(mission)
    session.commit()

    data = {
        "repo_id": repo.id,
        "repo_name": repo.name,
        "scan_job_id": scan_job.id,
        "finding_ids": [f1.id, f2.id, f3.id, f4.id],
    }
    session.close()
    return data


@pytest.fixture
def non_disposable_fixture(auth):
    """Seed a non-disposable repository with scan job and findings."""
    eng = get_engine(TEST_DB_URL)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=eng, future=True)
    session = Session()

    repo = Repository(
        name="real-project",
        url="https://github.com/org/real-project",
        status="active",
        metadata_json={"is_disposable": False},
    )
    session.add(repo)
    session.flush()

    scan_job = ScanJob(
        repository_id=repo.id,
        status="completed",
        scan_type="full",
        branch="main",
        started_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
        completed_at=datetime(2026, 8, 20, 0, 3, tzinfo=timezone.utc),
        findings_count=1,
        metadata_json={
            "review_scope": {
                "folders_inspected": ["src"],
                "files_inspected": 2,
                "repository_name": "real-project",
                "exclusions": [],
            }
        },
    )
    session.add(scan_job)
    session.flush()

    f1 = Finding(
        repository_id=repo.id,
        finding_type="complexity",
        severity="medium",
        category="complexity",
        title="Complex function",
        module="src/main.py",
    )
    session.add(f1)
    session.flush()

    session.commit()
    data = {"repo_id": repo.id, "repo_name": repo.name, "scan_job_id": scan_job.id}
    session.close()
    return data


class TestGuidedSummaryRepositoryContext:
    """Regression tests for guided-summary repository-context integration."""

    def test_summary_resolves_repository_without_explicit_id(
        self, client, auth, m8_fixture
    ):
        """GET /api/guided/summary without repository_id must resolve the repo
        from ScanJob, returning real repository_id, name, and metadata."""
        r = client.get("/api/guided/summary", headers=auth)
        assert r.status_code == 200
        data = r.json()

        assert data["repository_id"] == m8_fixture["repo_id"]
        assert data["repository_name"] == m8_fixture["repo_name"]
        assert data["repository_metadata"] is not None
        assert data["repository_metadata"]["is_disposable"] is True

    def test_summary_and_review_scope_resolve_same_repository(
        self, client, auth, m8_fixture
    ):
        """Both endpoints must resolve the identical repository for the same scan/session."""
        summary = client.get("/api/guided/summary", headers=auth).json()
        scope = client.get("/api/guided/review-scope", headers=auth).json()

        assert summary["repository_id"] == m8_fixture["repo_id"]
        assert scope.get("repository_name") == m8_fixture["repo_name"]
        assert summary["repository_name"] == scope.get("repository_name")

    def test_summary_findings_count_unchanged(
        self, client, auth, m8_fixture
    ):
        """Summary counts must reflect the repository's findings."""
        r = client.get("/api/guided/summary", headers=auth)
        data = r.json()
        assert data["total_findings"] == 4
        assert data["needs_attention"] == 1
        assert data["needs_context"] == 3

    def test_summary_authority_unchanged(
        self, client, auth, m8_fixture
    ):
        """Authority level must remain at recommend (1), never elevated."""
        r = client.get("/api/guided/summary", headers=auth)
        data = r.json()
        assert data["authority_level"] == 1
        assert data["nothing_changed"] is True

    def test_non_disposable_repository_not_marked_disposable(
        self, client, auth, non_disposable_fixture
    ):
        """A real (non-disposable) repository must not receive is_disposable."""
        r = client.get("/api/guided/summary", headers=auth)
        data = r.json()
        assert data["repository_id"] == non_disposable_fixture["repo_id"]
        assert data["repository_name"] == non_disposable_fixture["repo_name"]
        assert data["repository_metadata"]["is_disposable"] is False

    def test_explicit_repository_id_overrides_scan_job_discovery(
        self, client, auth, m8_fixture
    ):
        """Passing repository_id directly must still work and return that repo's data."""
        r = client.get(
            f"/api/guided/summary?repository_id={m8_fixture['repo_id']}",
            headers=auth,
        )
        data = r.json()
        assert data["repository_id"] == m8_fixture["repo_id"]
        assert data["repository_name"] == m8_fixture["repo_name"]

    def test_summary_without_scan_job_returns_nulls(
        self, client, auth
    ):
        """When no ScanJob exists, summary returns null repository fields (not a crash)."""
        r = client.get("/api/guided/summary", headers=auth)
        assert r.status_code == 200
        data = r.json()
        assert data["repository_id"] is None
        assert data["repository_name"] is None
        assert data["repository_metadata"] is None
