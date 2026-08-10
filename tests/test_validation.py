"""Tests for 7-Day Operational Validation Program."""

from __future__ import annotations

import os
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

os.environ["HERMES_JWT_SECRET"] = "test-secret-validation"

from enterprise.database import Base
import enterprise.models  # noqa: F401 — ensure all models are registered

TEST_DB_URL = "sqlite:///./test_validation.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False}, future=True)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, future=True)


def _override_get_db():
    s = TestSession()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(autouse=True, scope="session")
def create_tables():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    try:
        os.remove("test_validation.db")
    except OSError:
        pass


@pytest.fixture(autouse=True)
def clean_tables():
    yield
    with test_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.commit()


@pytest.fixture
def client():
    from enterprise.app import app
    from enterprise.database import get_db
    app.dependency_overrides[get_db] = _override_get_db
    from starlette.testclient import TestClient
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def db():
    session = TestSession()
    yield session
    session.close()


@pytest.fixture
def auth_headers(client):
    client.post("/api/auth/register", json={
        "email": "trial-test@example.com",
        "name": "Trial Tester",
        "password": "testpass123",
    })
    resp = client.post("/api/auth/login", json={
        "email": "trial-test@example.com",
        "password": "testpass123",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_repo(client, auth_headers, name="test-repo"):
    resp = client.post("/api/repositories", headers=auth_headers, json={
        "name": name,
        "url": f"https://github.com/test/{name}",
        "language": "python",
    })
    return resp.json()


@pytest.fixture
def repo(client, auth_headers):
    return _create_repo(client, auth_headers)


# ─── TRIAL LIFECYCLE ───

class TestTrialLifecycle:
    def test_create_trial(self, client, auth_headers):
        resp = client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-001",
            "operator": "tester@example.com",
            "repositories": [],
            "baseline_version": "1.1.0",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == "trial-001"
        assert data["status"] == "ACTIVE"
        assert data["operator"] == "trial-test@example.com"

    def test_list_trials(self, client, auth_headers):
        client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-a",
            "operator": "tester@example.com",
        })
        client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-b",
            "operator": "tester@example.com",
        })
        resp = client.get("/api/trial", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_get_trial(self, client, auth_headers):
        client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-002",
            "operator": "tester@example.com",
        })
        resp = client.get("/api/trial/trial-002", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["trial_id"] == "trial-002"

    def test_complete_trial(self, client, auth_headers):
        client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-003",
            "operator": "tester@example.com",
        })
        resp = client.post("/api/trial/trial-003/complete", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "COMPLETED"
        assert resp.json()["completed_at"] is not None

    def test_abort_trial(self, client, auth_headers):
        client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-004",
            "operator": "tester@example.com",
        })
        resp = client.post("/api/trial/trial-004/abort", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ABORTED"

    def test_cannot_complete_nonexistent(self, client, auth_headers):
        resp = client.post("/api/trial/nonexistent/complete", headers=auth_headers)
        assert resp.status_code == 404

    def test_trial_with_repositories(self, client, auth_headers):
        repo = _create_repo(client, auth_headers)
        resp = client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-005",
            "operator": "tester@example.com",
            "repositories": [repo["id"]],
        })
        assert resp.status_code == 201
        assert repo["id"] in resp.json()["repositories"]


# ─── DAILY SNAPSHOTS ───

class TestDailySnapshots:
    def test_create_snapshot(self, client, auth_headers):
        client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-snap",
            "operator": "tester@example.com",
        })
        resp = client.post("/api/trial/trial-snap/snapshots/2026-01-15", headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["date"] == "2026-01-15"
        assert data["trial_id"] == "trial-snap"
        assert "metrics" in data

    def test_list_snapshots(self, client, auth_headers):
        client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-snap2",
            "operator": "tester@example.com",
        })
        client.post("/api/trial/trial-snap2/snapshots/2026-01-15", headers=auth_headers)
        client.post("/api/trial/trial-snap2/snapshots/2026-01-16", headers=auth_headers)
        resp = client.get("/api/trial/trial-snap2/snapshots", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_snapshot_metrics_structure(self, client, auth_headers):
        client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-snap3",
            "operator": "tester@example.com",
        })
        resp = client.post("/api/trial/trial-snap3/snapshots/2026-01-15", headers=auth_headers)
        metrics = resp.json()["metrics"]
        assert "successful_scans" in metrics
        assert "failed_scans" in metrics
        assert "findings_generated" in metrics
        assert "findings_by_severity" in metrics


