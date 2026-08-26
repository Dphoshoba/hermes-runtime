"""C3 — Health and readiness endpoint tests.

Verifies:
- /api/health returns lightweight liveness (no DB check)
- /api/ready returns database connectivity status
- Neither endpoint leaks secrets or database URLs
- Readiness degrades gracefully when DB is unavailable
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from enterprise.app import app


@pytest.fixture(autouse=True)
def _setup_db():
    """Ensure a test database exists for the app."""
    os.environ.setdefault("EVOSIA_DATABASE_URL", "sqlite:///./test_health_check.db")
    os.environ.setdefault("EVOSIA_ENV", "development")
    yield


class TestHealthEndpoint:
    """Verify /api/health is a lightweight liveness probe."""

    def test_health_returns_200(self) -> None:
        client = TestClient(app)
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_health_returns_ok(self) -> None:
        client = TestClient(app)
        resp = client.get("/api/health")
        data = resp.json()
        assert data["status"] == "ok"

    def test_health_includes_version(self) -> None:
        client = TestClient(app)
        resp = client.get("/api/health")
        data = resp.json()
        assert "version" in data
        assert data["version"] == "1.3.0"

    def test_health_does_not_leak_secrets(self) -> None:
        client = TestClient(app)
        resp = client.get("/api/health")
        body = resp.text
        assert "secret" not in body.lower()
        assert "password" not in body.lower()
        assert "EVOSIA_" not in body


class TestReadinessEndpoint:
    """Verify /api/ready checks database connectivity."""

    def test_ready_returns_200_when_db_available(self) -> None:
        client = TestClient(app)
        resp = client.get("/api/ready")
        assert resp.status_code == 200

    def test_ready_returns_ok_status(self) -> None:
        client = TestClient(app)
        resp = client.get("/api/ready")
        data = resp.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"

    def test_ready_does_not_leak_secrets(self) -> None:
        client = TestClient(app)
        resp = client.get("/api/ready")
        body = resp.text
        assert "secret" not in body.lower()
        assert "password" not in body.lower()
        assert "EVOSIA_" not in body


class TestReadinessDegraded:
    """Verify /api/ready degrades gracefully when DB is unavailable."""

    def test_ready_returns_degraded_when_db_unavailable(self) -> None:
        """Point to a non-existent database to simulate failure."""
        original = os.environ.get("EVOSIA_DATABASE_URL")
        os.environ["EVOSIA_DATABASE_URL"] = "sqlite:///nonexistent/path/db.sqlite"
        try:
            # Need a fresh engine for the new URL
            from enterprise.database import _ENGINES
            _ENGINES.clear()

            client = TestClient(app)
            resp = client.get("/api/ready")
            # Should still return a response (not crash)
            assert resp.status_code in (200, 503)
            data = resp.json()
            assert data["status"] == "degraded"
            assert data["database"] == "unavailable"
        finally:
            if original is not None:
                os.environ["EVOSIA_DATABASE_URL"] = original
            else:
                os.environ.pop("EVOSIA_DATABASE_URL", None)
            _ENGINES.clear()


class TestVersionEndpoint:
    """Verify /api/version returns build provenance."""

    def test_version_returns_200(self) -> None:
        client = TestClient(app)
        resp = client.get("/api/version")
        assert resp.status_code == 200

    def test_version_includes_provenance(self) -> None:
        client = TestClient(app)
        resp = client.get("/api/version")
        data = resp.json()
        assert "version" in data
        assert "build_sha" in data
        assert "provenance" in data

    def test_version_does_not_leak_secrets(self) -> None:
        client = TestClient(app)
        resp = client.get("/api/version")
        body = resp.text
        assert "secret" not in body.lower()
        assert "password" not in body.lower()
        # Only check non-empty secret env vars (empty string matches everything)
        jwt_secret = os.environ.get("EVOSIA_JWT_SECRET", "")
        if jwt_secret:
            assert jwt_secret not in body
        db_url = os.environ.get("EVOSIA_DATABASE_URL", "")
        if db_url:
            assert db_url not in body
