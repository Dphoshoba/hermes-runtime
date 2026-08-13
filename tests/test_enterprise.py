"""Comprehensive tests for the Engineering Command Center backend."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

# Set test database before importing app
os.environ["HERMES_DATABASE_URL"] = "sqlite:///./test_enterprise.db"

from enterprise.app import app
from enterprise.database import Base, get_engine, SessionLocal
from enterprise.models import User, Repository, JournalEvent, Finding, Mission, Report, ScanJob, ScanHistory
from enterprise.services import hash_password, create_access_token
from enterprise.services.scanner import SCAN_STAGES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def user(db) -> User:
    u = User(
        email="test@example.com",
        name="Test User",
        hashed_password=hash_password("password123"),
        is_admin=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def token(user) -> str:
    return create_access_token({"sub": user.id, "email": user.email})


@pytest.fixture
def auth_headers(token) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def repo(db, user) -> Repository:
    r = Repository(
        name="test-repo",
        url="https://github.com/test/repo",
        default_branch="main",
        language="Python",
        status="active",
        health_score=85.0,
        findings_count=5,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@pytest.fixture
def sample_events(db, repo) -> list[JournalEvent]:
    events = []
    for i, etype in enumerate([
        "readiness.assessed", "repo.scanned", "engineering.analyzed",
        "governance.decided", "mission.completed",
    ]):
        ev = JournalEvent(
            event_id=f"evt-{i:04d}",
            timestamp=f"2026-08-09T{10+i:02d}:00:00.000000Z",
            event_type=etype,
            stage=etype.split(".")[0],
            repository_id=repo.id,
            actor="system",
            payload={"index": i},
            payload_sha256=f"hash-{i:04d}",
        )
        db.add(ev)
        events.append(ev)
    db.commit()
    return events


@pytest.fixture
def sample_findings(db, repo) -> list[Finding]:
    findings = []
    for i, (sev, cat) in enumerate([
        ("critical", "Architecture"), ("high", "Testing"), ("medium", "Documentation"),
    ]):
        f = Finding(
            repository_id=repo.id,
            finding_type="debt",
            severity=sev,
            category=cat,
            title=f"Finding {i}: {cat} issue",
            description=f"Description for finding {i}",
            module=f"module_{i}.py",
            priority_score=8.0 - i,
            effort="medium",
            status="open",
        )
        db.add(f)
        findings.append(f)
    db.commit()
    return findings


@pytest.fixture
def sample_missions(db, repo) -> list[Mission]:
    missions = []
    for i, status in enumerate(["pending", "running", "completed"]):
        m = Mission(
            mission_id=f"mission-{i:04d}",
            repository_id=repo.id,
            title=f"Mission {i}",
            description=f"Mission description {i}",
            mission_type="remediation",
            status=status,
            priority=i,
        )
        db.add(m)
        missions.append(m)
    db.commit()
    return missions


@pytest.fixture
def sample_reports(db, repo, sample_missions) -> list[Report]:
    reports = []
    for m in sample_missions:
        if m.status == "completed":
            r = Report(
                mission_id=m.id,
                repository_id=repo.id,
                title=f"Report for {m.title}",
                status="COMPLETED",
                summary="All tasks completed successfully",
                report_data={"tasks_completed": 5, "tasks_failed": 0},
                duration_seconds=45.2,
                tasks_planned=5,
                tasks_completed=5,
                tasks_failed=0,
            )
            db.add(r)
            reports.append(r)
    db.commit()
    return reports


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    def test_health(self, client):
        res = client.get("/api/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class TestAuth:
    def test_register(self, client):
        res = client.post("/api/auth/register", json={
            "email": "new@example.com",
            "name": "New User",
            "password": "password123",
        })
        assert res.status_code == 201
        data = res.json()
        assert data["email"] == "new@example.com"
        assert data["name"] == "New User"
        assert "id" in data

    def test_register_duplicate(self, client, user):
        res = client.post("/api/auth/register", json={
            "email": "test@example.com",
            "name": "Another",
            "password": "password123",
        })
        assert res.status_code == 409

    def test_login_success(self, client, user):
        res = client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "password123",
        })
        assert res.status_code == 200
        assert "access_token" in res.json()

    def test_login_wrong_password(self, client, user):
        res = client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpassword",
        })
        assert res.status_code == 401

    def test_me_authenticated(self, client, auth_headers):
        res = client.get("/api/auth/me", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["email"] == "test@example.com"

    def test_me_unauthenticated(self, client):
        res = client.get("/api/auth/me")
        assert res.status_code == 401


# ---------------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------------

class TestRepositories:
    def test_list_empty(self, client, auth_headers):
        res = client.get("/api/repositories", headers=auth_headers)
        assert res.status_code == 200
        assert res.json() == []

    def test_create(self, client, auth_headers):
        res = client.post("/api/repositories", headers=auth_headers, json={
            "name": "my-repo",
            "url": "https://github.com/me/repo",
        })
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "my-repo"
        assert data["status"] == "active"

    def test_list_with_data(self, client, auth_headers, repo):
        res = client.get("/api/repositories", headers=auth_headers)
        assert res.status_code == 200
        assert len(res.json()) == 1
        assert res.json()[0]["name"] == "test-repo"

    def test_get_by_id(self, client, auth_headers, repo):
        res = client.get(f"/api/repositories/{repo.id}", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["id"] == repo.id

    def test_get_not_found(self, client, auth_headers):
        res = client.get("/api/repositories/nonexistent", headers=auth_headers)
        assert res.status_code == 404

    def test_update(self, client, auth_headers, repo):
        res = client.patch(f"/api/repositories/{repo.id}", headers=auth_headers, json={
            "language": "TypeScript",
        })
        assert res.status_code == 200
        assert res.json()["language"] == "TypeScript"

    def test_delete(self, client, auth_headers, repo):
        res = client.delete(f"/api/repositories/{repo.id}", headers=auth_headers)
        assert res.status_code == 204

    def test_filter_by_status(self, client, auth_headers, repo):
        res = client.get("/api/repositories?status=active", headers=auth_headers)
        assert res.status_code == 200
        assert len(res.json()) == 1

        res = client.get("/api/repositories?status=inactive", headers=auth_headers)
        assert res.status_code == 200
        assert len(res.json()) == 0


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class TestDashboard:
    def test_stats_empty(self, client, auth_headers):
        res = client.get("/api/dashboard/stats", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total_repositories"] == 0
        assert data["open_findings"] == 0
        assert data["total_missions"] == 0

    def test_stats_with_data(self, client, auth_headers, repo, sample_findings, sample_missions):
        res = client.get("/api/dashboard/stats", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total_repositories"] == 1
        assert data["total_findings"] == 3
        assert data["open_findings"] == 3
        assert data["critical_findings"] == 1
        assert data["high_findings"] == 1
        assert data["total_missions"] == 3
        assert data["pending_missions"] == 1
        assert data["running_missions"] == 1
        assert data["completed_missions"] == 1

    def test_activity(self, client, auth_headers, sample_events):
        res = client.get("/api/dashboard/activity", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 5
        assert len(data["events"]) == 5


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------

class TestJournal:
    def test_list_empty(self, client, auth_headers):
        res = client.get("/api/journal", headers=auth_headers)
        assert res.status_code == 200
        assert res.json() == []

    def test_list_with_data(self, client, auth_headers, sample_events):
        res = client.get("/api/journal", headers=auth_headers)
        assert res.status_code == 200
        assert len(res.json()) == 5

    def test_filter_by_event_type(self, client, auth_headers, sample_events):
        res = client.get("/api/journal?event_type=readiness.assessed", headers=auth_headers)
        assert res.status_code == 200
        assert len(res.json()) == 1
        assert res.json()[0]["event_type"] == "readiness.assessed"

    def test_filter_by_stage(self, client, auth_headers, sample_events):
        res = client.get("/api/journal?stage=readiness", headers=auth_headers)
        assert res.status_code == 200
        assert len(res.json()) == 1

    def test_get_event(self, client, auth_headers, sample_events):
        event_id = sample_events[0].event_id
        res = client.get(f"/api/journal/{event_id}", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["event_id"] == event_id

    def test_get_event_not_found(self, client, auth_headers):
        res = client.get("/api/journal/nonexistent", headers=auth_headers)
        assert res.status_code == 404

    def test_limit(self, client, auth_headers, sample_events):
        res = client.get("/api/journal?limit=2", headers=auth_headers)
        assert res.status_code == 200
        assert len(res.json()) == 2


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

class TestFindings:
    def test_list_empty(self, client, auth_headers):
        res = client.get("/api/findings", headers=auth_headers)
        assert res.status_code == 200
        assert res.json() == []

    def test_list_with_data(self, client, auth_headers, sample_findings):
        res = client.get("/api/findings", headers=auth_headers)
        assert res.status_code == 200
        assert len(res.json()) == 3

    def test_filter_by_severity(self, client, auth_headers, sample_findings):
        res = client.get("/api/findings?severity=critical", headers=auth_headers)
        assert res.status_code == 200
        assert len(res.json()) == 1
        assert res.json()[0]["severity"] == "critical"

    def test_filter_by_category(self, client, auth_headers, sample_findings):
        res = client.get("/api/findings?category=Testing", headers=auth_headers)
        assert res.status_code == 200
        assert len(res.json()) == 1

    def test_get_finding(self, client, auth_headers, sample_findings):
        fid = sample_findings[0].id
        res = client.get(f"/api/findings/{fid}", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["id"] == fid

    def test_get_finding_not_found(self, client, auth_headers):
        res = client.get("/api/findings/nonexistent", headers=auth_headers)
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# Missions
# ---------------------------------------------------------------------------

class TestMissions:
    def test_list_empty(self, client, auth_headers):
        res = client.get("/api/missions", headers=auth_headers)
        assert res.status_code == 200
        assert res.json() == []

    def test_list_with_data(self, client, auth_headers, sample_missions):
        res = client.get("/api/missions", headers=auth_headers)
        assert res.status_code == 200
        assert len(res.json()) == 3

    def test_filter_by_status(self, client, auth_headers, sample_missions):
        res = client.get("/api/missions?status=pending", headers=auth_headers)
        assert res.status_code == 200
        assert len(res.json()) == 1
        assert res.json()[0]["status"] == "pending"

    def test_filter_by_type(self, client, auth_headers, sample_missions):
        res = client.get("/api/missions?mission_type=remediation", headers=auth_headers)
        assert res.status_code == 200
        assert len(res.json()) == 3

    def test_get_mission(self, client, auth_headers, sample_missions):
        mid = sample_missions[0].id
        res = client.get(f"/api/missions/{mid}", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["id"] == mid

    def test_get_mission_not_found(self, client, auth_headers):
        res = client.get("/api/missions/nonexistent", headers=auth_headers)
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

class TestReports:
    def test_list_empty(self, client, auth_headers):
        res = client.get("/api/reports", headers=auth_headers)
        assert res.status_code == 200
        assert res.json() == []

    def test_list_with_data(self, client, auth_headers, sample_reports):
        res = client.get("/api/reports", headers=auth_headers)
        assert res.status_code == 200
        assert len(res.json()) == 1
        assert res.json()[0]["status"] == "COMPLETED"

    def test_get_report(self, client, auth_headers, sample_reports):
        rid = sample_reports[0].id
        res = client.get(f"/api/reports/{rid}", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["id"] == rid

    def test_get_report_not_found(self, client, auth_headers):
        res = client.get("/api/reports/nonexistent", headers=auth_headers)
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_full_workflow(self, client, auth_headers):
        """Register user -> create repo -> check dashboard -> list journal."""
        # Dashboard starts empty
        res = client.get("/api/dashboard/stats", headers=auth_headers)
        assert res.json()["total_repositories"] == 0

        # Create repo
        res = client.post("/api/repositories", headers=auth_headers, json={
            "name": "integration-repo",
            "url": "https://github.com/test/integration",
        })
        assert res.status_code == 201
        repo_id = res.json()["id"]

        # Dashboard shows repo
        res = client.get("/api/dashboard/stats", headers=auth_headers)
        assert res.json()["total_repositories"] == 1

        # List repos
        res = client.get("/api/repositories", headers=auth_headers)
        assert len(res.json()) == 1

        # Get repo
        res = client.get(f"/api/repositories/{repo_id}", headers=auth_headers)
        assert res.json()["name"] == "integration-repo"

    def test_unauthenticated_access_blocked(self, client):
        """All API endpoints require authentication."""
        for path in [
            "/api/repositories",
            "/api/dashboard/stats",
            "/api/journal",
            "/api/findings",
            "/api/missions",
            "/api/reports",
            "/api/auth/me",
        ]:
            res = client.get(path)
            assert res.status_code == 401, f"{path} should require auth"


# ---------------------------------------------------------------------------
# Scan Jobs — Create, Start, Cancel, Retry
# ---------------------------------------------------------------------------

class TestScanJobs:
    def test_create_scan_job(self, client, auth_headers, repo):
        res = client.post("/api/scans", headers=auth_headers, json={
            "repository_id": repo.id,
        })
        assert res.status_code == 201
        data = res.json()
        assert data["status"] == "pending"
        assert data["attempt"] == 1
        assert data["scan_type"] == "full"

    def test_create_scan_repo_not_found(self, client, auth_headers):
        res = client.post("/api/scans", headers=auth_headers, json={
            "repository_id": "nonexistent",
        })
        assert res.status_code == 404

    def test_list_scans(self, client, auth_headers, repo):
        client.post("/api/scans", headers=auth_headers, json={"repository_id": repo.id})
        res = client.get("/api/scans", headers=auth_headers)
        assert res.status_code == 200
        assert len(res.json()) == 1

    def test_get_scan(self, client, auth_headers, repo):
        create = client.post("/api/scans", headers=auth_headers, json={"repository_id": repo.id})
        scan_id = create.json()["id"]
        res = client.get(f"/api/scans/{scan_id}", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["id"] == scan_id

    def test_get_scan_not_found(self, client, auth_headers):
        res = client.get("/api/scans/nonexistent", headers=auth_headers)
        assert res.status_code == 404

    def test_start_scan(self, client, auth_headers, repo):
        create = client.post("/api/scans", headers=auth_headers, json={"repository_id": repo.id})
        scan_id = create.json()["id"]
        res = client.post(f"/api/scans/{scan_id}/start", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "completed"
        assert data["duration_seconds"] is not None
        assert data["duration_seconds"] >= 0

    def test_scan_has_stage_timings(self, client, auth_headers, repo):
        create = client.post("/api/scans", headers=auth_headers, json={"repository_id": repo.id})
        scan_id = create.json()["id"]
        res = client.post(f"/api/scans/{scan_id}/start", headers=auth_headers)
        data = res.json()
        timings = data["stage_timings"]
        assert isinstance(timings, dict)
        for stage in SCAN_STAGES:
            assert stage in timings
            assert "started_at" in timings[stage]
            assert "completed_at" in timings[stage]
            assert "duration_seconds" in timings[stage]

    def test_scan_history_recorded(self, client, auth_headers, repo):
        create = client.post("/api/scans", headers=auth_headers, json={"repository_id": repo.id})
        scan_id = create.json()["id"]
        client.post(f"/api/scans/{scan_id}/start", headers=auth_headers)
        res = client.get(f"/api/scans/{scan_id}/history", headers=auth_headers)
        assert res.status_code == 200
        history = res.json()
        assert len(history) >= 2
        stages = [h["stage"] for h in history]
        assert "completed" in stages

    def test_cancel_pending_scan(self, client, auth_headers, repo):
        create = client.post("/api/scans", headers=auth_headers, json={"repository_id": repo.id})
        scan_id = create.json()["id"]
        res = client.post(f"/api/scans/{scan_id}/cancel", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "cancelled"
        assert data["cancelled_at"] is not None
        assert data["cancellation_requested_at"] is not None

    def test_cancel_idempotent(self, client, auth_headers, repo):
        create = client.post("/api/scans", headers=auth_headers, json={"repository_id": repo.id})
        scan_id = create.json()["id"]
        client.post(f"/api/scans/{scan_id}/cancel", headers=auth_headers)
        res = client.post(f"/api/scans/{scan_id}/cancel", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["status"] == "cancelled"

    def test_cancel_completed_scan_no_effect(self, client, auth_headers, repo):
        create = client.post("/api/scans", headers=auth_headers, json={"repository_id": repo.id})
        scan_id = create.json()["id"]
        client.post(f"/api/scans/{scan_id}/start", headers=auth_headers)
        res = client.post(f"/api/scans/{scan_id}/cancel", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["status"] == "completed"

    def test_cancel_emits_journal_event(self, client, auth_headers, repo):
        create = client.post("/api/scans", headers=auth_headers, json={"repository_id": repo.id})
        scan_id = create.json()["id"]
        client.post(f"/api/scans/{scan_id}/cancel", headers=auth_headers)
        res = client.get("/api/journal?event_type=scan.cancelled", headers=auth_headers)
        assert res.status_code == 200
        events = res.json()
        assert len(events) == 1
        assert events[0]["payload"]["scan_id"] == scan_id

    def test_retry_failed_scan(self, client, auth_headers, repo):
        create = client.post("/api/scans", headers=auth_headers, json={"repository_id": repo.id})
        scan_id = create.json()["id"]
        client.post(f"/api/scans/{scan_id}/start", headers=auth_headers)
        db = SessionLocal()
        job = db.query(ScanJob).filter(ScanJob.id == scan_id).first()
        job.status = "failed"
        job.error_message = "test error"
        db.commit()
        db.close()

        res = client.post(f"/api/scans/{scan_id}/retry", headers=auth_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["attempt"] == 2
        assert data["previous_scan_id"] == scan_id
        assert data["status"] == "pending"

    def test_retry_cancelled_scan(self, client, auth_headers, repo):
        create = client.post("/api/scans", headers=auth_headers, json={"repository_id": repo.id})
        scan_id = create.json()["id"]
        client.post(f"/api/scans/{scan_id}/cancel", headers=auth_headers)

        res = client.post(f"/api/scans/{scan_id}/retry", headers=auth_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["attempt"] == 2
        assert data["previous_scan_id"] == scan_id

    def test_retry_completed_scan_rejected(self, client, auth_headers, repo):
        create = client.post("/api/scans", headers=auth_headers, json={"repository_id": repo.id})
        scan_id = create.json()["id"]
        client.post(f"/api/scans/{scan_id}/start", headers=auth_headers)

        res = client.post(f"/api/scans/{scan_id}/retry", headers=auth_headers)
        assert res.status_code == 400

    def test_retry_pending_scan_rejected(self, client, auth_headers, repo):
        create = client.post("/api/scans", headers=auth_headers, json={"repository_id": repo.id})
        scan_id = create.json()["id"]

        res = client.post(f"/api/scans/{scan_id}/retry", headers=auth_headers)
        assert res.status_code == 400

    def test_retry_emits_journal_event(self, client, auth_headers, repo):
        create = client.post("/api/scans", headers=auth_headers, json={"repository_id": repo.id})
        scan_id = create.json()["id"]
        db = SessionLocal()
        job = db.query(ScanJob).filter(ScanJob.id == scan_id).first()
        job.status = "failed"
        db.commit()
        db.close()

        client.post(f"/api/scans/{scan_id}/retry", headers=auth_headers)
        res = client.get("/api/journal?event_type=scan.retried", headers=auth_headers)
        assert len(res.json()) == 1

    def test_retry_lineage(self, client, auth_headers, repo):
        create = client.post("/api/scans", headers=auth_headers, json={"repository_id": repo.id})
        scan1_id = create.json()["id"]

        db = SessionLocal()
        job = db.query(ScanJob).filter(ScanJob.id == scan1_id).first()
        job.status = "failed"
        db.commit()
        db.close()

        res = client.post(f"/api/scans/{scan1_id}/retry", headers=auth_headers)
        scan2_id = res.json()["id"]
        assert scan2_id != scan1_id
        assert res.json()["previous_scan_id"] == scan1_id
        assert res.json()["attempt"] == 2

        db = SessionLocal()
        job2 = db.query(ScanJob).filter(ScanJob.id == scan2_id).first()
        job2.status = "failed"
        db.commit()
        db.close()

        res2 = client.post(f"/api/scans/{scan2_id}/retry", headers=auth_headers)
        assert res2.json()["attempt"] == 3
        assert res2.json()["previous_scan_id"] == scan2_id
        db.close()

    def test_scan_timing_values_are_numeric(self, client, auth_headers, repo):
        create = client.post("/api/scans", headers=auth_headers, json={"repository_id": repo.id})
        scan_id = create.json()["id"]
        res = client.post(f"/api/scans/{scan_id}/start", headers=auth_headers)
        timings = res.json()["stage_timings"]
        for stage, timing in timings.items():
            assert isinstance(timing["duration_seconds"], (int, float))


# ---------------------------------------------------------------------------
# Dashboard Activity & Overnight
# ---------------------------------------------------------------------------

class TestDashboardActivity:
    def test_activity_v2_empty(self, client, auth_headers):
        res = client.get("/api/dashboard/activity-v2", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["repositories_total"] == 0
        assert data["scans_queued"] == 0

    def test_activity_v2_with_data(self, client, auth_headers, repo, sample_findings):
        res = client.get("/api/dashboard/activity-v2", headers=auth_headers)
        data = res.json()
        assert data["repositories_total"] == 1
        assert data["new_findings_since"] >= 3

    def test_activity_v2_with_since(self, client, auth_headers, repo):
        future = "2099-01-01T00:00:00Z"
        res = client.get(f"/api/dashboard/activity-v2?since={future}", headers=auth_headers)
        data = res.json()
        assert data["new_findings_since"] == 0

    def test_activity_v2_malformed_timestamp(self, client, auth_headers):
        res = client.get("/api/dashboard/activity-v2?since=not-a-date", headers=auth_headers)
        assert res.status_code == 200

    def test_overnight_empty(self, client, auth_headers):
        res = client.get("/api/dashboard/overnight", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["successful_scans"] == 0
        assert data["failed_scans"] == 0
        assert "summary" in data

    def test_overnight_with_scans(self, client, auth_headers, repo):
        create = client.post("/api/scans", headers=auth_headers, json={"repository_id": repo.id})
        scan_id = create.json()["id"]
        client.post(f"/api/scans/{scan_id}/start", headers=auth_headers)

        res = client.get("/api/dashboard/overnight", headers=auth_headers)
        data = res.json()
        assert data["successful_scans"] >= 1
        assert data["repositories_scanned"] >= 1

    def test_overnight_custom_window(self, client, auth_headers, repo):
        res = client.get(
            "/api/dashboard/overnight?window_start=2020-01-01T00:00:00Z&window_end=2099-12-31T23:59:59Z",
            headers=auth_headers,
        )
        assert res.status_code == 200

    def test_overnight_malformed_timestamps(self, client, auth_headers):
        res = client.get("/api/dashboard/overnight?window_start=bad", headers=auth_headers)
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# Auth boundaries
# ---------------------------------------------------------------------------

class TestAuthBoundaries:
    def test_scans_require_auth(self, client):
        for method, path in [
            ("GET", "/api/scans"),
            ("POST", "/api/scans"),
        ]:
            res = getattr(client, method.lower())(path)
            assert res.status_code == 401, f"{method} {path} should require auth"

    def test_scan_start_requires_auth(self, client):
        res = client.post("/api/scans/fake/start")
        assert res.status_code == 401

    def test_scan_cancel_requires_auth(self, client):
        res = client.post("/api/scans/fake/cancel")
        assert res.status_code == 401

    def test_scan_retry_requires_auth(self, client):
        res = client.post("/api/scans/fake/retry")
        assert res.status_code == 401

    def test_activity_v2_requires_auth(self, client):
        res = client.get("/api/dashboard/activity-v2")
        assert res.status_code == 401

    def test_overnight_requires_auth(self, client):
        res = client.get("/api/dashboard/overnight")
        assert res.status_code == 401

    def test_repo_sync_requires_auth(self, client):
        res = client.post("/api/repositories/fake/sync")
        assert res.status_code == 401