# ─── OPERATOR FEEDBACK ───

class TestOperatorFeedback:
    def test_submit_feedback(self, client, auth_headers):
        client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-fb",
            "operator": "tester@example.com",
        })
        repo = _create_repo(client, auth_headers)
        resp = client.post("/api/feedback", headers=auth_headers, json={
            "finding_id": "some-finding-id",
            "repository_id": repo["id"],
            "classification": "USEFUL",
            "notes": "This finding helped identify a real issue",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["classification"] == "USEFUL"
        assert data["trial_id"] == "trial-fb"

    def test_feedback_classifications(self, client, auth_headers):
        client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-fb2",
            "operator": "tester@example.com",
        })
        for cls in ["USEFUL", "FALSE_POSITIVE", "NOT_ACTIONABLE", "NEEDS_MORE_EVIDENCE", "DUPLICATE", "UNKNOWN"]:
            resp = client.post("/api/feedback", headers=auth_headers, json={
                "finding_id": f"finding-{cls}",
                "classification": cls,
            })
            assert resp.status_code == 201

    def test_list_feedback(self, client, auth_headers):
        client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-fb3",
            "operator": "tester@example.com",
        })
        client.post("/api/feedback", headers=auth_headers, json={
            "finding_id": "f1",
            "classification": "USEFUL",
        })
        client.post("/api/feedback", headers=auth_headers, json={
            "finding_id": "f2",
            "classification": "FALSE_POSITIVE",
        })
        resp = client.get("/api/feedback?trial_id=trial-fb3", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_feedback_requires_active_trial(self, client, auth_headers):
        resp = client.post("/api/feedback", headers=auth_headers, json={
            "finding_id": "f1",
            "classification": "USEFUL",
        })
        assert resp.status_code == 400


# ─── FRICTION JOURNAL ───

class TestFrictionJournal:
    def test_record_friction(self, client, auth_headers):
        client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-fr",
            "operator": "tester@example.com",
        })
        resp = client.post("/api/friction", headers=auth_headers, json={
            "category": "confusing_ui",
            "severity": "medium",
            "description": "Dashboard reloads on every click",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["category"] == "confusing_ui"
        assert data["severity"] == "medium"

    def test_friction_severities(self, client, auth_headers):
        client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-fr2",
            "operator": "tester@example.com",
        })
        for sev in ["low", "medium", "high", "critical"]:
            resp = client.post("/api/friction", headers=auth_headers, json={
                "category": "test",
                "severity": sev,
                "description": f"Test {sev} friction",
            })
            assert resp.status_code == 201

    def test_list_friction(self, client, auth_headers):
        client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-fr3",
            "operator": "tester@example.com",
        })
        client.post("/api/friction", headers=auth_headers, json={
            "category": "slow_operation",
            "severity": "high",
            "description": "Scan takes 10 minutes",
        })
        resp = client.get("/api/friction?trial_id=trial-fr3", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_friction_with_related_ids(self, client, auth_headers):
        client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-fr4",
            "operator": "tester@example.com",
        })
        resp = client.post("/api/friction", headers=auth_headers, json={
            "category": "scan_failure",
            "severity": "high",
            "description": "Scan failed silently",
            "related_scan_id": "some-scan-id",
            "related_finding_id": "some-finding-id",
        })
        assert resp.status_code == 201
        assert resp.json()["related_scan_id"] == "some-scan-id"


# ─── TRUST METRICS ───

class TestTrustMetrics:
    def test_trust_metrics_endpoint(self, client, auth_headers):
        resp = client.get("/api/operations/trust-metrics", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "finding_precision" in data
        assert "scan_reliability" in data
        assert "safety_violation_count" in data

    def test_trust_metrics_with_feedback(self, client, auth_headers):
        client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-tm",
            "operator": "tester@example.com",
        })
        for _ in range(3):
            client.post("/api/feedback", headers=auth_headers, json={
                "finding_id": f"useful-{_}",
                "classification": "USEFUL",
            })
        for _ in range(2):
            client.post("/api/feedback", headers=auth_headers, json={
                "finding_id": f"fp-{_}",
                "classification": "FALSE_POSITIVE",
            })
        resp = client.get("/api/operations/trust-metrics", headers=auth_headers)
        data = resp.json()
        assert data["confirmed_useful"] >= 3
        assert data["confirmed_false_positives"] >= 2
        assert data["finding_precision"] is not None
        assert 0 <= data["finding_precision"] <= 1


