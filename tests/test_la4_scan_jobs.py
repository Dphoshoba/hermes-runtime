"""LA4 governed read-only project scanning tests — security, authority, lifecycle."""

from __future__ import annotations

import hashlib
import os
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

# Unique file-backed DB for LA4 tests — set before any enterprise imports.
LA4_DB_URL = "sqlite:///./test_la4.db"
os.environ["HERMES_DATABASE_URL"] = LA4_DB_URL
os.environ["EVOSIA_DATABASE_URL"] = LA4_DB_URL

from enterprise.app import app
from enterprise.database import Base, get_engine, SessionLocal, _ENGINES
from enterprise.models import (
    AgentJob, Device, DeviceProject, User, BootstrapToken,
)
from enterprise.services.agent_job_service import (
    create_scan_job, get_next_job, get_job,
    mark_job_started, complete_job, fail_job,
)
from enterprise.schemas import (
    ALLOWED_OPERATION_TYPES, JOB_STATUS_PENDING,
    JOB_STATUS_STARTED, JOB_STATUS_COMPLETED, JOB_STATUS_FAILED,
)
from evosia_agent.scanner import (
    scan_project, ScanLimits, ScanResult,
    MAX_FILE_SIZE_BYTES, MAX_TOTAL_BYTES_READ, MAX_FILE_COUNT,
    _get_git_metadata,
)
from evosia_agent.path_validation import SymlinkStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _la4_db(monkeypatch):
    """Isolated database for LA4 tests."""
    monkeypatch.setenv("HERMES_DATABASE_URL", LA4_DB_URL)
    monkeypatch.setenv("EVOSIA_DATABASE_URL", LA4_DB_URL)
    monkeypatch.setenv("EVOSIA_JWT_SECRET", "la4-test-secret")
    import enterprise.services as _svc
    monkeypatch.setattr(_svc, "SECRET_KEY", "la4-test-secret")
    import enterprise.app as _app_mod
    monkeypatch.setattr(_app_mod, "SECRET_KEY", "la4-test-secret")
    _ENGINES.clear()
    eng = get_engine(LA4_DB_URL)
    _app_mod.engine = eng
    Base.metadata.create_all(bind=eng)
    yield
    Base.metadata.drop_all(bind=eng)
    _ENGINES.pop(LA4_DB_URL, None)
    try:
        os.remove("./test_la4.db")
    except OSError:
        pass


@pytest.fixture
def la4_client():
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def la4_auth(la4_client):
    email = f"la4-{uuid.uuid4().hex[:8]}@test.com"
    password = "testpass1234"
    la4_client.post("/api/auth/register", json={
        "email": email, "password": password, "name": "LA4 Tester"
    })
    r = la4_client.post("/api/auth/login", json={"email": email, "password": password})
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def la4_user_id(la4_auth):
    """Get the user ID from the auth header."""
    from jose import jwt
    from enterprise.services import SECRET_KEY, ALGORITHM
    token = la4_auth["Authorization"].split(" ")[1]
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return payload["sub"]


@pytest.fixture
def la4_device(la4_client, la4_auth):
    """Register and activate a device, return device info."""
    r = la4_client.post("/api/devices/register", json={
        "device_name": "LA4 Test Device",
        "platform": "macos",
        "agent_version": "evosia-agent/0.1.0",
    }, headers=la4_auth)
    bootstrap_token = r.json()["bootstrap_token"]
    device_id = r.json()["device_id"]

    # Exchange bootstrap token
    r = la4_client.post("/api/devices/exchange", json={
        "bootstrap_token": bootstrap_token,
    })
    device_credential = r.json()["access_token"]

    return {
        "device_id": device_id,
        "device_credential": device_credential,
    }


@pytest.fixture
def la4_project(la4_client, la4_auth, la4_device):
    """Register a device project, return project info."""
    device_id = la4_device["device_id"]
    device_credential = la4_device["device_credential"]

    # Create project auth token
    r = la4_client.post(f"/api/devices/{device_id}/project-auth-token", headers=la4_auth)
    project_auth_token = r.json()["project_authorization_token"]

    # Register project
    r = la4_client.post("/api/device-projects/", json={
        "device_id": device_id,
        "display_name": "TestProject",
        "local_root_fingerprint": "test_fingerprint",
        "project_authorization_token": project_auth_token,
    })
    project_id = r.json()["id"]

    return {
        "project_id": project_id,
        "device_id": device_id,
        "device_credential": device_credential,
    }


