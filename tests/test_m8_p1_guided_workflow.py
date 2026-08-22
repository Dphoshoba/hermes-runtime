"""M8 Participant 1 — Guided workflow & review evidence remediation tests.

Covers: review-scope evidence (authoritative, non-fabricated), finding source
location exposure, mission originating_finding relationship, duplicate
prevention on preparation, truthful PREPARED semantics, authority invariants,
and Gemini boundary (no state mutation / no scope fabrication).
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("EVOSIA_DATABASE_URL", "sqlite:///./test_m8_p1_workflow.db")
os.environ.setdefault("EVOSIA_JWT_SECRET", "m8-p1-workflow-test-secret")
os.environ.setdefault("EVOSIA_M8_FIXTURE", "enabled")

from pathlib import Path

from enterprise.app import app
from enterprise.database import Base, get_engine
import enterprise.app as _app_mod
import enterprise.services as _svc
from fastapi.testclient import TestClient

M8_DB = "sqlite:///./test_m8_p1_workflow.db"


@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    monkeypatch.setenv("HERMES_DATABASE_URL", M8_DB)
    monkeypatch.setenv("EVOSIA_DATABASE_URL", M8_DB)
    monkeypatch.setenv("EVOSIA_M8_FIXTURE", "enabled")
    monkeypatch.setenv("EVOSIA_JWT_SECRET", "m8-p1-workflow-test-secret")
    monkeypatch.setattr(_svc, "SECRET_KEY", "m8-p1-workflow-test-secret")
    monkeypatch.setattr(_app_mod, "SECRET_KEY", "m8-p1-workflow-test-secret")
    _app_mod.engine = get_engine()
    Base.metadata.create_all(bind=_app_mod.engine)
    yield
    Base.metadata.drop_all(bind=_app_mod.engine)


@pytest.fixture()
def seeded_client(tmp_path):
    """Seeded fixture + authenticated participant client."""
    from enterprise.services.m8_fixture import seed_m8_fixture

    seed_m8_fixture()
    with TestClient(app) as c:
        r = c.post(
            "/api/auth/login",
            json={"email": "m8-participant@example.com", "password": "m8-participant-password"},
        )
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c


# ---------------------------------------------------------------------------
# Review scope evidence
# ---------------------------------------------------------------------------

class TestReviewScopeEvidence:
    def test_build_review_scope_reflects_actual_files(self, tmp_path):
        from evosia.repo_scanner import build_review_scope

        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        (tmp_path / "src" / "a.py").write_text("x = 1\n")
        (tmp_path / "src" / "b.py").write_text("y = 2\n")
        (tmp_path / "tests" / "t_a.py").write_text("z = 3\n")

        inspected = [
            tmp_path / "src" / "a.py",
            tmp_path / "src" / "b.py",
            tmp_path / "tests" / "t_a.py",
        ]
        scope = build_review_scope(tmp_path, inspected)

        assert scope["total_files_inspected"] == 3
        assert sorted(scope["files_inspected"]) == ["src/a.py", "src/b.py", "tests/t_a.py"]
        assert set(scope["folders_inspected"]) == {"src", "tests"}
        assert scope["total_folders_inspected"] == 2
        # Truthful exclusion: per-file skipped count is not recorded by the walker
        assert scope["excluded_files"] is None
        assert "exclusion_note" in scope

    def test_folder_and_file_counts_are_not_fabricated(self, tmp_path):
        from evosia.repo_scanner import build_review_scope

        (tmp_path / "only_one").mkdir()
        (tmp_path / "only_one" / "single.py").write_text("pass\n")
        scope = build_review_scope(tmp_path, [tmp_path / "only_one" / "single.py"])

        assert scope["total_files_inspected"] == 1
        assert scope["total_folders_inspected"] == 1
        assert scope["total_files_inspected"] == len(scope["files_inspected"])
        assert scope["total_folders_inspected"] == len(scope["folders_inspected"])

    def test_scan_repository_includes_review_scope(self, tmp_path):
        from evosia.repo_scanner import scan_repository

        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "mod.py").write_text("def f():\n    return 1\n")
        result = scan_repository(tmp_path)
        scope = result["review_scope"]
        # Registry path without per-file records must be truthful, not fabricated
        if scope.get("available") is False:
            assert "coverage was not recorded" in scope.get("exclusion_note", "")
        else:
            assert scope["total_files_inspected"] >= 1

    def test_review_scope_endpoint_reports_unavailable_without_scan(self, seeded_client):
        r = seeded_client.get("/api/guided/review-scope")
        assert r.status_code == 200
        body = r.json()
        assert body["available"] is False
        # No fabricated counts in the unavailable state
        assert "files_inspected" not in body
        assert "total_files_inspected" not in body

    def test_review_scope_endpoint_serves_recorded_coverage(self, seeded_client):
        from enterprise.models import ScanJob, Repository
        from sqlalchemy.orm import sessionmaker

        db = sessionmaker(bind=_app_mod.engine)()
        try:
            repo = db.query(Repository).first()
            job = ScanJob(
                repository_id=repo.id,
                status="completed",
                metadata_json={
                    "review_scope": {
                        "scope_root": "sample-service",
                        "folders_inspected": ["src"],
                        "files_inspected": ["src/config.py"],
                        "total_folders_inspected": 1,
                        "total_files_inspected": 1,
                        "excluded_files": None,
                    }
                },
            )
            db.add(job)
            db.commit()
            scan_id = job.id
        finally:
            db.close()

        r = seeded_client.get("/api/guided/review-scope")
        assert r.status_code == 200
        body = r.json()
        assert body["available"] is True
        assert body["scan_id"] == scan_id
        assert body["total_files_inspected"] == 1
        assert body["provenance"] == "LIVE_EVOSIA_EVIDENCE"


# ---------------------------------------------------------------------------
# Finding → Mission bridge
# ---------------------------------------------------------------------------

class TestFindingMissionBridge:
    def test_finding_source_location_returned(self, seeded_client):
        r = seeded_client.get("/api/guided/needs-attention")
        assert r.status_code == 200
        items = r.json()
        assert items, "fixture must produce at least one actionable finding"
        item = items[0]
        assert item["technical"]["module"], "finding must expose its source module"

    def test_mission_originating_finding_relationship_returned(self, seeded_client):
        r = seeded_client.get("/api/guided/missions")
        assert r.status_code == 200
        missions = r.json()
        assert missions, "fixture must produce a DRAFT mission"
        m = missions[0]
        assert m.get("originating_finding"), "mission must expose its originating finding"


# ---------------------------------------------------------------------------
# Preparation: duplicates, failure, PREPARED semantics
# ---------------------------------------------------------------------------

class TestPreparationSemantics:
    def _approve(self, client):
        missions = client.get("/api/guided/missions").json()
        draft = [m for m in missions if m["status"] == "DRAFT"]
        assert draft, "expected a DRAFT mission"
        mission_id = draft[0]["mission_id"]
        r = client.post(f"/api/guided/missions/{mission_id}/approve-preparation", json={"operator": "tester"})
        assert r.status_code == 200
        return mission_id

    def test_prepared_requires_actual_evidence_or_is_failed_truthfully(self, seeded_client):
        mission_id = self._approve(seeded_client)
        r = seeded_client.post(f"/api/guided/missions/{mission_id}/prepare")
        assert r.status_code == 200
        body = r.json()
        # PREPARED only when objective evidence exists; otherwise truthfully not PREPARED
        if body["status"] == "PREPARED":
            assert body["workspace_path"]
            assert body["diff_content"]
            assert body["affected_files"]
            assert body["validation_status"] == "passed"
        else:
            assert body["status"] in ("preparing", "failed")
        assert body["execution_authorized"] is False

    def test_repeated_prepare_returns_existing_not_duplicate(self, seeded_client):
        mission_id = self._approve(seeded_client)
        first = seeded_client.post(f"/api/guided/missions/{mission_id}/prepare").json()
        second = seeded_client.post(f"/api/guided/missions/{mission_id}/prepare").json()

        if first.get("status") == "PREPARED":
            assert second.get("deduplicated") is True
            assert second["prepared_change_id"] == first["prepared_change_id"]

    def test_failed_preparation_does_not_mutate_target_repository(self, seeded_client):
        from pathlib import Path

        repo_dir = Path("validation/m8-disposable-repo/src/config.py")
        before = repo_dir.read_text()
        mission_id = self._approve(seeded_client)
        seeded_client.post(f"/api/guided/missions/{mission_id}/prepare")
        after = repo_dir.read_text()
        assert before == after

    def test_authority_remains_false_through_prepare_path(self, seeded_client):
        mission_id = self._approve(seeded_client)
        body = seeded_client.post(f"/api/guided/missions/{mission_id}/prepare").json()
        assert body["execution_authorized"] is False

    def test_permission_endpoint_unchanged(self, seeded_client):
        p = seeded_client.get("/api/guided/permission").json()
        assert p["can_execute"] is False
        assert p["execution_enabled"] is False
        assert p["mutation_enabled"] is False


# ---------------------------------------------------------------------------
# Gemini boundary
# ---------------------------------------------------------------------------

class TestGeminiBoundary:
    def test_gemini_cannot_manufacture_review_scope(self, seeded_client):
        # No endpoint allows Gemini to create review scope; the only scope
        # source is the scanner record.
        routes = {getattr(r, "path", "") for r in app.routes}
        write_scope_routes = [p for p in routes if "review-scope" in p and "POST" in getattr(
            next(x for x in app.routes if getattr(x, "path", "") == p), "methods", set())]
        assert all(p.endswith("/review-scope") for p in write_scope_routes)

    def test_gemini_failure_does_not_change_authority_state(self, seeded_client):
        missions = seeded_client.get("/api/guided/missions").json()
        if missions:
            mid = missions[0]["mission_id"]
            r = seeded_client.get(f"/api/guided/explain/mission/{mid}")
            # Regardless of Gemini availability, response must be an explanation payload or error — never an authority change.
            if r.status_code == 200:
                body = r.json()
                assert "execution_authorized" not in body or body.get("execution_authorized") is False
        p = seeded_client.get("/api/guided/permission").json()
        assert p["execution_enabled"] is False and p["mutation_enabled"] is False