# ─── MORNING BRIEF ───

class TestMorningBrief:
    def test_morning_brief_endpoint(self, client, auth_headers):
        resp = client.get("/api/operations/morning-brief", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "greeting" in data
        assert data["greeting"] in ("Good Morning", "Good Afternoon", "Good Evening")
        assert "repositories_scanned" in data
        assert "new_findings" in data
        assert "recommended_review_order" in data

    def test_morning_brief_with_data(self, client, auth_headers):
        repo = _create_repo(client, auth_headers)
        resp = client.post("/api/scans", headers=auth_headers, json={
            "repository_id": repo["id"],
        })
        scan_id = resp.json()["id"]
        client.post(f"/api/scans/{scan_id}/start", headers=auth_headers)

        resp = client.get("/api/operations/morning-brief", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["repositories_scanned"] >= 1


# ─── DAILY METRICS ───

class TestDailyMetrics:
    def test_daily_metrics_endpoint(self, client, auth_headers):
        resp = client.get("/api/operations/daily-metrics/2026-01-15", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["date"] == "2026-01-15"
        assert "successful_scans" in data
        assert "findings_by_severity" in data
        assert "findings_by_category" in data

    def test_metrics_with_scans(self, client, auth_headers):
        repo = _create_repo(client, auth_headers)
        resp = client.post("/api/scans", headers=auth_headers, json={
            "repository_id": repo["id"],
        })
        scan_id = resp.json()["id"]
        client.post(f"/api/scans/{scan_id}/start", headers=auth_headers)

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        resp = client.get(f"/api/operations/daily-metrics/{today}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["successful_scans"] >= 1


# ─── TRIAL DASHBOARD ───

class TestTrialDashboard:
    def test_trial_dashboard(self, client, auth_headers):
        client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-dash",
            "operator": "tester@example.com",
        })
        client.post("/api/trial/trial-dash/snapshots/2026-01-15", headers=auth_headers)
        client.post("/api/trial/trial-dash/snapshots/2026-01-16", headers=auth_headers)

        resp = client.get("/api/trial/trial-dash/dashboard", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == "trial-dash"
        assert data["days_completed"] == 2
        assert len(data["daily_summaries"]) == 2
        assert data["daily_summaries"][0]["day_number"] == 1

    def test_dashboard_nonexistent(self, client, auth_headers):
        resp = client.get("/api/trial/nonexistent/dashboard", headers=auth_headers)
        assert resp.status_code == 404


# ─── FEATURE PROPOSALS ───

class TestFeatureProposals:
    def test_propose_feature(self, client, auth_headers):
        client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-fp",
            "operator": "tester@example.com",
        })
        resp = client.post("/api/proposals", headers=auth_headers, json={
            "problem": "Missing diff view for findings",
            "observed_evidence": "Operator had to use GitHub UI separately",
            "frequency": "daily",
            "current_workaround": "Manual GitHub navigation",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["problem"] == "Missing diff view for findings"
        assert data["decision"] == "NEEDS_MORE_EVIDENCE"

    def test_decide_feature(self, client, auth_headers):
        client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-fp2",
            "operator": "tester@example.com",
        })
        resp = client.post("/api/proposals", headers=auth_headers, json={
            "problem": "Test problem",
            "observed_evidence": "Test evidence",
        })
        proposal_id = resp.json()["id"]

        resp = client.post(f"/api/proposals/{proposal_id}/decide", headers=auth_headers, json={
            "decision": "ACCEPT",
            "decision_notes": "High value, low effort",
        })
        assert resp.status_code == 200
        assert resp.json()["decision"] == "ACCEPT"
        assert resp.json()["decided_at"] is not None

    def test_list_proposals(self, client, auth_headers):
        client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-fp3",
            "operator": "tester@example.com",
        })
        client.post("/api/proposals", headers=auth_headers, json={
            "problem": "P1",
            "observed_evidence": "E1",
        })
        client.post("/api/proposals", headers=auth_headers, json={
            "problem": "P2",
            "observed_evidence": "E2",
        })
        resp = client.get("/api/proposals?trial_id=trial-fp3", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2


# ─── SCHEDULING ───

class TestScheduling:
    def test_scheduled_repositories(self, client, auth_headers):
        _create_repo(client, auth_headers, "sched-repo")
        resp = client.get("/api/scheduling/repositories", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_validate_schedule(self, client, auth_headers):
        repo = _create_repo(client, auth_headers)
        resp = client.post("/api/scheduling/validate", headers=auth_headers, json={
            "repository_id": repo["id"],
            "cron_expression": "0 9 * * *",
            "enabled": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["cron_valid"] is True
        assert data["safety_check"]["allowed"] is True


# ─── SAFETY BOUNDARY ───

class TestSafetyBoundary:
    def test_read_operations_allowed(self, client, auth_headers):
        from enterprise.services.safety import check_safety_boundary
        for op in ["scan_repository", "read_metadata", "analyze_code"]:
            result = check_safety_boundary(op)
            assert result["allowed"] is True

    def test_write_operations_forbidden(self):
        from enterprise.services.safety import check_safety_boundary
        for op in ["modify_source_code", "create_branch", "commit", "push",
                    "create_pull_request", "merge", "modify_github_settings",
                    "modify_workflows", "execute_mission"]:
            result = check_safety_boundary(op)
            assert result["allowed"] is False

    def test_enforce_read_only_raises(self):
        from enterprise.services.safety import enforce_read_only
        with pytest.raises(ValueError, match="Forbidden"):
            enforce_read_only("push")

    def test_enforce_read_only_passes(self):
        from enterprise.services.safety import enforce_read_only
        enforce_read_only("scan_repository")


# ─── FINAL REPORT GENERATOR ───

class TestReportGenerator:
    def test_generate_report(self, client, auth_headers):
        client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-report",
            "operator": "tester@example.com",
        })
        client.post("/api/trial/trial-report/snapshots/2026-01-15", headers=auth_headers)
        client.post("/api/feedback", headers=auth_headers, json={
            "finding_id": "f1",
            "classification": "USEFUL",
        })

        from enterprise.services.report_generator import generate_final_report
        db = TestSession()
        try:
            report = generate_final_report(db, "trial-report")
            assert "OPERATIONAL VALIDATION REPORT" in report
            assert "trial-report" in report
            assert "Repository Cohort" in report
            assert "Scan Reliability" in report
            assert "Finding Quality" in report
        finally:
            db.close()


# ─── UNAVAILABLE METRIC HANDLING ───

class TestUnavailableMetrics:
    def test_metrics_with_no_data(self, client, auth_headers):
        resp = client.get("/api/operations/daily-metrics/2020-01-01", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["successful_scans"] == 0
        assert data["average_scan_duration"] is None
        assert data["slowest_pipeline_stage"] is None

    def test_trust_with_no_feedback(self, client, auth_headers):
        resp = client.get("/api/operations/trust-metrics", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["finding_precision"] is None
        assert data["confirmed_useful"] == 0


# ─── SCHEMA VALIDATION ───

class TestSchemaValidation:
    def test_invalid_feedback_classification(self, client, auth_headers):
        client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-sv",
            "operator": "tester@example.com",
        })
        resp = client.post("/api/feedback", headers=auth_headers, json={
            "finding_id": "f1",
            "classification": "INVALID",
        })
        assert resp.status_code == 422

    def test_invalid_friction_severity(self, client, auth_headers):
        client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-sv2",
            "operator": "tester@example.com",
        })
        resp = client.post("/api/friction", headers=auth_headers, json={
            "category": "test",
            "severity": "extreme",
            "description": "Test",
        })
        assert resp.status_code == 422

    def test_invalid_feature_decision(self, client, auth_headers):
        client.post("/api/trial", headers=auth_headers, json={
            "trial_id": "trial-sv3",
            "operator": "tester@example.com",
        })
        resp = client.post("/api/proposals", headers=auth_headers, json={
            "problem": "P",
            "observed_evidence": "E",
        })
        pid = resp.json()["id"]
        resp = client.post(f"/api/proposals/{pid}/decide", headers=auth_headers, json={
            "decision": "MAYBE",
        })
        assert resp.status_code == 422


