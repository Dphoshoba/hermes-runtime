"""M1 — Guided Mode End-to-End Contract Test."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

os.environ["HERMES_DATABASE_URL"] = "sqlite:///./test_guided_e2e.db"

import pytest
from fastapi.testclient import TestClient

from enterprise.app import app
from enterprise.database import Base, get_engine


@pytest.fixture(autouse=True)
def setup_db():
    eng = get_engine(os.environ["HERMES_DATABASE_URL"])
    Base.metadata.create_all(bind=eng)
    yield
    Base.metadata.drop_all(bind=eng)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    email = f"guided-{uuid.uuid4().hex[:8]}@test.com"
    password = "testpass1234"
    client.post("/api/auth/register", json={
        "email": email, "password": password, "name": "Guided Test User",
    })
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_data(client, auth_headers):
    """Seed a small repository with findings for Guided Mode E2E."""
    from enterprise.database import get_engine, sessionmaker
    from enterprise.models import Repository, Finding, FindingAdjudication, Mission
    eng = get_engine(os.environ["HERMES_DATABASE_URL"])
    Session = sessionmaker(autocommit=False, autoflush=False, bind=eng, future=True)
    session = Session()
    repo = Repository(name="test-project", url="https://example.com/test", status="active")
    session.add(repo)
    session.flush()

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
    adj1 = FindingAdjudication(
        finding_id=f1.id,
        classification="ACTIONABLE",
        operator="operator:test",
        reviewed_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
    )
    session.add(adj1)

    f2 = Finding(
        repository_id=repo.id,
        finding_type="complexity",
        severity="medium",
        category="Complexity",
        title="Large Module: AssessmentList.tsx",
        description="A module may be larger than ideal.",
        module="src/components/assessment/AssessmentList.tsx",
    )
    session.add(f2)

    m1 = Mission(
        mission_id="REC-MISSION-001",
        repository_id=repo.id,
        title="Remove hardcoded credential from auth code",
        description="Prepare a proposed change to remove a hardcoded credential.",
        mission_type="refactor",
        status="DRAFT",
        priority=5,
        metadata_json={"originating_finding_id": f1.id, "governance_approval_reference": "HUMAN-ADJUDICATION-FINDING-001"},
    )
    session.add(m1)
    session.commit()
    session.close()


class TestGuidedModeE2E:
    def test_summary_shows_plain_language_headline(self, client, auth_headers):
        _seed_data(client, auth_headers)
        r = client.get("/api/guided/summary", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "headline" in data
        assert "things examined" in data["headline"]
        assert "0 changes made" in data["headline"]
        assert data["nothing_changed"] is True
        assert data["total_findings"] >= 2

    def test_needs_attention_shows_actionable_items(self, client, auth_headers):
        _seed_data(client, auth_headers)
        r = client.get("/api/guided/needs-attention", headers=auth_headers)
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        for item in items:
            assert "finding_id" in item
            assert "why_it_matters" in item
            assert item["has_human_decision"] is True

    def test_needs_context_clusters_nme(self, client, auth_headers):
        _seed_data(client, auth_headers)
        r = client.get("/api/guided/needs-context", headers=auth_headers)
        assert r.status_code == 200
        questions = r.json()
        assert len(questions) >= 1
        for q in questions:
            assert "question" in q
            assert "why_asking" in q
            assert "affects_count" in q
            assert q["affects_count"] >= 1

    def test_missions_explain_consequences(self, client, auth_headers):
        _seed_data(client, auth_headers)
        r = client.get("/api/guided/missions", headers=auth_headers)
        assert r.status_code == 200
        missions = r.json()
        assert len(missions) >= 1
        for m in missions:
            assert "authority_consequence" in m
            text = m["authority_consequence"].lower()
            assert "not" in text or "will not" in text

    def test_prepare_requires_approval_first(self, client, auth_headers):
        _seed_data(client, auth_headers)
        r = client.get("/api/guided/missions", headers=auth_headers)
        missions = r.json()
        draft = next((m for m in missions if m["status"] == "DRAFT"), None)
        if draft:
            r2 = client.post(f"/api/guided/missions/{draft['mission_id']}/prepare", headers=auth_headers)
            assert r2.status_code == 409

    def test_approval_then_prepare_is_non_executing(self, client, auth_headers):
        _seed_data(client, auth_headers)
        r = client.get("/api/guided/missions", headers=auth_headers)
        missions = r.json()
        draft = next((m for m in missions if m["status"] == "DRAFT"), None)
        if draft:
            r2 = client.post(
                f"/api/guided/missions/{draft['mission_id']}/approve-preparation",
                json={"operator": "operator:test"},
                headers=auth_headers,
            )
            assert r2.status_code == 200
            assert r2.json()["execution_authorized"] is False

            r3 = client.post(f"/api/guided/missions/{draft['mission_id']}/prepare", headers=auth_headers)
            assert r3.status_code == 200
            assert r3.json()["execution_authorized"] is False

    def test_permission_level_visible(self, client, auth_headers):
        _seed_data(client, auth_headers)
        r = client.get("/api/guided/permission", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["can_observe"] is True
        assert data["can_recommend"] is True
        assert data["execution_enabled"] is False

    def test_technical_details_not_required(self, client, auth_headers):
        _seed_data(client, auth_headers)
        r = client.get("/api/guided/summary", headers=auth_headers)
        data = r.json()
        assert "INSUFFICIENT_EVIDENCE" not in data["headline"]
        assert "gate_state" not in data["headline"]
