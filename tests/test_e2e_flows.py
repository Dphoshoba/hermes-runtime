"""End-to-end tests for the enterprise API (happy path + failure paths).

These tests exercise the full HTTP API flow using FastAPI TestClient.
They validate: auth, repositories, scanning, findings, scans cancel/retry.
"""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

# Use a fresh test database
_TEST_DB_URL = "sqlite:///./test_e2e.db"
os.environ["HERMES_DATABASE_URL"] = _TEST_DB_URL
os.environ["EVOSIA_DATABASE_URL"] = _TEST_DB_URL

from enterprise.app import app
from enterprise.database import Base, get_engine, _ENGINES


@pytest.fixture(autouse=True)
def setup_db():
    """Create fresh tables for each test on this suite's database engine."""
    _ENGINES.clear()
    eng = get_engine(_TEST_DB_URL)
    Base.metadata.create_all(bind=eng)
    yield
    Base.metadata.drop_all(bind=eng)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    """Register/login a test user and return auth headers."""
    email = f"e2e-{uuid.uuid4().hex[:8]}@test.com"
    password = "testpass1234"
    client.post("/api/auth/register", json={
        "email": email,
        "password": password,
        "name": "E2E Test User",
    })
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestAuthFlow:
    def test_register_and_login(self, client):
        email = f"auth-{uuid.uuid4().hex[:8]}@test.com"
        resp = client.post("/api/auth/register", json={
            "email": email, "password": "pass12345", "name": "Auth Test",
        })
        assert resp.status_code == 201

        resp = client.post("/api/auth/login", json={"email": email, "password": "pass12345"})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_wrong_password(self, client):
        email = f"fail-{uuid.uuid4().hex[:8]}@test.com"
        client.post("/api/auth/register", json={
            "email": email, "password": "correctpass", "name": "Fail Test",
        })
        resp = client.post("/api/auth/login", json={"email": email, "password": "wrongpass"})
        assert resp.status_code in (401, 400)

    def test_protected_route_without_token(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code in (401, 403)

    def test_me_endpoint(self, client, auth_headers):
        resp = client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "email" in data
        assert data["name"] == "E2E Test User"


class TestRepositoryFlow:
    def test_list_repositories_empty(self, client, auth_headers):
        resp = client.get("/api/repositories", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_add_and_list_repository(self, client, auth_headers):
        resp = client.post("/api/repositories", headers=auth_headers, json={
            "url": "https://github.com/octocat/Hello-World",
            "name": "octocat/Hello-World",
        })
        assert resp.status_code in (200, 201)
        repo = resp.json()

        resp = client.get("/api/repositories", headers=auth_headers)
        assert resp.status_code == 200
        repos = resp.json()
        assert any(r["id"] == repo["id"] for r in repos)

    def test_get_repository_detail(self, client, auth_headers):
        resp = client.post("/api/repositories", headers=auth_headers, json={
            "url": "https://github.com/octocat/Hello-World",
            "name": "octocat/Hello-World",
        })
        repo_id = resp.json()["id"]
        resp = client.get(f"/api/repositories/{repo_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "octocat/Hello-World"


class TestDashboardFlow:
    def test_dashboard_activity(self, client, auth_headers):
        resp = client.get("/api/dashboard/activity-v2", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "repositories_total" in data
        assert "scans_running" in data
        assert "latest_activity" in data

    def test_dashboard_overnight(self, client, auth_headers):
        resp = client.get("/api/dashboard/overnight", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "window_start" in data
        assert "summary" in data


class TestFindingsFlow:
    def test_list_findings_empty(self, client, auth_headers):
        resp = client.get("/api/findings?limit=100", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestScansFlow:
    def test_list_scans_empty(self, client, auth_headers):
        resp = client.get("/api/scans?limit=100", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_scan_nonexistent_repo_returns_error(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = client.post("/api/scans", headers=auth_headers, json={
            "repository_id": fake_id,
        })
        assert resp.status_code in (400, 404)


class TestScanCancellation:
    def test_cancel_nonexistent_scan(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = client.post(f"/api/scans/{fake_id}/cancel", headers=auth_headers)
        assert resp.status_code in (404, 400)

    def test_retry_nonexistent_scan(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = client.post(f"/api/scans/{fake_id}/retry", headers=auth_headers)
        assert resp.status_code in (404, 400)


class TestJournalFlow:
    def test_list_journal_events(self, client, auth_headers):
        resp = client.get("/api/journal?limit=50", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestMissionsFlow:
    def test_list_missions_empty(self, client, auth_headers):
        resp = client.get("/api/missions?limit=50", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