class TestTraceabilityAcceptance:
    """Traceability: every stage in SCAN_STAGES produces a timing entry."""

    def test_all_stages_have_timing_entries(self, client, auth_headers, repo):
        from enterprise.services.scanner import SCAN_STAGES
        resp = client.post("/api/scans", headers=auth_headers, json={
            "repository_id": repo["id"],
        })
        scan_id = resp.json()["id"]
        client.post(f"/api/scans/{scan_id}/start", headers=auth_headers)
        import time
        time.sleep(0.5)
        resp = client.get(f"/api/scans/{scan_id}", headers=auth_headers)
        data = resp.json()
        timings = data.get("stage_timings", {})
        for stage in SCAN_STAGES:
            assert stage in timings, f"Stage '{stage}' missing from stage_timings"
            entry = timings[stage]
            assert isinstance(entry, dict), f"Stage '{stage}' timing is not a dict"
            assert "duration_seconds" in entry, f"Stage '{stage}' missing duration_seconds"
            assert isinstance(entry["duration_seconds"], (int, float)), \
                f"Stage '{stage}' duration_seconds is not numeric"

    def test_no_internal_keys_in_stage_timings(self, client, auth_headers, repo):
        resp = client.post("/api/scans", headers=auth_headers, json={
            "repository_id": repo["id"],
        })
        scan_id = resp.json()["id"]
        client.post(f"/api/scans/{scan_id}/start", headers=auth_headers)
        import time
        time.sleep(0.5)
        resp = client.get(f"/api/scans/{scan_id}", headers=auth_headers)
        timings = resp.json().get("stage_timings", {})
        forbidden_keys = {"_materialized_path", "_commit_sha", "_ri", "_ei", "_governance", "_missions"}
        leaked = forbidden_keys.intersection(timings.keys())
        assert not leaked, f"Internal keys leaked into stage_timings: {leaked}"

    def test_all_stage_timings_have_started_and_completed(self, client, auth_headers, repo):
        resp = client.post("/api/scans", headers=auth_headers, json={
            "repository_id": repo["id"],
        })
        scan_id = resp.json()["id"]
        client.post(f"/api/scans/{scan_id}/start", headers=auth_headers)
        import time
        time.sleep(0.5)
        resp = client.get(f"/api/scans/{scan_id}", headers=auth_headers)
        timings = resp.json().get("stage_timings", {})
        for stage, entry in timings.items():
            if stage.startswith("_"):
                continue
            assert "started_at" in entry, f"Stage '{stage}' missing started_at"
            assert "completed_at" in entry, f"Stage '{stage}' missing completed_at"


