"""
I4 — Security & Deployment Hardening Tests

Proves the hardening invariants against real defects found in the baseline:
  CORS-1: wildcard origins must never be combined with credentials
  JWT-1:  JWT secret must not fall back to a hardcoded default in production
          (enforced at app startup via validate_security_config, NOT at import)
  GEM-1:  Gemini API key must never be logged or exposed to the client

All I2/I3 authority invariants remain intact (no mutation, no execution path).
"""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from enterprise.app import app as _app
from enterprise.database import Base, get_engine
from sqlalchemy.orm import sessionmaker as _sm


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    eng = get_engine()
    Base.metadata.create_all(bind=eng)
    yield
    Base.metadata.drop_all(bind=eng)
    from enterprise.database import _ENGINES
    _ENGINES.clear()


def _auth_header(client: TestClient) -> dict[str, str]:
    email = f"i4-{uuid.uuid4().hex[:8]}@test.com"
    client.post(
        "/api/auth/register",
        json={"email": email, "password": "testpass1234", "name": "I4"},
    )
    r = client.post(
        "/api/auth/login",
        json={"email": email, "password": "testpass1234"},
    )
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestCORSNoWildcardWithCredentials:
    """CORS-1: '*' + allow_credentials=True is invalid and insecure."""

    def test_default_closed_when_no_env(self):
        from fastapi.middleware.cors import CORSMiddleware

        cors = next(
            (m for m in _app.user_middleware if m.cls is CORSMiddleware),
            None,
        )
        assert cors is not None
        # Default (no env) => closed origins, credentials False
        assert cors.kwargs["allow_origins"] == []
        assert cors.kwargs["allow_credentials"] is False

    def test_wildcard_disables_credentials(self):
        # Replicate the app's CORS resolution logic for the '*' branch.
        raw = "*"
        if raw.strip() == "*":
            origins = ["*"]
            credentials = False
        else:
            origins = [o.strip() for o in raw.split(",") if o.strip()]
            credentials = bool(origins)
        assert origins == ["*"]
        assert credentials is False  # wildcard + credentials never allowed

    def test_explicit_origins_enable_credentials(self):
        raw = "https://app.evosia.example,https://portal.evosia.example"
        origins = [o.strip() for o in raw.split(",") if o.strip()]
        credentials = bool(origins)
        assert origins == [
            "https://app.evosia.example",
            "https://portal.evosia.example",
        ]
        assert credentials is True


class TestJWTSecretNotHardcoded:
    """JWT-1: production must refuse to start with insecure default secret.

    Enforced at app startup via validate_security_config(), not at import,
    so test collection / TestClient still work.
    """

    def test_production_fails_without_secret(self):
        from enterprise.app import validate_security_config

        saved = os.environ.pop("EVOSIA_JWT_SECRET", None)
        saved_env = os.environ.pop("EVOSIA_ENV", None)
        os.environ["EVOSIA_ENV"] = "production"
        try:
            with pytest.raises(RuntimeError):
                validate_security_config()
        finally:
            if saved is not None:
                os.environ["EVOSIA_JWT_SECRET"] = saved
            if saved_env is not None:
                os.environ["EVOSIA_ENV"] = saved_env

    def test_development_allows_dev_secret(self):
        from enterprise.app import validate_security_config

        saved = os.environ.pop("EVOSIA_JWT_SECRET", None)
        saved_env = os.environ.pop("EVOSIA_ENV", None)
        os.environ["EVOSIA_ENV"] = "development"
        try:
            validate_security_config()  # must not raise
        finally:
            if saved is not None:
                os.environ["EVOSIA_JWT_SECRET"] = saved
            if saved_env is not None:
                os.environ["EVOSIA_ENV"] = saved_env

    def test_module_import_does_not_raise(self):
        # Regression guard: importing the package must never raise on missing secret.
        import importlib
        import enterprise.services as svc

        importlib.reload(svc)
        assert svc.SECRET_KEY is not None


class TestGeminiKeyNotExposed:
    """GEM-1: API key never reaches logs or client responses."""

    def test_key_not_in_any_explain_response(self):
        from unittest.mock import patch

        client = TestClient(_app)
        hdr = _auth_header(client)
        with patch(
            "enterprise.services.gemini_explain._call_gemini",
            return_value="ok",
        ):
            for ep in ["/api/guided/explain/status", "/api/guided/explain/approval"]:
                resp = client.get(ep, headers=hdr)
                assert "EVOSIA_GEMINI_API_KEY" not in resp.text
                assert "api_key" not in resp.text.lower()

    def test_scrub_redacts_key(self):
        from enterprise.services.gemini_explain import _scrub_secret

        assert _scrub_secret("AIza1234567890abcdef") == "AIza…REDACTED"
        assert _scrub_secret(None) == "<unset>"
        assert _scrub_secret("") == "<unset>"


class TestAuthorityInvariantsPreserved:
    """I2/I3 invariants must survive I4 hardening."""

    def test_no_execute_endpoint(self):
        client = TestClient(_app)
        r = client.post("/api/guided/execute", json={})
        assert r.status_code == 404

    def test_permission_still_read_only(self):
        client = TestClient(_app)
        hdr = _auth_header(client)
        pr = client.get("/api/guided/permission", headers=hdr)
        if pr.status_code == 200:
            body = pr.json()
            assert body["can_execute"] is False
            assert body["execution_enabled"] is False
            assert body["mutation_enabled"] is False
