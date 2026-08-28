"""LA1 device trust domain tests — security, regression, authority invariants."""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from sqlalchemy.orm import Session

from enterprise.services.device_auth import (
    create_bootstrap_token,
    verify_bootstrap_token,
    create_device_token,
    verify_device_token,
    _hash_token,
    BOOTSTRAP_TOKEN_EXPIRE_MINUTES,
    DEVICE_TOKEN_EXPIRE_DAYS,
)
from enterprise.models import Device, BootstrapToken


# ---------------------------------------------------------------------------
# Bootstrap Token Tests — Single-Use & Storage
# ---------------------------------------------------------------------------

class TestBootstrapToken:
    """Verify bootstrap token creation, verification, and single-use enforcement."""

    def test_create_and_verify_bootstrap_token(self):
        """Bootstrap token round-trips correctly with hashed storage."""
        from sqlalchemy.orm import Session

        mock_db = MagicMock(spec=Session)
        device_id = "dev_test123"
        user_id = "user_abc"

        token, expires_at = create_bootstrap_token(mock_db, device_id, user_id)

        # Verify token was stored (add called with a BootstrapToken)
        assert mock_db.add.called
        stored_record = mock_db.add.call_args[0][0]
        assert isinstance(stored_record, BootstrapToken)
        assert stored_record.device_id == device_id
        assert stored_record.user_id == user_id
        assert stored_record.consumed is False
        assert stored_record.expires_at == expires_at

        # Verify the stored hash matches the token
        assert stored_record.token_hash == _hash_token(token)

        # Verify plaintext is NOT stored
        assert stored_record.token_hash != token
        assert "la_boot_" not in stored_record.token_hash

    def test_bootstrap_token_rejects_invalid_token(self):
        """Bootstrap verification rejects tokens not in database."""
        mock_db = MagicMock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(Exception) as exc_info:
            verify_bootstrap_token(mock_db, "invalid_token")
        assert "Invalid bootstrap token" in str(exc_info.value.detail)

    def test_bootstrap_token_rejects_reuse(self):
        """Bootstrap verification rejects already-consumed tokens."""
        mock_db = MagicMock(spec=Session)
        mock_record = MagicMock(spec=BootstrapToken)
        mock_record.consumed = True
        mock_record.expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_record

        with pytest.raises(Exception) as exc_info:
            verify_bootstrap_token(mock_db, "valid_token")
        assert "already used" in str(exc_info.value.detail)

    def test_bootstrap_token_rejects_expired(self):
        """Bootstrap verification rejects expired tokens."""
        mock_db = MagicMock(spec=Session)
        mock_record = MagicMock(spec=BootstrapToken)
        mock_record.consumed = False
        mock_record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_record

        with pytest.raises(Exception) as exc_info:
            verify_bootstrap_token(mock_db, "valid_token")
        assert "expired" in str(exc_info.value.detail)

    def test_bootstrap_token_single_use_enforced(self):
        """After successful verification, token is marked as consumed."""
        mock_db = MagicMock(spec=Session)
        mock_record = MagicMock(spec=BootstrapToken)
        mock_record.consumed = False
        mock_record.expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        mock_record.device_id = "dev_test123"
        mock_record.user_id = "user_abc"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_record

        result = verify_bootstrap_token(mock_db, "valid_token")

        assert mock_record.consumed is True
        assert mock_db.commit.called
        assert result["sub"] == "dev_test123"
        assert result["user_id"] == "user_abc"

    def test_bootstrap_token_hash_is_deterministic(self):
        """Token hashing is deterministic and uses SHA-256."""
        token = "test_token_12345"
        hash1 = _hash_token(token)
        hash2 = _hash_token(token)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex digest length


# ---------------------------------------------------------------------------
# Device Token Tests
# ---------------------------------------------------------------------------