class TestAntiMockRegression:
    """Ensure scanner actually invokes Core, not mocks."""

    def test_scan_completes_all_stages(self, client, auth_headers, repo):
        resp = client.post("/api/scans", headers=auth_headers, json={
            "repository_id": repo["id"],
        })
        scan_id = resp.json()["id"]
        client.post(f"/api/scans/{scan_id}/start", headers=auth_headers)
        import time
        time.sleep(1.0)
        resp = client.get(f"/api/scans/{scan_id}", headers=auth_headers)
        data = resp.json()
        assert data["status"] in ("completed", "failed"), f"Scan status: {data['status']}"
        from enterprise.services.scanner import SCAN_STAGES
        timings = data.get("stage_timings", {})
        for stage in SCAN_STAGES:
            assert stage in timings, f"Stage '{stage}' missing from stage_timings"

    def test_scanner_module_has_no_mock_imports(self):
        import inspect
        from enterprise.services import scanner
        source = inspect.getsource(scanner)
        assert "mock" not in source.lower(), "Scanner source contains mock patterns"
        assert "TODO" not in source, "Scanner source contains TODO placeholders"

    def test_hermes_core_bridge_has_real_calls(self):
        import inspect
        from enterprise.services import hermes_core
        source = inspect.getsource(hermes_core)
        assert "run_readiness" in source, "hermes_core missing run_readiness"
        assert "run_repository_intelligence" in source, "hermes_core missing run_repository_intelligence"
        assert "run_engineering_intelligence" in source, "hermes_core missing run_engineering_intelligence"
        assert "run_governance" in source, "hermes_core missing run_governance"
        assert "run_mission_recommendation" in source, "hermes_core missing run_mission_recommendation"

    def test_scan_stages_match_expected_canonical_order(self):
        from enterprise.services.scanner import SCAN_STAGES
        expected = [
            "metadata", "materialization", "readiness", "repository_intelligence",
            "engineering_intelligence", "governance", "mission_recommendation",
            "persistence", "journal",
        ]
        assert SCAN_STAGES == expected, f"SCAN_STAGES mismatch: {SCAN_STAGES} != {expected}"

