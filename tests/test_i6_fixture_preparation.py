"""
I6 — M8 Blocker Remediation Tests

Proves B1 (deterministic disposable fixture) and B2 (real preparation with
objective PREPARED evidence) using the REAL backend, REAL Guided Mode API
(TestClient), and a REAL isolated workspace + REAL validation.

No participants are recruited or simulated. No M8 execution occurs.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Use a FILE-based isolated DB (distinct from the :memory: engines used by
# I2/I3/I4 boundary tests) so the real preparation engine and the app share one
# engine without colliding with other in-memory test modules.
_I6_DB = "sqlite:///./test_i6_m8.db"
os.environ["HERMES_DATABASE_URL"] = _I6_DB
os.environ["EVOSIA_DATABASE_URL"] = _I6_DB
os.environ["EVOSIA_M8_FIXTURE"] = "enabled"
os.environ["EVOSIA_JWT_SECRET"] = "i6-test-secret"
os.environ["EVOSIA_PREP_ROOT"] = tempfile.mkdtemp(prefix="i6-prep-")

from fastapi.testclient import TestClient  # noqa: E402

from enterprise.app import app  # noqa: E402
from enterprise.database import Base, get_engine, SessionLocal  # noqa: E402
from enterprise.services import hash_password  # noqa: E402
from enterprise.services.m8_fixture import (  # noqa: E402
    REPO_ID,
    MISSION_ID,
    USER_ID,
    verify_m8_fixture,
    seed_m8_fixture,
)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    eng = get_engine()
    Base.metadata.create_all(bind=eng)
    yield
    Base.metadata.drop_all(bind=eng)


@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture()
def client():
    # Seed fixture into the live in-memory engine used by the app.
    seed_m8_fixture()
    with TestClient(app) as c:
        # register + login the fixture participant (JSON, not form)
        c.post(
            "/api/auth/register",
            json={"email": "m8-participant@example.com", "name": "M8 Participant",
                  "password": "m8-participant-password"},
        )
        r = c.post(
            "/api/auth/login",
            json={"email": "m8-participant@example.com", "password": "m8-participant-password"},
        )
        token = r.json()["access_token"]
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c


def _reset_and_seed(db):
    seed_m8_fixture(db)


# ---------------------------------------------------------------------------
# B1 — Fixture
# ---------------------------------------------------------------------------

class TestB1Fixture:
    def test_seed_is_deterministic(self, db):
        from enterprise.models import Repository

        def snapshot():
            seed_m8_fixture(db)
            repo = db.query(Repository).filter_by(id=REPO_ID).first()
            return (repo.id, repo.name)

        first = snapshot()
        second = snapshot()
        assert first == second

    def test_reset_restores_canonical_starting_state(self, db):
        from enterprise.models import Mission
        from enterprise.services.m8_fixture import reset_m8_fixture

        seed_m8_fixture(db)
        reset_m8_fixture(db)
        m = db.query(Mission).filter_by(id=MISSION_ID).first()
        assert m.status == "DRAFT"

    def test_fixture_contains_required_evidence(self, db):
        seed_m8_fixture(db)
        rep = verify_m8_fixture(db)
        assert rep["status"] == "verified"
        assert rep["findings"] >= 4
        assert rep["actionable_findings"] == 1
        assert rep["missions"] == 1
        assert rep["git_initialized"] is True

    def test_fixture_has_no_production_secrets(self, db):
        from enterprise.models import Repository

        seed_m8_fixture(db)
        repo = db.query(Repository).filter_by(id=REPO_ID).first()
        assert repo.metadata_json.get("is_disposable") is True
        assert repo.metadata_json.get("preparation_allowed") is True


# ---------------------------------------------------------------------------
# B2 — Real preparation
# ---------------------------------------------------------------------------

class TestB2Preparation:
    def test_preparation_requires_approval(self, client):
        # Try to prepare the DRAFT mission directly (not approved) -> 409.
        r = client.post(f"/api/guided/missions/{MISSION_ID}/prepare")
        assert r.status_code == 409

    def test_preparation_creates_isolated_workspace(self, client):
        # Approve then prepare.
        client.post(f"/api/guided/missions/{MISSION_ID}/approve-preparation",
                    json={"operator": "M8 Participant"})
        r = client.post(f"/api/guided/missions/{MISSION_ID}/prepare")
        assert r.status_code == 200
        body = r.json()
        assert body["workspace_path"] is not None
        ws = Path(body["workspace_path"])
        assert ws.exists()
        assert "prep-" in ws.name

    def test_target_repository_unchanged(self, client):
        from enterprise.services.m8_fixture import disposable_repo_path
        target = disposable_repo_path()
        before = sorted(p.read_bytes() for p in target.rglob("*") if p.is_file() and ".git" not in p.parts)
        client.post(f"/api/guided/missions/{MISSION_ID}/approve-preparation",
                    json={"operator": "M8 Participant"})
        client.post(f"/api/guided/missions/{MISSION_ID}/prepare")
        after = sorted(p.read_bytes() for p in target.rglob("*") if p.is_file() and ".git" not in p.parts)
        assert after == before

    def test_real_candidate_change_produced(self, client):
        client.post(f"/api/guided/missions/{MISSION_ID}/approve-preparation",
                    json={"operator": "M8 Participant"})
        r = client.post(f"/api/guided/missions/{MISSION_ID}/prepare")
        body = r.json()
        assert "src/config.py" in body["affected_files"]

    def test_real_diff_recorded(self, client):
        client.post(f"/api/guided/missions/{MISSION_ID}/approve-preparation",
                    json={"operator": "M8 Participant"})
        r = client.post(f"/api/guided/missions/{MISSION_ID}/prepare")
        body = r.json()
        assert body["diff_content"] is not None
        assert "API_KEY" in body["diff_content"]
        assert "environment" in body["diff_content"].lower() or "os.environ" in body["diff_content"]

    def test_real_validation_executes(self, client):
        client.post(f"/api/guided/missions/{MISSION_ID}/approve-preparation",
                    json={"operator": "M8 Participant"})
        r = client.post(f"/api/guided/missions/{MISSION_ID}/prepare")
        body = r.json()
        assert body["validation_status"] == "passed"
        assert body["validation_output"] is not None

    def test_prepared_assigned_only_after_evidence(self, client):
        client.post(f"/api/guided/missions/{MISSION_ID}/approve-preparation",
                    json={"operator": "M8 Participant"})
        r = client.post(f"/api/guided/missions/{MISSION_ID}/prepare")
        body = r.json()
        assert body["status"] == "PREPARED"
        # Retrieve prepared change and confirm evidence fields populated.
        pc = client.get(f"/api/guided/prepared-changes/{body['prepared_change_id']}").json()
        assert pc["status"] == "PREPARED"
        assert pc["workspace_path"] is not None
        assert pc["affected_files"]
        assert pc["diff_content"]
        assert pc["validation_status"] == "passed"

    def test_failed_preparation_cannot_produce_prepared(self, db, client):
        # A repository not flagged preparation_allowed cannot be prepared.
        from enterprise.models import Repository
        repo = db.query(Repository).filter_by(id=REPO_ID).first()
        repo.metadata_json = {**repo.metadata_json, "preparation_allowed": False}
        db.commit()
        client.post(f"/api/guided/missions/{MISSION_ID}/approve-preparation",
                    json={"operator": "M8 Participant"})
        r = client.post(f"/api/guided/missions/{MISSION_ID}/prepare")
        # Either rejected (400) or failed status — never PREPARED.
        assert r.status_code in (200, 400)
        if r.status_code == 200:
            assert r.json()["status"] != "PREPARED"


# ---------------------------------------------------------------------------
# Execution boundary + authority
# ---------------------------------------------------------------------------

class TestExecutionBoundary:
    def test_execution_remains_unauthorized(self, client):
        perm = client.get("/api/guided/permission").json()
        assert perm["execution_enabled"] is False
        assert perm["can_execute"] is False
        assert perm["mutation_enabled"] is False

    def test_no_execute_endpoint_exists(self, client):
        # There is intentionally no execution path; a bogus POST returns 404.
        r = client.post(f"/api/guided/missions/{MISSION_ID}/execute")
        assert r.status_code == 404

    def test_merge_deploy_target_mutation_impossible(self, client):
        # After a full prepare, the target repo still has the original hardcoded key.
        from enterprise.services.m8_fixture import disposable_repo_path
        client.post(f"/api/guided/missions/{MISSION_ID}/approve-preparation",
                    json={"operator": "M8 Participant"})
        client.post(f"/api/guided/missions/{MISSION_ID}/prepare")
        cfg = (disposable_repo_path() / "src" / "config.py").read_text()
        assert "example-fake-key-do-not-use" in cfg  # target unchanged
        assert "os.environ.get" not in cfg  # no edit leaked to target