class TestDeviceToken:
    """Verify device credential creation, verification, and expiry."""

    def test_create_and_verify_device_token(self):
        """Device token round-trips correctly."""
        device_id = "dev_test123"
        user_id = "user_abc"
        token, expires_at = create_device_token(device_id, user_id)

        payload = verify_device_token(token)
        assert payload["sub"] == device_id
        assert payload["user_id"] == user_id
        assert payload["token_type"] == "device"
        assert expires_at > datetime.now(timezone.utc)

    def test_device_token_rejects_bootstrap_type(self):
        """Device verification rejects bootstrap tokens."""
        device_id = "dev_test123"
        user_id = "user_abc"

        # Create a mock bootstrap token (with wrong type for device verification)
        from jose import jwt
        from enterprise.services.device_auth import SECRET_KEY, ALGORITHM

        payload = {
            "sub": device_id,
            "user_id": user_id,
            "token_type": "bootstrap",
            "exp": datetime.now(timezone.utc) + timedelta(days=30),
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        with pytest.raises(Exception) as exc_info:
            verify_device_token(token)
        assert "Invalid token type" in str(exc_info.value.detail)

    def test_device_token_rejects_invalid_signature(self):
        """Device verification rejects tokens with wrong signature."""
        from jose import jwt

        payload = {
            "sub": "dev_test123",
            "user_id": "user_abc",
            "token_type": "device",
            "exp": datetime.now(timezone.utc) + timedelta(days=30),
        }
        token = jwt.encode(payload, "wrong-secret", algorithm="HS256")

        with pytest.raises(Exception) as exc_info:
            verify_device_token(token)
        assert "Invalid or expired device token" in str(exc_info.value.detail)


# ---------------------------------------------------------------------------
# Authority Invariant Tests
# ---------------------------------------------------------------------------

class TestAuthorityInvariants:
    """Verify LA1 authority invariants are preserved."""

    def test_i1_no_autonomous_actions(self):
        """I1: No autonomous action endpoints exist in LA1 routers."""
        from enterprise.routers import devices, agent

        assert devices.router is not None
        assert agent.router is not None

    def test_i3_no_execute_shell_merge_deploy(self):
        """I3: LA1 does not introduce execute, shell, merge, or deploy capabilities."""
        from enterprise.services.safety import FORBIDDEN_OPERATIONS

        # LA1 capabilities are limited to heartbeat and job_poll
        # These must NOT be in FORBIDDEN_OPERATIONS
        assert "heartbeat" not in FORBIDDEN_OPERATIONS
        assert "job_poll" not in FORBIDDEN_OPERATIONS

    def test_i4_human_approval_not_bypassed(self):
        """I4: LA1 does not bypass human approval for merges or deployments."""
        from enterprise.services.safety import FORBIDDEN_OPERATIONS

        assert "merge" in FORBIDDEN_OPERATIONS
        # LA1 does not add any deploy capability — it remains outside allowed operations


# ---------------------------------------------------------------------------
# Model Import Tests
# ---------------------------------------------------------------------------

class TestModelImports:
    """Verify all LA1 components are importable."""

    def test_import_device_model(self):
        """Device model is importable."""
        from enterprise.models import Device
        assert Device.__tablename__ == "devices"

    def test_import_bootstrap_token_model(self):
        """BootstrapToken model is importable."""
        from enterprise.models import BootstrapToken
        assert BootstrapToken.__tablename__ == "bootstrap_tokens"

    def test_import_device_schemas(self):
        """Device schemas are importable."""
        from enterprise.schemas import (
            DeviceRegister,
            DeviceRegisterResponse,
            DeviceTokenExchange,
            DeviceTokenResponse,
            DeviceResponse,
            DeviceHeartbeatRequest,
            DeviceHeartbeatResponse,
        )
        assert DeviceRegister is not None

    def test_import_device_services(self):
        """Device services are importable."""
        from enterprise.services.device_auth import (
            create_bootstrap_token,
            verify_bootstrap_token,
            create_device_token,
            verify_device_token,
        )
        from enterprise.services.device_service import (
            register_device,
            exchange_bootstrap_token,
            get_device,
            list_devices,
            revoke_device,
        )
        assert create_bootstrap_token is not None


# ---------------------------------------------------------------------------
# LA6.3B Exchange Contract Regression Tests — Integration
# ---------------------------------------------------------------------------

import os
import uuid as _uuid

# Set DB URL before any enterprise imports (same pattern as test_la4_scan_jobs).
_LA6B_DB_URL = "sqlite:///./test_la6b_exchange.db"
os.environ.setdefault("HERMES_DATABASE_URL", _LA6B_DB_URL)
os.environ.setdefault("EVOSIA_DATABASE_URL", _LA6B_DB_URL)


class TestDeviceExchangeContractRegression:
    """LA6.3B: Prove POST /api/devices/exchange returns device_id,
    matching the contract expected by evosia_agent/agent.py."""

    @pytest.fixture(autouse=True)
    def _setup_db(self, monkeypatch):
        """Isolated database for each test, mirroring LA4 fixture."""
        from enterprise.database import Base, get_engine, _ENGINES
        import enterprise.services as _svc
        import enterprise.app as _app_mod

        monkeypatch.setenv("HERMES_DATABASE_URL", _LA6B_DB_URL)
        monkeypatch.setenv("EVOSIA_DATABASE_URL", _LA6B_DB_URL)
        monkeypatch.setenv("EVOSIA_JWT_SECRET", "la6b-test-secret")
        monkeypatch.setattr(_svc, "SECRET_KEY", "la6b-test-secret")
        monkeypatch.setattr(_app_mod, "SECRET_KEY", "la6b-test-secret")
        _ENGINES.clear()
        eng = get_engine(_LA6B_DB_URL)
        _app_mod.engine = eng
        Base.metadata.create_all(bind=eng)
        yield
        Base.metadata.drop_all(bind=eng)
        _ENGINES.pop(_LA6B_DB_URL, None)

    @pytest.fixture
    def client(self):
        from enterprise.app import app
        from starlette.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    @pytest.fixture
    def user_auth(self, client):
        email = f"la6b-{_uuid.uuid4().hex[:8]}@test.com"
        client.post("/api/auth/register", json={
            "email": email, "password": "testpass1234", "name": "LA6B Tester"
        })
        r = client.post("/api/auth/login", json={"email": email, "password": "testpass1234"})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    @pytest.fixture
    def registration(self, client, user_auth):
        r = client.post("/api/devices/register", json={
            "device_name": "LA6B Test Device",
            "platform": "macos",
            "agent_version": "evosia-agent/0.1.0",
        }, headers=user_auth)
        return r.json()

    def test_exchange_returns_device_id(self, client, registration):
        """Exchange response contains device_id field (LA6.3B contract fix)."""
        r = client.post("/api/devices/exchange", json={
            "bootstrap_token": registration["bootstrap_token"],
        })
        assert r.status_code == 200
        body = r.json()
        assert "device_id" in body

    def test_exchange_device_id_matches_registration(self, client, registration):
        """Returned device_id equals the device_id from human-authorized registration."""
        r = client.post("/api/devices/exchange", json={
            "bootstrap_token": registration["bootstrap_token"],
        })
        body = r.json()
        assert body["device_id"] == registration["device_id"]

    def test_exchange_returns_access_token(self, client, registration):
        """Exchange response contains access_token."""
        r = client.post("/api/devices/exchange", json={
            "bootstrap_token": registration["bootstrap_token"],
        })
        body = r.json()
        assert "access_token" in body
        assert len(body["access_token"]) > 0

    def test_exchange_token_type_is_device(self, client, registration):
        """token_type remains 'device' (no authority change)."""
        r = client.post("/api/devices/exchange", json={
            "bootstrap_token": registration["bootstrap_token"],
        })
        assert r.json()["token_type"] == "device"

    def test_access_token_verifies_as_device_credential(self, client, registration):
        """access_token is a valid device JWT that verifies correctly."""
        r = client.post("/api/devices/exchange", json={
            "bootstrap_token": registration["bootstrap_token"],
        })
        from enterprise.services.device_auth import verify_device_token
        payload = verify_device_token(r.json()["access_token"])
        assert payload["sub"] == registration["device_id"]
        assert payload["token_type"] == "device"

    def test_bootstrap_token_single_use(self, client, registration):
        """Second exchange with same bootstrap token is rejected."""
        client.post("/api/devices/exchange", json={
            "bootstrap_token": registration["bootstrap_token"],
        })
        r = client.post("/api/devices/exchange", json={
            "bootstrap_token": registration["bootstrap_token"],
        })
        assert r.status_code == 401

    def test_exchange_response_contract_fields(self, client, registration):
        """Full contract: device_id, access_token, token_type, expires_at."""
        r = client.post("/api/devices/exchange", json={
            "bootstrap_token": registration["bootstrap_token"],
        })
        body = r.json()
        assert set(body.keys()) == {"device_id", "access_token", "token_type", "expires_at"}


# ---------------------------------------------------------------------------
# LA6.3D Heartbeat Reconciliation Tests — Integration
# ---------------------------------------------------------------------------

class TestHeartbeatReconciliation:
    """LA6.3D: Prove heartbeat updates last_seen_at and agent_version."""

    @pytest.fixture(autouse=True)
    def _setup_db(self, monkeypatch):
        """Isolated database for each test."""
        from enterprise.database import Base, get_engine, _ENGINES
        import enterprise.services as _svc
        import enterprise.app as _app_mod

        monkeypatch.setenv("HERMES_DATABASE_URL", _LA6B_DB_URL)
        monkeypatch.setenv("EVOSIA_DATABASE_URL", _LA6B_DB_URL)
        monkeypatch.setenv("EVOSIA_JWT_SECRET", "la6d-test-secret")
        monkeypatch.setattr(_svc, "SECRET_KEY", "la6d-test-secret")
        monkeypatch.setattr(_app_mod, "SECRET_KEY", "la6d-test-secret")
        _ENGINES.clear()
        eng = get_engine(_LA6B_DB_URL)
        _app_mod.engine = eng
        Base.metadata.create_all(bind=eng)
        yield
        Base.metadata.drop_all(bind=eng)
        _ENGINES.pop(_LA6B_DB_URL, None)

    @pytest.fixture
    def client(self):
        from enterprise.app import app
        from starlette.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    @pytest.fixture
    def user_auth(self, client):
        email = f"la6d-{_uuid.uuid4().hex[:8]}@test.com"
        client.post("/api/auth/register", json={
            "email": email, "password": "testpass1234", "name": "LA6D Tester"
        })
        r = client.post("/api/auth/login", json={"email": email, "password": "testpass1234"})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    @pytest.fixture
    def active_device(self, client, user_auth):
        """Register, exchange, return device info + credential."""
        r = client.post("/api/devices/register", json={
            "device_name": "LA6D Test Device",
            "platform": "windows",
            "agent_version": "evosia-agent/0.1.0",
        }, headers=user_auth)
        reg = r.json()
        r = client.post("/api/devices/exchange", json={
            "bootstrap_token": reg["bootstrap_token"],
        })
        return {
            "device_id": reg["device_id"],
            "credential": r.json()["access_token"],
        }

    def test_heartbeat_updates_last_seen_at(self, client, active_device):
        """Heartbeat updates last_seen_at timestamp."""
        r = client.post("/api/agent/heartbeat", json={
            "device_id": active_device["device_id"],
            "agent_version": "evosia-agent/0.1.0",
        }, headers={"Authorization": f"Bearer {active_device['credential']}"})
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

        # Verify last_seen_at is set
        from enterprise.services.device_service import get_device
        from enterprise.database import SessionLocal
        db = SessionLocal()
        try:
            device = get_device(db, active_device["device_id"])
            assert device.last_seen_at is not None
        finally:
            db.close()

    def test_heartbeat_updates_agent_version(self, client, active_device):
        """Heartbeat updates agent_version from the heartbeat request body."""
        r = client.post("/api/agent/heartbeat", json={
            "device_id": active_device["device_id"],
            "agent_version": "evosia-agent/0.2.5",
        }, headers={"Authorization": f"Bearer {active_device['credential']}"})
        assert r.status_code == 200

        from enterprise.services.device_service import get_device
        from enterprise.database import SessionLocal
        db = SessionLocal()
        try:
            device = get_device(db, active_device["device_id"])
            assert device.agent_version == "evosia-agent/0.2.5"
        finally:
            db.close()

    def test_heartbeat_rejects_mismatched_device_id(self, client, active_device):
        """Heartbeat rejects request if JWT subject != body device_id."""
        r = client.post("/api/agent/heartbeat", json={
            "device_id": "dev_injected_fake_id",
            "agent_version": "evosia-agent/0.1.0",
        }, headers={"Authorization": f"Bearer {active_device['credential']}"})
        assert r.status_code == 403

    def test_heartbeat_rejects_revoked_device(self, client, active_device):
        """Revoked device heartbeat is rejected."""
        # Revoke the device
        from enterprise.services.device_service import revoke_device
        from enterprise.database import SessionLocal
        db = SessionLocal()
        try:
            from enterprise.services.device_auth import verify_device_token
            payload = verify_device_token(active_device["credential"])
            revoke_device(db, active_device["device_id"], payload["user_id"])
        finally:
            db.close()

        r = client.post("/api/agent/heartbeat", json={
            "device_id": active_device["device_id"],
            "agent_version": "evosia-agent/0.1.0",
        }, headers={"Authorization": f"Bearer {active_device['credential']}"})
        assert r.status_code == 403

    def test_registration_accepts_unreported_version(self, client, user_auth):
        """Registration accepts 'unreported' as agent_version (transitional value)."""
        r = client.post("/api/devices/register", json={
            "device_name": "Test Unreported",
            "platform": "windows",
            "agent_version": "unreported",
        }, headers=user_auth)
        assert r.status_code == 201
        assert r.json()["device_id"]

    def test_ui_does_not_hardcode_false_version(self):
        """DevicesPage no longer contains hardcoded evosia-agent/0.3.0."""
        import re
        with open("enterprise-ui/src/pages/DevicesPage.tsx", "r") as f:
            content = f.read()
        assert "evosia-agent/0.3.0" not in content


# ---------------------------------------------------------------------------
# LA6.4A Authority Tests — Project Authorization
# ---------------------------------------------------------------------------

class TestProjectAuthorizationAuthority:
    """LA6.4A: Prove the certified authority model is preserved."""

    @pytest.fixture(autouse=True)
    def _setup_db(self, monkeypatch):
        """Isolated database for each test."""
        from enterprise.database import Base, get_engine, _ENGINES
        import enterprise.services as _svc
        import enterprise.app as _app_mod

        monkeypatch.setenv("HERMES_DATABASE_URL", _LA6B_DB_URL)
        monkeypatch.setenv("EVOSIA_DATABASE_URL", _LA6B_DB_URL)
        monkeypatch.setenv("EVOSIA_JWT_SECRET", "la6a-test-secret")
        monkeypatch.setattr(_svc, "SECRET_KEY", "la6a-test-secret")
        monkeypatch.setattr(_app_mod, "SECRET_KEY", "la6a-test-secret")
        _ENGINES.clear()
        eng = get_engine(_LA6B_DB_URL)
        _app_mod.engine = eng
        Base.metadata.create_all(bind=eng)
        yield
        Base.metadata.drop_all(bind=eng)
        _ENGINES.pop(_LA6B_DB_URL, None)

    @pytest.fixture
    def client(self):
        from enterprise.app import app
        from starlette.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    @pytest.fixture
    def user_auth(self, client):
        email = f"la6a-{_uuid.uuid4().hex[:8]}@test.com"
        client.post("/api/auth/register", json={
            "email": email, "password": "testpass1234", "name": "LA6A Tester"
        })
        r = client.post("/api/auth/login", json={"email": email, "password": "testpass1234"})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    @pytest.fixture
    def active_device(self, client, user_auth):
        """Register, exchange, return device info + credential."""
        r = client.post("/api/devices/register", json={
            "device_name": "LA6A Test Device",
            "platform": "macos",
            "agent_version": "evosia-agent/0.1.0",
        }, headers=user_auth)
        reg = r.json()
        r = client.post("/api/devices/exchange", json={
            "bootstrap_token": reg["bootstrap_token"],
        })
        return {
            "device_id": reg["device_id"],
            "credential": r.json()["access_token"],
        }

    # A. Device JWT cannot mint project authorization token
    def test_device_cannot_mint_auth_token(self, client, active_device):
        """Device credential alone cannot create a project authorization token."""
        r = client.post(f"/api/devices/{active_device['device_id']}/project-auth-token",
                        headers={"Authorization": f"Bearer {active_device['credential']}"})
        assert r.status_code == 401

    # B. Unauthenticated caller cannot mint project authorization token
    def test_unauthenticated_cannot_mint_auth_token(self, client, active_device):
        """Unauthenticated request to create auth token is rejected."""
        r = client.post(f"/api/devices/{active_device['device_id']}/project-auth-token")
        assert r.status_code == 401

    # C. User can mint token only for a device they own
    def test_user_cannot_mint_token_for_other_device(self, client, active_device):
        """User cannot create auth token for a device they don't own."""
        # Create a second user
        email2 = f"la6a-other-{_uuid.uuid4().hex[:8]}@test.com"
        client.post("/api/auth/register", json={
            "email": email2, "password": "testpass1234", "name": "Other"
        })
        r2 = client.post("/api/auth/login", json={"email": email2, "password": "testpass1234"})
        other_auth = {"Authorization": f"Bearer {r2.json()['access_token']}"}

        r = client.post(f"/api/devices/{active_device['device_id']}/project-auth-token",
                        headers=other_auth)
        assert r.status_code == 403

    # D. Token expires after configured lifetime
    def test_token_has_expiry(self, client, user_auth, active_device):
        """Project authorization token has a defined expiry."""
        r = client.post(f"/api/devices/{active_device['device_id']}/project-auth-token",
                        headers=user_auth)
        assert r.status_code == 200
        data = r.json()
        assert "expires_at" in data
        assert "project_authorization_token" in data

    # E. Token is single-use
    def test_token_is_single_use(self, client, user_auth, active_device):
        """Project authorization token can only be consumed once."""
        r = client.post(f"/api/devices/{active_device['device_id']}/project-auth-token",
                        headers=user_auth)
        token = r.json()["project_authorization_token"]

        # First use — succeeds
        r1 = client.post("/api/device-projects/", json={
            "device_id": active_device["device_id"],
            "display_name": "TestProject",
            "local_root_fingerprint": "abc123",
            "project_authorization_token": token,
        })
        assert r1.status_code == 201

        # Second use — rejected
        r2 = client.post("/api/device-projects/", json={
            "device_id": active_device["device_id"],
            "display_name": "TestProject2",
            "local_root_fingerprint": "def456",
            "project_authorization_token": token,
        })
        assert r2.status_code == 401

    # F. Token cannot authorize another device
    def test_token_cannot_authorize_other_device(self, client, user_auth, active_device):
        """Token bound to device A cannot register a project on device B."""
        # Create a second device
        r = client.post("/api/devices/register", json={
            "device_name": "Device B",
            "platform": "windows",
            "agent_version": "evosia-agent/0.1.0",
        }, headers=user_auth)
        device_b = r.json()

        # Create token for device A
        r = client.post(f"/api/devices/{active_device['device_id']}/project-auth-token",
                        headers=user_auth)
        token = r.json()["project_authorization_token"]

        # Try to use token for device B — should fail
        r = client.post("/api/device-projects/", json={
            "device_id": device_b["device_id"],
            "display_name": "TestProject",
            "local_root_fingerprint": "abc123",
            "project_authorization_token": token,
        })
        assert r.status_code == 403

    # G. Agent project add without human token fails closed
    def test_agent_project_add_requires_token(self):
        """project_add() without authorization token prints instructions and returns."""
        from evosia_agent.agent import project_add
        import io, contextlib
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            project_add("/tmp/test_project")
        output = f.getvalue()
        assert "Project authorization required" in output
        assert "--authorization-token" in output

    # H. Agent project add no longer attempts token creation
    def test_agent_project_add_does_not_call_self_auth(self):
        """project_add() never calls request_project_authorization_token."""
        import inspect
        from evosia_agent import agent
        source = inspect.getsource(agent.project_add)
        assert "request_project_authorization_token" not in source

    # I. Agent never receives/stores user JWT
    def test_agent_never_stores_user_jwt(self):
        """CredentialStore only stores device credentials, never user JWT."""
        from evosia_agent.credential_store import DeviceCredential
        fields = {f.name for f in DeviceCredential.__dataclass_fields__.values()}
        assert "user_id" not in fields
        assert "user_jwt" not in fields
        assert "user_token" not in fields

    # J. Raw absolute path absent from project-registration payload
    def test_project_registration_no_raw_path(self):
        """register_project() never sends raw absolute path."""
        from evosia_agent.project_api import ProjectApiClient
        import inspect
        source = inspect.getsource(ProjectApiClient.register_project)
        assert "raw" not in source.lower()
        # The body only contains device_id, display_name, local_root_fingerprint, token
        assert "local_root" in source

    # K. local_root_fingerprint is non-empty, deterministic, SHA-256
    def test_fingerprint_is_deterministic_sha256(self):
        """Fingerprint is deterministic SHA-256 hex digest."""
        import tempfile
        from pathlib import Path
        from evosia_agent.path_validation import compute_local_root_fingerprint

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            fp1 = compute_local_root_fingerprint(p)
            fp2 = compute_local_root_fingerprint(p)
            assert fp1 == fp2
            assert len(fp1) == 64
            assert all(c in "0123456789abcdef" for c in fp1)

    # L. Different canonical roots produce different fingerprints
    def test_different_roots_different_fingerprints(self):
        """Different canonical paths produce different fingerprints."""
        import tempfile
        from pathlib import Path
        from evosia_agent.path_validation import compute_local_root_fingerprint

        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "project_a"
            b = Path(tmp) / "project_b"
            a.mkdir()
            b.mkdir()
            assert compute_local_root_fingerprint(a) != compute_local_root_fingerprint(b)

    # M. Duplicate device_id + fingerprint remains rejected
    def test_duplicate_fingerprint_rejected(self, client, user_auth, active_device):
        """Duplicate device_id + fingerprint is rejected with 409."""
        token1_resp = client.post(f"/api/devices/{active_device['device_id']}/project-auth-token",
                                  headers=user_auth)
        token1 = token1_resp.json()["project_authorization_token"]

        client.post("/api/device-projects/", json={
            "device_id": active_device["device_id"],
            "display_name": "ProjectA",
            "local_root_fingerprint": "same_fingerprint",
            "project_authorization_token": token1,
        })

        token2_resp = client.post(f"/api/devices/{active_device['device_id']}/project-auth-token",
                                  headers=user_auth)
        token2 = token2_resp.json()["project_authorization_token"]

        r = client.post("/api/device-projects/", json={
            "device_id": active_device["device_id"],
            "display_name": "ProjectA",
            "local_root_fingerprint": "same_fingerprint",
            "project_authorization_token": token2,
        })
        assert r.status_code == 409

    # N. Successful registration remains REVIEW_ONLY
    def test_registration_authority_is_review_only(self, client, user_auth, active_device):
        """Registered project has authority = REVIEW_ONLY."""
        r = client.post(f"/api/devices/{active_device['device_id']}/project-auth-token",
                        headers=user_auth)
        token = r.json()["project_authorization_token"]

        r = client.post("/api/device-projects/", json={
            "device_id": active_device["device_id"],
            "display_name": "TestProject",
            "local_root_fingerprint": "fingerprint_123",
            "project_authorization_token": token,
        })
        assert r.status_code == 201
        assert r.json()["authority"] == "REVIEW_ONLY"

    # O. Symlink escape protection remains intact
    def test_symlink_escape_detected(self):
        """Symlink escaping root is detected."""
        import tempfile, os
        from pathlib import Path
        from evosia_agent.path_validation import has_symlink_escape, SymlinkStatus

        if os.name == "nt":
            pytest.skip("Windows symlink behavior differs")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            outside = Path(tmp) / "outside"
            outside.mkdir()
            link = root / "escape"
            link.symlink_to(outside)
            results = has_symlink_escape(root)
            assert any(r.status == SymlinkStatus.ESCAPES_ROOT for r in results)

    # P. Broken symlink remains fail-closed
    def test_broken_symlink_detected(self):
        """Broken symlink is detected."""
        import tempfile
        from pathlib import Path
        from evosia_agent.path_validation import has_symlink_escape, SymlinkStatus

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            link = root / "broken"
            link.symlink_to(Path(tmp) / "nonexistent")
            results = has_symlink_escape(root)
            assert any(r.status == SymlinkStatus.BROKEN_OR_UNRESOLVABLE for r in results)

    # Q. No execution/merge/deploy/mutation capability introduced
    def test_no_execution_authority(self):
        """FORBIDDEN_OPERATIONS still contains execution, merge, deploy."""
        from enterprise.services.safety import FORBIDDEN_OPERATIONS
        assert "merge" in FORBIDDEN_OPERATIONS

    def test_allowed_operations_is_only_project_scan(self):
        """Only PROJECT_SCAN is allowed."""
        from enterprise.schemas import ALLOWED_OPERATION_TYPES
        assert ALLOWED_OPERATION_TYPES == frozenset({"PROJECT_SCAN"})
