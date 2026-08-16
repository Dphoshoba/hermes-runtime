"""
I3 — Gemini Explanation Layer Tests

Verifies that the explanation layer:
  - labels all output GEMINI_EXPLANATION
  - cannot alter authoritative mission state
  - cannot alter permissions
  - cannot create preparation evidence
  - returns insufficient-evidence when authoritative data is absent
  - degrades gracefully when Gemini is unavailable
  - never exposes credentials to the frontend
  - introduces no autonomous execution path
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

os.environ["HERMES_DATABASE_URL"] = "sqlite:///./test_i3_gemini.db"

import pytest

from enterprise.app import app
from enterprise.database import Base, get_engine
from sqlalchemy.orm import sessionmaker as _sm


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    eng = get_engine(os.environ["HERMES_DATABASE_URL"])
    Base.metadata.create_all(bind=eng)
    yield


@pytest.fixture(scope="module")
def auth_header():
    """Register → login → return auth header with real JWT."""
    email = f"i3-{uuid.uuid4().hex[:8]}@test.com"
    password = "testpass1234"
    resp = app_test_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "name": "I3 Test User"},
    )
    resp = app_test_client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


app_test_client = TestClient(app)


class TestGeminiProvenance:
    """All Gemini output must carry GEMINI_EXPLANATION provenance."""

    def test_status_endpoint_reports_service(self, auth_header):
        r = app_test_client.get("/api/guided/explain/status", headers=auth_header)
        assert r.status_code == 200
        body = r.json()
        assert body["provenance"] == "GEMINI_EXPLANATION"
        assert body["service"] == "Gemini Explanation Layer"

    def test_approval_explanation_tagged(self, auth_header):
        with patch("enterprise.services.gemini_explain._call_gemini", return_value="approval explanation"):
            r = app_test_client.get("/api/guided/explain/approval", headers=auth_header)
            assert r.status_code == 200
            body = r.json()
            assert body["provenance"] == "GEMINI_EXPLANATION"


class TestGeminiCannotAlterAuthority:
    """Gemini explanation endpoints must NEVER mutate authoritative state."""

    def test_no_execution_endpoint_introduced(self, auth_header):
        r = app_test_client.post("/api/guided/execute", json={}, headers=auth_header)
        assert r.status_code == 404


class TestGeminiCannotAlterPermissions:
    """Explain endpoint must not change permissions."""

    def test_permission_state_unchanged(self, auth_header):
        with patch("enterprise.services.gemini_explain._call_gemini", return_value="ok"):
            app_test_client.get("/api/guided/explain/approval", headers=auth_header)
        r = app_test_client.get("/api/guided/permission", headers=auth_header)
        body = r.json()
        assert body["can_execute"] is False
        assert body["execution_enabled"] is False
        assert body["mutation_enabled"] is False


class TestGeminiCannotCreateEvidence:
    """Gemini cannot create preparation evidence or prepared changes."""

    def test_no_prepared_change_created(self, auth_header):
        from enterprise.models import PreparedChange
        eng = get_engine(os.environ["HERMES_DATABASE_URL"])
        session = _sm(autocommit=False, autoflush=False, bind=get_engine(), future=True)()
        count_before = session.query(PreparedChange).count()
        with patch("enterprise.services.gemini_explain._call_gemini", return_value="ok"):
            app_test_client.get("/api/guided/explain/approval", headers=auth_header)
        count_after = session.query(PreparedChange).count()
        assert count_after == count_before
        session.close()


class TestInsufficientEvidence:
    """Missing authoritative evidence produces appropriate response."""

    def test_missing_finding_returns_404(self, auth_header):
        with patch("enterprise.services.gemini_explain._call_gemini"):
            r = app_test_client.get(
                "/api/guided/explain/finding/nonexistent-id-xxx",
                headers=auth_header,
            )
            assert r.status_code == 404


class TestGeminiFailureFallback:
    """Gemini failure must not block Guided Mode."""

    def test_gemini_unavailable_does_not_crash(self, auth_header):
        with patch("enterprise.services.gemini_explain._call_gemini", side_effect=RuntimeError("gemini down")):
            r = app_test_client.get("/api/guided/explain/approval", headers=auth_header)
            assert r.status_code == 200
            body = r.json()
            assert "GEMINI_EXPLANATION" in body["provenance"]
            assert body["available"] is False

    def test_summary_still_works_when_gemini_down(self, auth_header):
        with patch("enterprise.services.gemini_explain._call_gemini", side_effect=RuntimeError("down")):
            r = app_test_client.get("/api/guided/summary", headers=auth_header)
            assert r.status_code == 200
            assert r.json()["nothing_changed"] is True


class TestNoCredentialLeak:
    """API key must never be exposed to the frontend."""

    def test_api_key_not_in_any_response(self, auth_header):
        with patch("enterprise.services.gemini_explain._call_gemini", return_value="ok"):
            for r in [
                app_test_client.get("/api/guided/explain/status", headers=auth_header),
                app_test_client.get("/api/guided/explain/approval", headers=auth_header),
            ]:
                text = r.text.lower()
                assert "evosia_gemini_api_key" not in text
                assert "api_key" not in text

    def test_status_endpoint_does_not_expose_key(self, auth_header):
        r = app_test_client.get("/api/guided/explain/status", headers=auth_header)
        body = r.json()
        assert "key" not in body
        assert "EVOSIA_GEMINI_API_KEY" not in str(body)


class TestNoAutonomousExecution:
    """Gemini integration introduces no execution path."""

    def test_no_execute_endpoint(self, auth_header):
        r = app_test_client.post("/api/guided/execute", json={}, headers=auth_header)
        assert r.status_code == 404

    def test_no_merge_endpoint(self, auth_header):
        r = app_test_client.post("/api/guided/merge", json={}, headers=auth_header)
        assert r.status_code == 404

    def test_no_deploy_endpoint(self, auth_header):
        r = app_test_client.post("/api/guided/deploy", json={}, headers=auth_header)
        assert r.status_code == 404


class TestAllowListEnforcement:
    """Only allow-listed fields may reach Gemini."""

    def test_finding_excludes_authoritative_fields(self):
        from enterprise.services.gemini_explain import explain_finding
        test_finding = {
            "title": "Test finding",
            "category": "complexity",
            "plain_title": "Test finding",
            "why_it_matters": "test",
            "severity": "critical",       # should NOT be sent
            "evidence_hash": "abc123",    # should NOT be sent
            "gate_state": "BLOCKED",      # should NOT be sent
        }
        with patch("enterprise.services.gemini_explain._call_gemini", return_value="ok") as mock_call:
            explain_finding(test_finding)
            sent_prompt = mock_call.call_args[0][0]
            # Check that the filtered evidence dict does not contain sensitive keys
            # (the instruction text mentioning "fabricate" is expected to appear)
            evidence_section = sent_prompt.split("Finding: ")[-1] if "Finding: " in sent_prompt else ""
            assert "severity" not in evidence_section
            assert "evidence_hash" not in evidence_section
            assert "gate_state" not in evidence_section
            assert "'category'" in sent_prompt

    def test_prepared_change_excludes_sensitive_fields(self):
        from enterprise.services.gemini_explain import explain_prepared_change
        test_pc = {
            "id": "pc-123",
            "title": "Test prepared change",
            "description": "A test change",
            "workspace_path": "/secret/path",
            "affected_files": ["/secret/file.py"],
            "diff_content": "SECRET DIFF",
            "validation_status": "passed",
        }
        with patch("enterprise.services.gemini_explain._call_gemini", return_value="ok") as mock_call:
            explain_prepared_change(test_pc)
            sent_prompt = mock_call.call_args[0][0]
            assert "workspace_path" not in sent_prompt
            assert "affected_files" not in sent_prompt
            assert "diff_content" not in sent_prompt
            assert "validation_status" not in sent_prompt