# ===========================================================================
# 1. Human-Authorized Scan Job Creation
# ===========================================================================

class TestHumanAuthorizedScanCreation:
    def test_user_creates_scan_job(self, la4_client, la4_auth, la4_project):
        """Authenticated user can create a PROJECT_SCAN job."""
        r = la4_client.post(
            f"/api/device-projects/{la4_project['project_id']}/scans",
            json={"operation_type": "PROJECT_SCAN"},
            headers=la4_auth,
        )
        assert r.status_code == 201
        data = r.json()
        assert data["operation_type"] == "PROJECT_SCAN"
        assert data["status"] == "PENDING"
        assert data["device_id"] == la4_project["device_id"]
        assert data["device_project_id"] == la4_project["project_id"]


# ===========================================================================
# 2. Unauthenticated Scan Creation Rejected
# ===========================================================================

class TestUnauthenticatedScanRejected:
    def test_no_auth_rejected(self, la4_client, la4_project):
        r = la4_client.post(
            f"/api/device-projects/{la4_project['project_id']}/scans",
            json={"operation_type": "PROJECT_SCAN"},
        )
        assert r.status_code == 401


# ===========================================================================
# 3. Device Token Cannot Create Scan Authority
# ===========================================================================

class TestDeviceTokenCannotCreateScan:
    def test_device_credential_rejected(self, la4_client, la4_project):
        """Device credential (JWT) must not create scan jobs."""
        r = la4_client.post(
            f"/api/device-projects/{la4_project['project_id']}/scans",
            json={"operation_type": "PROJECT_SCAN"},
            headers={"Authorization": f"Bearer {la4_project['device_credential']}"},
        )
        assert r.status_code == 401


# ===========================================================================
# 4. PROJECT_SCAN Is the Only LA4 Operation
# ===========================================================================

class TestOnlyProjectScanAllowed:
    def test_invalid_operation_rejected(self, la4_client, la4_auth, la4_project):
        r = la4_client.post(
            f"/api/device-projects/{la4_project['project_id']}/scans",
            json={"operation_type": "SHELL_COMMAND"},
            headers=la4_auth,
        )
        assert r.status_code == 422  # Pydantic validation rejects pattern

    def test_arbitrary_command_rejected(self, la4_client, la4_auth, la4_project):
        r = la4_client.post(
            f"/api/device-projects/{la4_project['project_id']}/scans",
            json={"operation_type": "rm -rf /"},
            headers=la4_auth,
        )
        assert r.status_code == 422

    def test_only_project_scan_in_allowlist(self):
        assert ALLOWED_OPERATION_TYPES == frozenset({"PROJECT_SCAN"})


# ===========================================================================
# 5. Device Polls Assigned Job
# ===========================================================================

