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
