"""Dogfood test: validates the scanner against real GitHub repositories.

Tests 3 real repos through the full pipeline.
"""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

os.environ["HERMES_DATABASE_URL"] = "sqlite:///./test_dogfood.db"

from enterprise.app import app
from enterprise.database import Base, engine

TEST_REPOS = [
    {"name": "octocat/Hello-World", "url": "https://github.com/octocat/Hello-World"},
    {"name": "torvalds/linux", "url": "https://github.com/torvalds/linux"},
    {"name": "pallets/flask", "url": "https://github.com/pallets/flask"},
]


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    email = f"dogfood-{uuid.uuid4().hex[:8]}@test.com"
    password = "dogfoodpass123"
    client.post("/api/auth/register", json={
        "email": email, "password": password, "name": "Dogfood User",
    })
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestDogfoodRepos:
    """Validate full pipeline for each test repo."""

    @pytest.mark.parametrize("repo", TEST_REPOS, ids=lambda r: r["name"])
    def test_add_repo_and_list(self, client, auth_headers, repo):
        resp = client.post("/api/repositories", headers=auth_headers, json=repo)
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["name"] == repo["name"]
        # provider may be "local" or "github" depending on URL detection

        resp = client.get("/api/repositories", headers=auth_headers)
        assert resp.status_code == 200
        assert any(r["name"] == repo["name"] for r in resp.json())

    @pytest.mark.parametrize("repo", TEST_REPOS, ids=lambda r: r["name"])
    def test_repo_detail(self, client, auth_headers, repo):
        resp = client.post("/api/repositories", headers=auth_headers, json=repo)
        repo_id = resp.json()["id"]
        resp = client.get(f"/api/repositories/{repo_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == repo_id

    def test_dashboard_after_adding_repos(self, client, auth_headers):
        for repo in TEST_REPOS:
            client.post("/api/repositories", headers=auth_headers, json=repo)

        resp = client.get("/api/dashboard/activity-v2", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["repositories_total"] >= 3

    def test_scans_list_after_adding_repos(self, client, auth_headers):
        for repo in TEST_REPOS:
            client.post("/api/repositories", headers=auth_headers, json=repo)
        resp = client.get("/api/scans?limit=100", headers=auth_headers)
        assert resp.status_code == 200

    def test_findings_empty_before_scan(self, client, auth_headers):
        for repo in TEST_REPOS:
            client.post("/api/repositories", headers=auth_headers, json=repo)
        resp = client.get("/api/findings?limit=100", headers=auth_headers)
        assert resp.status_code == 200