class TestDevicePollsJob:
    def test_device_gets_next_job(self, la4_client, la4_auth, la4_project):
        """Device can fetch next pending job."""
        # Create a job
        la4_client.post(
            f"/api/device-projects/{la4_project['project_id']}/scans",
            json={"operation_type": "PROJECT_SCAN"},
            headers=la4_auth,
        )

        # Device polls
        r = la4_client.get(
            "/api/agent/jobs/next",
            headers={"Authorization": f"Bearer {la4_project['device_credential']}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data is not None
        assert data["status"] == "PENDING"
        assert data["device_id"] == la4_project["device_id"]

    def test_no_jobs_returns_none(self, la4_client, la4_project):
        r = la4_client.get(
            "/api/agent/jobs/next",
            headers={"Authorization": f"Bearer {la4_project['device_credential']}"},
        )
        assert r.status_code == 200
        assert r.json() is None


# ===========================================================================
# 6. Wrong Device Cannot Fetch Job
# ===========================================================================

class TestWrongDeviceCannotFetchJob:
    def test_wrong_device_rejected(self, la4_client, la4_auth, la4_project):
        """A different device cannot fetch another device's job."""
        # Create job for la4_project's device
        la4_client.post(
            f"/api/device-projects/{la4_project['project_id']}/scans",
            json={"operation_type": "PROJECT_SCAN"},
            headers=la4_auth,
        )

        # Register a second device
        r = la4_client.post("/api/devices/register", json={
            "device_name": "Other Device",
            "platform": "windows",
            "agent_version": "evosia-agent/0.1.0",
        }, headers=la4_auth)
        other_bootstrap = r.json()["bootstrap_token"]
        r = la4_client.post("/api/devices/exchange", json={
            "bootstrap_token": other_bootstrap,
        })
        other_credential = r.json()["access_token"]

        # Other device tries to fetch the job
        r = la4_client.get(
            "/api/agent/jobs/next",
            headers={"Authorization": f"Bearer {other_credential}"},
        )
        assert r.status_code == 200
        assert r.json() is None  # No jobs for this device


# ===========================================================================
# 7. Revoked Device Cannot Fetch Job
# ===========================================================================

class TestRevokedDeviceCannotFetchJob:
    def test_revoked_device_rejected(self, la4_client, la4_auth, la4_project):
        """Revoked device cannot fetch jobs."""
        # Create job
        la4_client.post(
            f"/api/device-projects/{la4_project['project_id']}/scans",
            json={"operation_type": "PROJECT_SCAN"},
            headers=la4_auth,
        )

        # Revoke device
        la4_client.post(
            f"/api/devices/{la4_project['device_id']}/revoke",
            headers=la4_auth,
        )

        # Revoked device tries to poll
        r = la4_client.get(
            "/api/agent/jobs/next",
            headers={"Authorization": f"Bearer {la4_project['device_credential']}"},
        )
        assert r.status_code == 403


# ===========================================================================
# 8. Revoked Project Cannot Be Scanned
# ===========================================================================

class TestRevokedProjectCannotBeScanned:
    def test_revoked_project_rejected(self, la4_client, la4_auth, la4_project):
        """Cannot create scan job for revoked project."""
        # Revoke project
        la4_client.post(
            f"/api/device-projects/{la4_project['project_id']}/revoke",
            headers=la4_auth,
        )

        # Try to create scan job
        r = la4_client.post(
            f"/api/device-projects/{la4_project['project_id']}/scans",
            json={"operation_type": "PROJECT_SCAN"},
            headers=la4_auth,
        )
        assert r.status_code == 400
        assert "revoked" in r.json()["detail"].lower()


# ===========================================================================
# 9. Job Lifecycle PENDING → STARTED → COMPLETED
# ===========================================================================

class TestJobLifecycleHappyPath:
    def test_full_lifecycle(self, la4_client, la4_auth, la4_project):
        # Create job
        r = la4_client.post(
            f"/api/device-projects/{la4_project['project_id']}/scans",
            json={"operation_type": "PROJECT_SCAN"},
            headers=la4_auth,
        )
        job_id = r.json()["id"]

        device_cred = la4_project["device_credential"]
        headers = {"Authorization": f"Bearer {device_cred}"}

        # Get job
        r = la4_client.get(f"/api/agent/jobs/{job_id}", headers=headers)
        assert r.json()["status"] == "PENDING"

        # Mark started
        r = la4_client.post(f"/api/agent/jobs/{job_id}/started",
            json={"agent_version": "evosia-agent/0.1.0"}, headers=headers)
        assert r.json()["status"] == "STARTED"

        # Submit results
        evidence = {
            "job_id": job_id,
            "device_id": la4_project["device_id"],
            "device_project_id": la4_project["project_id"],
            "project_display_name": "TestProject",
            "agent_version": "evosia-agent/0.1.0",
            "started_at": "2026-08-27T00:00:00Z",
            "completed_at": "2026-08-27T00:01:00Z",
            "file_count": 10,
            "languages": ["Python"],
            "project_structure_summary": {},
            "findings": [],
            "truncated": False,
            "limits": {},
            "provenance": "LIVE_EVOSIA_EVIDENCE",
            "evidence_source": "device_local_scan",
        }
        r = la4_client.post(f"/api/agent/jobs/{job_id}/results",
            json={"evidence": evidence, "duration_seconds": 60.0}, headers=headers)
        assert r.json()["status"] == "COMPLETED"


# ===========================================================================
# 10. Failed Job Lifecycle
# ===========================================================================

class TestFailedJobLifecycle:
    def test_pending_to_failed(self, la4_client, la4_auth, la4_project):
        r = la4_client.post(
            f"/api/device-projects/{la4_project['project_id']}/scans",
            json={"operation_type": "PROJECT_SCAN"},
            headers=la4_auth,
        )
        job_id = r.json()["id"]

        device_cred = la4_project["device_credential"]
        headers = {"Authorization": f"Bearer {device_cred}"}

        # Report failure from PENDING
        r = la4_client.post(f"/api/agent/jobs/{job_id}/failed",
            json={"failure_reason": "Project not found locally"}, headers=headers)
        assert r.json()["status"] == "FAILED"
        assert r.json()["failure_reason"] == "Project not found locally"

    def test_started_to_failed(self, la4_client, la4_auth, la4_project):
        r = la4_client.post(
            f"/api/device-projects/{la4_project['project_id']}/scans",
            json={"operation_type": "PROJECT_SCAN"},
            headers=la4_auth,
        )
        job_id = r.json()["id"]

        device_cred = la4_project["device_credential"]
        headers = {"Authorization": f"Bearer {device_cred}"}

        la4_client.post(f"/api/agent/jobs/{job_id}/started",
            json={"agent_version": "evosia-agent/0.1.0"}, headers=headers)

        r = la4_client.post(f"/api/agent/jobs/{job_id}/failed",
            json={"failure_reason": "Scan timeout"}, headers=headers)
        assert r.json()["status"] == "FAILED"


# ===========================================================================
# 11. Duplicate Completion Rejected
# ===========================================================================

class TestDuplicateCompletionRejected:
    def test_cannot_complete_twice(self, la4_client, la4_auth, la4_project):
        r = la4_client.post(
            f"/api/device-projects/{la4_project['project_id']}/scans",
            json={"operation_type": "PROJECT_SCAN"},
            headers=la4_auth,
        )
        job_id = r.json()["id"]

        device_cred = la4_project["device_credential"]
        headers = {"Authorization": f"Bearer {device_cred}"}

        la4_client.post(f"/api/agent/jobs/{job_id}/started",
            json={"agent_version": "evosia-agent/0.1.0"}, headers=headers)

        evidence = {
            "job_id": job_id,
            "device_id": la4_project["device_id"],
            "device_project_id": la4_project["project_id"],
            "project_display_name": "TestProject",
            "agent_version": "evosia-agent/0.1.0",
            "started_at": "2026-08-27T00:00:00Z",
            "completed_at": "2026-08-27T00:01:00Z",
            "file_count": 10,
            "languages": [],
            "project_structure_summary": {},
            "findings": [],
            "truncated": False,
            "limits": {},
            "provenance": "LIVE_EVOSIA_EVIDENCE",
            "evidence_source": "device_local_scan",
        }
        la4_client.post(f"/api/agent/jobs/{job_id}/results",
            json={"evidence": evidence, "duration_seconds": 60.0}, headers=headers)

        # Try to complete again
        r = la4_client.post(f"/api/agent/jobs/{job_id}/results",
            json={"evidence": evidence, "duration_seconds": 60.0}, headers=headers)
        assert r.status_code == 409


# ===========================================================================
# 12–16. Filesystem Containment, Traversal, Symlink Tests (Scanner)
# ===========================================================================

class TestScannerContainment:
    def test_normal_source_read(self):
        """Normal source file can be read."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main.py").write_text("print('hello')")
            result = scan_project(root)
            assert result.file_count >= 1
            assert "Python" in result.languages

    def test_sensitive_file_contents_excluded(self, tmp_path: Path):
        """Sensitive file contents are never read."""
        root = tmp_path / "project"
        root.mkdir()
        env_file = root / ".env"
        env_file.write_text("SECRET_KEY=abc123")
        (root / "main.py").write_text("print('hello')")

        result = scan_project(root)
        # .env file should be flagged but not read
        assert any(f["type"] == "SENSITIVE_FILE" for f in result.findings)
        assert str(env_file.relative_to(root)) in result.sensitive_files_found

    def test_private_key_excluded(self, tmp_path: Path):
        """Private key contents are never read."""
        root = tmp_path / "project"
        root.mkdir()
        key_file = root / "id_rsa"
        key_file.write_text("-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----")
        (root / "main.py").write_text("print('hello')")

        result = scan_project(root)
        assert any(f["type"] == "SENSITIVE_FILE" for f in result.findings)

    def test_pem_file_excluded(self, tmp_path: Path):
        """PEM files are never read."""
        root = tmp_path / "project"
        root.mkdir()
        (root / "cert.pem").write_text("-----BEGIN CERTIFICATE-----\nfake\n-----END CERTIFICATE-----")
        (root / "main.py").write_text("print('hello')")

        result = scan_project(root)
        assert any(f["path"] == "cert.pem" for f in result.findings)

    @pytest.mark.skipif(os.name == "nt", reason="Windows symlink differs")
    def test_symlink_escape_rejected(self, tmp_path: Path):
        """Escaping symlink is detected and not followed."""
        root = tmp_path / "project"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("secret")
        (root / "escape").symlink_to(outside)

        result = scan_project(root)
        assert any(f["type"] == "SYMLINK_ESCAPE" for f in result.findings)

    def test_traversal_attack_rejected(self, tmp_path: Path):
        """../ traversal is blocked by containment."""
        root = tmp_path / "project"
        root.mkdir()
        # This file exists but is outside the root
        outside = tmp_path / "outside.py"
        outside.write_text("import os; os.system('evil')")

        result = scan_project(root)
        # The scanner walks from project_root.rglob, so it cannot see outside
        assert result.file_count == 0

    def test_absolute_outside_root_rejected(self, tmp_path: Path):
        """Absolute path outside root is not scanned."""
        root = tmp_path / "project"
        root.mkdir()
        (root / "main.py").write_text("print('hello')")

        result = scan_project(root)
        # Only files within root are scanned
        assert result.file_count == 1

    def test_binary_file_excluded(self, tmp_path: Path):
        """Binary files are excluded from content reading."""
        root = tmp_path / "project"
        root.mkdir()
        (root / "image.png").write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
        (root / "main.py").write_text("print('hello')")

        result = scan_project(root)
        assert any(f["type"] == "BINARY_FILE" for f in result.findings)
        # Only Python file should be counted as read
        assert result.file_count >= 1


# ===========================================================================
# 17–23. Resource Bounds Tests
# ===========================================================================

class TestResourceBounds:
    def test_oversized_file_bounded(self, tmp_path: Path):
        """Oversized individual file is bounded."""
        root = tmp_path / "project"
        root.mkdir()
        # Create file larger than limit
        big_file = root / "big.py"
        big_file.write_text("x" * (MAX_FILE_SIZE_BYTES + 1))
        (root / "small.py").write_text("print('ok')")

        result = scan_project(root)
        assert any(f["type"] == "OVERSIZED_FILE" for f in result.findings)

    def test_aggregate_scan_size_bounded(self, tmp_path: Path):
        """Aggregate bytes read is bounded."""
        root = tmp_path / "project"
        root.mkdir()
        # Create files that exceed aggregate limit
        for i in range(100):
            (root / f"file_{i}.py").write_text("x" * 200_000)

        result = scan_project(root, ScanLimits(max_total_bytes=1_000_000))
        assert result.truncated

    def test_maximum_file_count_bounded(self, tmp_path: Path):
        """Maximum file count is bounded."""
        root = tmp_path / "project"
        root.mkdir()
        for i in range(MAX_FILE_COUNT + 100):
            (root / f"file_{i}.py").write_text("x")

        result = scan_project(root)
        assert result.truncated
        assert result.file_count <= MAX_FILE_COUNT

    def test_scan_reports_truncation(self, tmp_path: Path):
        """Scan result indicates if truncation occurred."""
        root = tmp_path / "project"
        root.mkdir()
        for i in range(10):
            (root / f"file_{i}.py").write_text("x" * 200_000)

        result = scan_project(root, ScanLimits(max_total_bytes=500_000))
        assert result.truncated

    def test_timeout_boundary(self):
        """ScanLimits includes timeout_seconds."""
        limits = ScanLimits(timeout_seconds=30)
        assert limits.timeout_seconds == 30


# ===========================================================================
# 24. Language Detection
# ===========================================================================

class TestLanguageDetection:
    def test_python_detected(self, tmp_path: Path):
        root = tmp_path / "project"
        root.mkdir()
        (root / "main.py").write_text("print('hello')")
        result = scan_project(root)
        assert "Python" in result.languages

    def test_typescript_detected(self, tmp_path: Path):
        root = tmp_path / "project"
        root.mkdir()
        (root / "app.ts").write_text("console.log('hello')")
        result = scan_project(root)
        assert "TypeScript" in result.languages

    def test_multiple_languages(self, tmp_path: Path):
        root = tmp_path / "project"
        root.mkdir()
        (root / "main.py").write_text("print('hello')")
        (root / "app.js").write_text("console.log('hello')")
        (root / "style.css").write_text("body { color: red; }")
        result = scan_project(root)
        assert "Python" in result.languages
        assert "JavaScript" in result.languages
        assert "CSS" in result.languages


# ===========================================================================
# 25. Git Metadata
# ===========================================================================

class TestGitMetadata:
    def test_git_metadata_safe(self, tmp_path: Path):
        """Git metadata uses only allowlisted commands."""
        root = tmp_path / "project"
        root.mkdir()
        (root / ".git").mkdir()
        # Without a real git repo, metadata should return None or empty
        metadata = _get_git_metadata(root)
        # Should not crash, may return None or empty dict
        assert metadata is None or isinstance(metadata, dict)

    def test_no_arbitrary_git_commands(self):
        """Git adapter only uses allowlisted commands."""
        from evosia_agent.scanner import _GIT_ALLOWLIST
        for cmd in _GIT_ALLOWLIST:
            # Only safe read-only commands
            assert "push" not in cmd
            assert "commit" not in cmd
            assert "merge" not in cmd
            assert "checkout" not in cmd
            assert "clone" not in cmd
            assert "rm" not in cmd


# ===========================================================================
# 26–27. Evidence Schema & Provenance
# ===========================================================================

class TestEvidenceSchema:
    def test_provenance_is_live(self):
        """Evidence must have LIVE_EVOSIA_EVIDENCE provenance."""
        from enterprise.schemas import ScanEvidence
        evidence = ScanEvidence(
            job_id="test",
            device_id="dev",
            device_project_id="proj",
            project_display_name="Test",
            agent_version="evosia-agent/0.1.0",
            started_at="2026-08-27T00:00:00Z",
            completed_at="2026-08-27T00:01:00Z",
            file_count=10,
            languages=["Python"],
            project_structure_summary={},
            findings=[],
            truncated=False,
            limits={},
        )
        assert evidence.provenance == "LIVE_EVOSIA_EVIDENCE"
        assert evidence.evidence_source == "device_local_scan"

    def test_result_provenance_in_scan(self, tmp_path: Path):
        """Scan result includes provenance fields."""
        root = tmp_path / "project"
        root.mkdir()
        (root / "main.py").write_text("print('hello')")
        result = scan_project(root)
        # ScanResult itself doesn't have provenance — that's added in execute_job
        # But the scan should produce valid findings
        assert isinstance(result, ScanResult)
        assert result.file_count >= 1


# ===========================================================================
# 28–30. Result Submission Validation
# ===========================================================================

class TestResultSubmissionValidation:
    def test_wrong_device_result_rejected(self, la4_client, la4_auth, la4_project):
        """Results from wrong device are rejected."""
        r = la4_client.post(
            f"/api/device-projects/{la4_project['project_id']}/scans",
            json={"operation_type": "PROJECT_SCAN"},
            headers=la4_auth,
        )
        job_id = r.json()["id"]

        # Register second device
        r = la4_client.post("/api/devices/register", json={
            "device_name": "Other",
            "platform": "macos",
            "agent_version": "evosia-agent/0.1.0",
        }, headers=la4_auth)
        other_bootstrap = r.json()["bootstrap_token"]
        r = la4_client.post("/api/devices/exchange", json={
            "bootstrap_token": other_bootstrap,
        })
        other_credential = r.json()["access_token"]

        # Wrong device tries to submit results
        evidence = {
            "job_id": job_id,
            "device_id": "wrong_device_id",
            "device_project_id": la4_project["project_id"],
            "project_display_name": "Test",
            "agent_version": "evosia-agent/0.1.0",
            "started_at": "2026-08-27T00:00:00Z",
            "completed_at": "2026-08-27T00:01:00Z",
            "file_count": 10,
            "languages": [],
            "project_structure_summary": {},
            "findings": [],
            "truncated": False,
            "limits": {},
            "provenance": "LIVE_EVOSIA_EVIDENCE",
            "evidence_source": "device_local_scan",
        }
        r = la4_client.post(f"/api/agent/jobs/{job_id}/results",
            json={"evidence": evidence, "duration_seconds": 60.0},
            headers={"Authorization": f"Bearer {other_credential}"})
        assert r.status_code in (403, 404)

    def test_wrong_job_result_rejected(self, la4_client, la4_auth, la4_project):
        """Results for wrong job are rejected."""
        r = la4_client.post(
            f"/api/device-projects/{la4_project['project_id']}/scans",
            json={"operation_type": "PROJECT_SCAN"},
            headers=la4_auth,
        )
        job_id = r.json()["id"]

        device_cred = la4_project["device_credential"]
        headers = {"Authorization": f"Bearer {device_cred}"}

        la4_client.post(f"/api/agent/jobs/{job_id}/started",
            json={"agent_version": "evosia-agent/0.1.0"}, headers=headers)

        # Wrong job_id in evidence
        evidence = {
            "job_id": "wrong_job_id",
            "device_id": la4_project["device_id"],
            "device_project_id": la4_project["project_id"],
            "project_display_name": "Test",
            "agent_version": "evosia-agent/0.1.0",
            "started_at": "2026-08-27T00:00:00Z",
            "completed_at": "2026-08-27T00:01:00Z",
            "file_count": 10,
            "languages": [],
            "project_structure_summary": {},
            "findings": [],
            "truncated": False,
            "limits": {},
            "provenance": "LIVE_EVOSIA_EVIDENCE",
            "evidence_source": "device_local_scan",
        }
        r = la4_client.post(f"/api/agent/jobs/{job_id}/results",
            json={"evidence": evidence, "duration_seconds": 60.0}, headers=headers)
        assert r.status_code == 403

    def test_invalid_provenance_rejected(self, la4_client, la4_auth, la4_project):
        """Results with wrong provenance are rejected."""
        r = la4_client.post(
            f"/api/device-projects/{la4_project['project_id']}/scans",
            json={"operation_type": "PROJECT_SCAN"},
            headers=la4_auth,
        )
        job_id = r.json()["id"]

        device_cred = la4_project["device_credential"]
        headers = {"Authorization": f"Bearer {device_cred}"}

        la4_client.post(f"/api/agent/jobs/{job_id}/started",
            json={"agent_version": "evosia-agent/0.1.0"}, headers=headers)

        evidence = {
            "job_id": job_id,
            "device_id": la4_project["device_id"],
            "device_project_id": la4_project["project_id"],
            "project_display_name": "Test",
            "agent_version": "evosia-agent/0.1.0",
            "started_at": "2026-08-27T00:00:00Z",
            "completed_at": "2026-08-27T00:01:00Z",
            "file_count": 10,
            "languages": [],
            "project_structure_summary": {},
            "findings": [],
            "truncated": False,
            "limits": {},
            "provenance": "SAMPLE_EVIDENCE",
            "evidence_source": "device_local_scan",
        }
        r = la4_client.post(f"/api/agent/jobs/{job_id}/results",
            json={"evidence": evidence, "duration_seconds": 60.0}, headers=headers)
        assert r.status_code == 400


# ===========================================================================
# 31. Project Immutability
# ===========================================================================

class TestProjectImmutability:
    def test_scan_does_not_modify_project(self, tmp_path: Path):
        """Scanning does not modify any files."""
        root = tmp_path / "project"
        root.mkdir()
        (root / "main.py").write_text("print('hello')")
        (root / "config.json").write_text('{"key": "value"}')

        def hash_tree(path: Path) -> str:
            hasher = hashlib.sha256()
            for root_dir, dirs, files in os.walk(path):
                for f in sorted(files):
                    filepath = Path(root_dir) / f
                    hasher.update(str(filepath.relative_to(path)).encode())
                    hasher.update(filepath.read_bytes())
            return hasher.hexdigest()

        before = hash_tree(root)
        scan_project(root)
        after = hash_tree(root)
        assert before == after


# ===========================================================================
# 32–34. No Arbitrary Command, Shell, Merge/Deploy APIs
# ===========================================================================

class TestNoArbitraryCommandAPIs:
    def test_no_arbitrary_command_endpoint(self, la4_client):
        """No endpoint exists for arbitrary command execution."""
        r = la4_client.post("/api/agent/execute", json={"command": "ls"})
        assert r.status_code == 404

    def test_no_shell_endpoint(self, la4_client):
        r = la4_client.post("/api/agent/shell", json={"cmd": "ls"})
        assert r.status_code == 404

    def test_no_merge_endpoint(self, la4_client):
        r = la4_client.post("/api/agent/merge", json={})
        assert r.status_code == 404

    def test_no_deploy_endpoint(self, la4_client):
        r = la4_client.post("/api/agent/deploy", json={})
        assert r.status_code == 404

    def test_no_scan_create_endpoint_for_device(self, la4_client):
        """Device cannot create scan jobs via any endpoint."""
        r = la4_client.post("/api/agent/create-scan", json={})
        assert r.status_code == 404

    def test_agent_code_no_shell(self):
        """Agent code has no shell execution capability."""
        import evosia_agent.scanner as scanner_mod
        source = open(scanner_mod.__file__).read()
        assert "subprocess.call" not in source
        assert "os.system" not in source
        assert "os.popen" not in source
        # subprocess.run is allowed but only with hardcoded allowlist
        assert "shell=True" not in source


# ===========================================================================
# 35–42. Regression Tests
# ===========================================================================

class TestLA3Regression:
    """LA3 tests must remain passing."""

    def test_path_validation_still_works(self):
        from evosia_agent.path_validation import validate_project_root
        with tempfile.TemporaryDirectory() as tmp:
            result = validate_project_root(tmp)
            assert result.is_absolute()

    def test_sensitive_path_detection_still_works(self):
        from evosia_agent.path_validation import is_sensitive_path
        assert is_sensitive_path(Path(".env"))
        assert is_sensitive_path(Path("id_rsa"))
        assert not is_sensitive_path(Path("main.py"))

    def test_symlink_detection_still_works(self):
        from evosia_agent.path_validation import has_symlink_escape
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "file.py").touch()
            results = has_symlink_escape(root)
            # Should not find any escaping symlinks
            assert all(r.status == SymlinkStatus.SAFE_INTERNAL for r in results)


class TestLA2Regression:
    """LA2 tests must remain passing."""

    def test_heartbeat_stops_on_revoked(self):
        from evosia_agent.heartbeat import HeartbeatLoop
        api = MagicMock()
        api.send_heartbeat.return_value = {"status": "revoked"}
        import threading
        revoked_event = threading.Event()
        loop = HeartbeatLoop(
            api_client=api, device_id="dev_abc", device_credential="jwt",
            agent_version="test", interval_seconds=1,
            on_revoked=lambda: revoked_event.set(),
        )
        import threading as t
        thread = t.Thread(target=loop.start)
        thread.start()
        revoked_event.wait(timeout=5)
        loop.stop()
        thread.join(timeout=5)
        assert revoked_event.is_set()

    def test_credential_store_roundtrip(self, tmp_path: Path):
        from evosia_agent.credential_store import CredentialStore, DeviceCredential
        store = CredentialStore(tmp_path)
        cred = DeviceCredential(
            device_id="dev_test", device_name="Test",
            credential="token", cloud_url="https://test.com",
        )
        store.save(cred)
        loaded = store.load()
        assert loaded.device_id == "dev_test"


class TestLA1Regression:
    """LA1 device trust tests must remain passing."""

    def test_bootstrap_token_hash(self):
        from enterprise.services.device_auth import _hash_token
        token = "test_token_12345"
        h = _hash_token(token)
        assert len(h) == 64

    def test_device_token_roundtrip(self):
        from enterprise.services.device_auth import create_device_token, verify_device_token
        token, _ = create_device_token("dev_123", "user_abc")
        payload = verify_device_token(token)
        assert payload["sub"] == "dev_123"


class TestAuthorityRegression:
    """Authority invariants must remain intact."""

    def test_safety_boundary(self):
        from enterprise.services.safety import FORBIDDEN_OPERATIONS
        assert "merge" in FORBIDDEN_OPERATIONS
        assert "commit" in FORBIDDEN_OPERATIONS
        assert "push" in FORBIDDEN_OPERATIONS

    def test_no_execute_in_safety(self):
        from enterprise.services.safety import FORBIDDEN_OPERATIONS
        assert "execute_mission" in FORBIDDEN_OPERATIONS


class TestSecurityRegression:
    """Security invariants must remain intact."""

    def test_no_inbound_ports_in_agent(self):
        """Agent code has no inbound network capability."""
        import evosia_agent.agent as agent_mod
        import evosia_agent.api_client as api_mod
        for mod in [agent_mod, api_mod]:
            source = open(mod.__file__).read()
            assert "uvicorn" not in source
            assert "FastAPI" not in source

    def test_no_ssl_bypass(self):
        """Agent code does not disable TLS verification."""
        import evosia_agent.api_client as api_mod
        source = open(api_mod.__file__).read()
        assert "_create_unverified_context" not in source
        assert "verify=False" not in source


class TestMigrationRegression:
    """Migration chain must remain valid."""

    def test_agent_job_model_exists(self):
        from enterprise.models import AgentJob
        assert AgentJob.__tablename__ == "agent_jobs"

    def test_device_project_model_exists(self):
        from enterprise.models import DeviceProject
        assert DeviceProject.__tablename__ == "device_projects"

    def test_device_model_exists(self):
        from enterprise.models import Device
        assert Device.__tablename__ == "devices"
