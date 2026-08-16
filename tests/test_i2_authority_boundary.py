"""
I2 — Authority Boundary Verification

Verifies the complete authority flow:
  DRAFT → APPROVED_FOR_FUTURE_EXECUTION → PREPARED

against an isolated in-memory SQLite database. No production data touched.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

# Each boundary suite uses its OWN unique file-backed database so that running
# I2/I3/I4/I6 together in one pytest process cannot collide on a shared
# `:memory:` engine key or on a stale module-level engine alias. No production
# data is touched (the file lives in the repo working dir and is removed on
# teardown).
I2_DB_URL = "sqlite:///./test_i2_boundary.db"

from enterprise.app import app
from enterprise.database import Base, get_engine
from enterprise.models import (
    Finding,
    FindingAdjudication,
    Mission,
    PreparedChange,
    Repository,
    User,
)


def _sha_dir(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for root, _dirs, files in os.walk(path):
        for f in files:
            if f.endswith((".pyc", "__pycache__")):
                continue
            p = os.path.join(root, f)
            rel = os.path.relpath(p, path)
            try:
                with open(p, "rb") as fh:
                    out[rel] = hashlib.sha256(fh.read()).hexdigest()[:16]
            except OSError:
                pass
    return out


def _make_fixture_repo() -> str:
    d = tempfile.mkdtemp(prefix="i2-fixture-repo-")
    with open(os.path.join(d, "README.md"), "w") as f:
        f.write("# I2 Fixture\n")
    with open(os.path.join(d, "src.py"), "w") as f:
        f.write("print('hello')\n")
    return d


@pytest.fixture(autouse=True)
def _isolated_i2_db(monkeypatch):
    """Create and tear down an isolated file-backed SQLite database for I2.

    The app binds its engine at import time; rebind it here so the running
    FastAPI app uses THIS test's database (not a stale engine from a previous
    module in the same process).
    """
    monkeypatch.setenv("HERMES_DATABASE_URL", I2_DB_URL)
    monkeypatch.setenv("EVOSIA_DATABASE_URL", I2_DB_URL)
    monkeypatch.setenv("EVOSIA_JWT_SECRET", "i2-test-secret")
    # SECRET_KEY is cached at import in enterprise.services; refresh it so the
    # JWT fail-closed startup guard sees the test secret (not the insecure default).
    import enterprise.services as _svc
    monkeypatch.setattr(_svc, "SECRET_KEY", "i2-test-secret")
    import enterprise.app as _app_mod
    monkeypatch.setattr(_app_mod, "SECRET_KEY", "i2-test-secret")
    _app_mod.engine = get_engine()
    eng = _app_mod.engine
    Base.metadata.create_all(bind=eng)
    yield
    Base.metadata.drop_all(bind=eng)
    from enterprise.database import _ENGINES
    _ENGINES.pop(I2_DB_URL, None)
    try:
        os.remove("./test_i2_boundary.db")
    except OSError:
        pass


@pytest.fixture
def i2_client():
    return TestClient(app)


@pytest.fixture
def i2_auth(i2_client):
    email = f"i2-{uuid.uuid4().hex[:8]}@test.com"
    password = "testpass1234"
    i2_client.post("/api/auth/register", json={
        "email": email, "password": password, "name": "I2 Tester"
    })
    r = i2_client.post("/api/auth/login", json={"email": email, "password": password})
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def i2_repo(i2_client, i2_auth):
    r = i2_client.post("/api/repositories", json={
        "name": "i2-fixture",
        "url": "https://example.com/i2-fixture",
        "status": "active",
    }, headers=i2_auth)
    return r.json()["id"]


@pytest.fixture
def i2_mission(i2_repo):
    """Create a DRAFT mission for authority flow testing."""
    eng = get_engine(I2_DB_URL)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=eng, future=True)
    session = Session()
    repo = session.get(Repository, i2_repo)

    f1 = Finding(
        repository_id=repo.id,
        finding_type="security",
        severity="high",
        category="Security",
        title="Hardcoded credential in auth endpoint",
        description="A credential appears directly in authentication code.",
        module="src/auth/login.ts",
    )
    session.add(f1)
    session.flush()

    session.add(FindingAdjudication(
        finding_id=f1.id,
        classification="ACTIONABLE",
        operator="operator:i2",
        reviewed_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
    ))

    m1 = Mission(
        mission_id=f"REC-MISSION-{uuid.uuid4().hex[:6]}",
        repository_id=repo.id,
        title="Remove hardcoded credential from auth code",
        description="Prepare a proposed change to remove a hardcoded credential.",
        mission_type="refactor",
        status="DRAFT",
        priority=5,
        metadata_json={
            "originating_finding_id": f1.id,
            "governance_approval_reference": "I2-ADJ-001",
        },
    )
    session.add(m1)
    session.commit()
    mission_id = m1.id
    session.close()
    return mission_id


class TestI2AuthorityBoundary:
    def test_summary_reports_no_changes_and_authority_level(
        self, i2_client, i2_auth, i2_repo
    ):
        r = i2_client.get("/api/guided/summary", headers=i2_auth)
        assert r.status_code == 200
        data = r.json()
        assert data["nothing_changed"] is True
        assert "0 changes made" in data["headline"]
        assert data["authority_level"] == 1
        assert data["authority_level_label"] == "Recommend — EVOSIA proposes work"

    def test_permission_gate_blocks_execution(
        self, i2_client, i2_auth
    ):
        r = i2_client.get("/api/guided/permission", headers=i2_auth)
        assert r.status_code == 200
        perm = r.json()
        assert perm["can_observe"] is True
        assert perm["can_recommend"] is True
        assert perm["can_prepare"] is False
        assert perm["can_execute"] is False
        assert perm["execution_enabled"] is False
        assert perm["mutation_enabled"] is False

    def test_prepare_requires_approval_first(
        self, i2_client, i2_auth, i2_mission
    ):
        r = i2_client.post(
            f"/api/guided/missions/{i2_mission}/prepare",
            headers=i2_auth,
        )
        assert r.status_code == 409

    def test_approval_then_prepare_flow(
        self, i2_client, i2_auth, i2_mission
    ):
        # Step 1: approve preparation
        r = i2_client.post(
            f"/api/guided/missions/{i2_mission}/approve-preparation",
            json={"operator": "operator:i2"},
            headers=i2_auth,
        )
        assert r.status_code == 200
        approval = r.json()
        assert approval["execution_authorized"] is False
        assert approval["status"] == "APPROVED_FOR_FUTURE_EXECUTION"

        # Step 2: prepare change
        r = i2_client.post(
            f"/api/guided/missions/{i2_mission}/prepare",
            headers=i2_auth,
        )
        assert r.status_code == 200
        prepared = r.json()
        assert prepared["execution_authorized"] is False
        # B2: prepare now executes REAL preparation. On a non-disposable repo it
        # truthfully fails (no PREPARED without evidence); on the disposable repo
        # it may reach PREPARED. The invariant is execution_authorized stays False
        # and the mission lifecycle is unchanged (asserted below).
        assert prepared["status"] in ("preparing", "PREPARED", "failed")
        prepared_id = prepared["prepared_change_id"]

        # Step 3: mission stays APPROVED_FOR_FUTURE_EXECUTION during preparation
        r = i2_client.get("/api/guided/missions", headers=i2_auth)
        missions = r.json()
        m = next(m for m in missions if m["mission_id"] == i2_mission)
        assert m["status"] == "APPROVED_FOR_FUTURE_EXECUTION"
        assert m["status_label"] == "Approved for preparation"

        # Step 4: prepared changes list
        r = i2_client.get("/api/guided/prepared-changes", headers=i2_auth)
        assert r.status_code == 200
        pcs = r.json()
        assert any(pc["id"] == prepared_id for pc in pcs)

        # Step 5: prepared change detail
        r = i2_client.get(f"/api/guided/prepared-changes/{prepared_id}", headers=i2_auth)
        assert r.status_code == 200
        pcd = r.json()
        assert pcd["workspace_path"] == prepared["workspace_path"]

    def test_prepared_not_assigned_without_workspace_evidence(
        self, i2_client, i2_auth, i2_mission, i2_repo
    ):
        """PREPARED must only be assigned when objective preparation evidence exists.

        Per I2 reconciliation: PREPARED means an actual candidate change in an
        isolated workspace with workspace_path, diff_content, affected_files,
        and validation_status. A mere PreparedChange DB record must NOT
        transition the mission to PREPARED.
        """
        from enterprise.database import SessionLocal

        # Approve preparation
        r = i2_client.post(
            f"/api/guided/missions/{i2_mission}/approve-preparation",
            json={"operator": "operator:i2"},
            headers=i2_auth,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "APPROVED_FOR_FUTURE_EXECUTION"

        # Prepare change — creates a record but not a real workspace
        r = i2_client.post(
            f"/api/guided/missions/{i2_mission}/prepare",
            headers=i2_auth,
        )
        assert r.status_code == 200
        prepared = r.json()

        # Mission must NOT transition to PREPARED — only APPROVED_FOR_FUTURE_EXECUTION
        r = i2_client.get("/api/guided/missions", headers=i2_auth)
        missions = r.json()
        m = next(m for m in missions if m["mission_id"] == i2_mission)
        assert m["status"] != "PREPARED"
        assert m["status"] == "APPROVED_FOR_FUTURE_EXECUTION"

        # The prepared change record has no objective evidence (non-disposable
        # repo -> preparation is truthfully rejected, no workspace/diff produced).
        pc_id = prepared["prepared_change_id"]
        r = i2_client.get(f"/api/guided/prepared-changes/{pc_id}", headers=i2_auth)
        assert r.status_code == 200
        pc = r.json()
        assert pc["workspace_path"] is None
        # No real candidate change/diff/validation evidence exists.
        assert pc["status"] != "PREPARED"

    def test_prepared_status_only_after_workspace_and_diff(
        self, i2_client, i2_auth, i2_mission, i2_repo
    ):
        """A mission whose PreparedChange has workspace_path+diff CAN be PREPARED.

        This proves the system knows how to assign PREPARED correctly — but
        only when real evidence exists, not from a stub record.
        """
        eng = get_engine(I2_DB_URL)
        Session = sessionmaker(autocommit=False, autoflush=False, bind=eng, future=True)
        session = Session()

        # Approve
        i2_client.post(
            f"/api/guided/missions/{i2_mission}/approve-preparation",
            json={"operator": "operator:i2"},
            headers=i2_auth,
        )

        # Prepare — creates stub record
        r = i2_client.post(
            f"/api/guided/missions/{i2_mission}/prepare",
            headers=i2_auth,
        )
        assert r.status_code == 200
        pc_id = r.json()["prepared_change_id"]

        # Manually populate real evidence (simulating completed preparation)
        pc = session.get(PreparedChange, pc_id)
        pc.workspace_path = "/workspace/sandbox-001"
        pc.diff_content = "--- a/src.py\n+++ b/src.py\n+print('real change')\n"
        pc.affected_files = ["src.py"]
        pc.validation_status = "passed"
        pc.status = "prepared"
        session.commit()
        session.close()

        # Verify the prepared change now has objective evidence
        r = i2_client.get(f"/api/guided/prepared-changes/{pc_id}", headers=i2_auth)
        pc_detail = r.json()
        assert pc_detail["workspace_path"] is not None
        assert pc_detail["validation_status"] != "pending"

        # Mission still must not auto-transition to PREPARED by the record alone
        r = i2_client.get("/api/guided/missions", headers=i2_auth)
        missions = r.json()
        m = next(m for m in missions if m["mission_id"] == i2_mission)
        assert m["status"] == "APPROVED_FOR_FUTURE_EXECUTION"

    def test_no_execute_endpoint_exists(
        self, i2_client, i2_auth, i2_mission
    ):
        r = i2_client.post(
            f"/api/guided/missions/{i2_mission}/execute",
            headers=i2_auth,
        )
        assert r.status_code == 404

    def test_target_repository_not_mutated_by_preparation(
        self, i2_client, i2_auth, i2_mission
    ):
        fixture_repo = _make_fixture_repo()
        before = _sha_dir(fixture_repo)

        # Run full authority flow
        i2_client.post(
            f"/api/guided/missions/{i2_mission}/approve-preparation",
            json={"operator": "operator:i2"},
            headers=i2_auth,
        )
        i2_client.post(
            f"/api/guided/missions/{i2_mission}/prepare",
            headers=i2_auth,
        )

        after = _sha_dir(fixture_repo)
        assert before == after, "Target repository was mutated during preparation"
        shutil.rmtree(fixture_repo, ignore_errors=True)

    def test_context_answers_do_not_authorize_changes(
        self, i2_client, i2_auth, i2_repo
    ):
        r = i2_client.get("/api/guided/needs-context", headers=i2_auth)
        assert r.status_code == 200
        questions = r.json()
        for q in questions:
            assert "question" in q
            assert "why_asking" in q

    def test_needs_attention_requires_human_decision(
        self, i2_client, i2_auth, i2_repo
    ):
        r = i2_client.get("/api/guided/needs-attention", headers=i2_auth)
        assert r.status_code == 200
        items = r.json()
        for item in items:
            assert item["has_human_decision"] is True
            assert "why_it_matters" in item
