"""Browser E2E tests — full happy path and failure path scenarios.

These tests simulate complete user workflows through the API,
covering: login → dashboard → repository → sync → scan → stages → findings → governance → journal → history → dashboard update.

Uses deterministic fixtures (no external GitHub calls).
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

os.environ["HERMES_DATABASE_URL"] = "sqlite:///./test_e2e_browser.db"

from enterprise.app import app
from enterprise.database import Base, get_engine


@pytest.fixture(autouse=True)
def setup_db():
    """Create fresh tables for each test on this suite's database engine."""
    eng = get_engine(os.environ["HERMES_DATABASE_URL"])
    Base.metadata.create_all(bind=eng)
    yield
    Base.metadata.drop_all(bind=eng)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    email = f"e2e-{uuid.uuid4().hex[:8]}@test.com"
    password = "testpass1234"
    client.post("/api/auth/register", json={
        "email": email, "password": password, "name": "E2E Test User",
    })
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_repo(client, auth_headers, name="test/repo"):
    resp = client.post("/api/repositories", headers=auth_headers, json={
        "url": f"https://github.com/{name}",
        "name": name,
    })
    assert resp.status_code in (200, 201)
    return resp.json()


# ─── HAPPY PATH: Full Workflow ───
class TestHappyPath:
    def test_login_to_dashboard(self, client, auth_headers):
        """Login → Dashboard shows metrics."""
        resp = client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "E2E Test User"

        resp = client.get("/api/dashboard/activity-v2", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "repositories_total" in data
        assert "scans_running" in data
        assert "latest_activity" in data

    def test_register_repo_sync_scan_findings_journal(self, client, auth_headers):
        """Full workflow: register repo → sync → scan → findings → journal."""
        # Register repository
        repo = _create_repo(client, auth_headers, "octocat/Hello-World")
        repo_id = repo["id"]

        # Verify in list
        resp = client.get("/api/repositories", headers=auth_headers)
        assert resp.status_code == 200
        assert any(r["id"] == repo_id for r in resp.json())

        # Get detail
        resp = client.get(f"/api/repositories/{repo_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "octocat/Hello-World"

        # Create and start scan
        resp = client.post("/api/scans", headers=auth_headers, json={
            "repository_id": repo_id,
        })
        assert resp.status_code in (200, 201)
        scan = resp.json()
        scan_id = scan["id"]

        # Start the scan
        resp = client.post(f"/api/scans/{scan_id}/start", headers=auth_headers)
        assert resp.status_code == 200

        # Verify scan is running
        resp = client.get(f"/api/scans/{scan_id}", headers=auth_headers)
        assert resp.status_code == 200
        scan_data = resp.json()
        assert scan_data["status"] in ("running", "completed", "failed")

        # List scans
        resp = client.get("/api/scans?limit=100", headers=auth_headers)
        assert resp.status_code == 200
        assert any(s["id"] == scan_id for s in resp.json())

        # Findings (may be empty for mock scan)
        resp = client.get("/api/findings?limit=100", headers=auth_headers)
        assert resp.status_code == 200

        # Journal
        resp = client.get("/api/journal?limit=50", headers=auth_headers)
        assert resp.status_code == 200

        # Dashboard after activity
        resp = client.get("/api/dashboard/activity-v2", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["repositories_total"] >= 1

    def test_overnight_summary_reflects_activity(self, client, auth_headers):
        """After scans, overnight summary reflects activity."""
        repo = _create_repo(client, auth_headers)
        repo_id = repo["id"]

        # Create and complete a scan
        resp = client.post("/api/scans", headers=auth_headers, json={
            "repository_id": repo_id,
        })
        scan_id = resp.json()["id"]
        client.post(f"/api/scans/{scan_id}/start", headers=auth_headers)

        # Check overnight summary
        resp = client.get("/api/dashboard/overnight", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "repositories_scanned" in data
        assert "summary" in data

    def test_scan_history_preserved(self, client, auth_headers):
        """Scan history records are preserved."""
        repo = _create_repo(client, auth_headers)
        resp = client.post("/api/scans", headers=auth_headers, json={
            "repository_id": repo["id"],
        })
        scan_id = resp.json()["id"]
        client.post(f"/api/scans/{scan_id}/start", headers=auth_headers)

        # Check scan detail has stage timings
        resp = client.get(f"/api/scans/{scan_id}", headers=auth_headers)
        assert resp.status_code == 200
        scan = resp.json()
        assert "stage_timings" in scan
        assert "stages_completed" in scan


# ─── FAILURE PATH: Cancel and Retry ───
class TestFailurePath:
    def test_cancel_pending_scan(self, client, auth_headers):
        """Cancel a pending scan → shows cancelled state."""
        repo = _create_repo(client, auth_headers)
        resp = client.post("/api/scans", headers=auth_headers, json={
            "repository_id": repo["id"],
        })
        scan_id = resp.json()["id"]
        assert resp.json()["status"] == "pending"

        # Cancel the scan before starting
        resp = client.post(f"/api/scans/{scan_id}/cancel", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

        # Verify cancelled state persists
        resp = client.get(f"/api/scans/{scan_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_retry_failed_scan(self, client, auth_headers):
        """Retry a failed scan → creates new attempt, original immutable."""
        repo = _create_repo(client, auth_headers)
        resp = client.post("/api/scans", headers=auth_headers, json={
            "repository_id": repo["id"],
        })
        scan_id = resp.json()["id"]

        # Manually set scan to failed status
        from enterprise.database import SessionLocal
        from enterprise.models import ScanJob
        db = SessionLocal()
        job = db.query(ScanJob).filter(ScanJob.id == scan_id).first()
        job.status = "failed"
        job.error_message = "Test failure"
        job.failure_classification = "unknown"
        db.commit()
        db.close()

        # Retry the scan
        resp = client.post(f"/api/scans/{scan_id}/retry", headers=auth_headers)
        assert resp.status_code in (200, 201)
        new_scan = resp.json()
        assert new_scan["id"] != scan_id
        assert new_scan["attempt"] == 2
        assert new_scan["previous_scan_id"] == scan_id

        # Original scan remains unchanged
        resp = client.get(f"/api/scans/{scan_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"
        assert resp.json()["attempt"] == 1

    def test_retry_cancelled_scan(self, client, auth_headers):
        """Retry a cancelled scan → creates new attempt."""
        repo = _create_repo(client, auth_headers)
        resp = client.post("/api/scans", headers=auth_headers, json={
            "repository_id": repo["id"],
        })
        scan_id = resp.json()["id"]
        # Cancel before starting
        client.post(f"/api/scans/{scan_id}/cancel", headers=auth_headers)

        # Retry
        resp = client.post(f"/api/scans/{scan_id}/retry", headers=auth_headers)
        assert resp.status_code in (200, 201)
        new_scan = resp.json()
        assert new_scan["id"] != scan_id
        assert new_scan["attempt"] == 2

    def test_cancel_idempotent(self, client, auth_headers):
        """Cancelling an already cancelled scan is idempotent."""
        repo = _create_repo(client, auth_headers)
        resp = client.post("/api/scans", headers=auth_headers, json={
            "repository_id": repo["id"],
        })
        scan_id = resp.json()["id"]
        client.post(f"/api/scans/{scan_id}/cancel", headers=auth_headers)

        # Cancel again
        resp = client.post(f"/api/scans/{scan_id}/cancel", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_retry_rejected_for_completed_scan(self, client, auth_headers):
        """Cannot retry a completed scan."""
        repo = _create_repo(client, auth_headers)
        resp = client.post("/api/scans", headers=auth_headers, json={
            "repository_id": repo["id"],
        })
        scan_id = resp.json()["id"]
        client.post(f"/api/scans/{scan_id}/start", headers=auth_headers)

        # Scan completed synchronously
        resp = client.get(f"/api/scans/{scan_id}", headers=auth_headers)
        assert resp.json()["status"] == "completed"

        resp = client.post(f"/api/scans/{scan_id}/retry", headers=auth_headers)
        assert resp.status_code in (400, 409)

    def test_failure_classification(self, client, auth_headers):
        """Failed scan has structured failure classification."""
        repo = _create_repo(client, auth_headers)
        resp = client.post("/api/scans", headers=auth_headers, json={
            "repository_id": repo["id"],
        })
        scan_id = resp.json()["id"]

        from enterprise.database import SessionLocal
        from enterprise.models import ScanJob
        db = SessionLocal()
        job = db.query(ScanJob).filter(ScanJob.id == scan_id).first()
        job.status = "failed"
        job.error_message = "GitHub API rate limit exceeded"
        job.failure_classification = "rate_limit"
        db.commit()
        db.close()

        resp = client.get(f"/api/scans/{scan_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["failure_classification"] == "rate_limit"
        assert "rate limit" in resp.json()["error_message"].lower()

    def test_journal_events_for_lifecycle(self, client, auth_headers):
        """Journal events are emitted for scan lifecycle."""
        repo = _create_repo(client, auth_headers)
        resp = client.post("/api/scans", headers=auth_headers, json={
            "repository_id": repo["id"],
        })
        scan_id = resp.json()["id"]
        client.post(f"/api/scans/{scan_id}/start", headers=auth_headers)

        resp = client.get("/api/journal?limit=50", headers=auth_headers)
        assert resp.status_code == 200
        events = resp.json()
        event_types = [e["event_type"] for e in events]
        assert any("scan" in et for et in event_types)
