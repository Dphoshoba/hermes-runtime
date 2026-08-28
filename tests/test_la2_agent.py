"""LA2 Local Agent tests — security, functionality, authority boundaries."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from evosia_agent.api_client import ApiClient, ApiError
from evosia_agent.config import AgentConfig, HEARTBEAT_INTERVAL_SECONDS
from evosia_agent.credential_store import CredentialStore, DeviceCredential
from evosia_agent.device_identity import DeviceIdentity, _get_platform
from evosia_agent.heartbeat import HeartbeatLoop
from evosia_agent.version import __version__, AGENT_VERSION


# ---------------------------------------------------------------------------
# Device Identity Tests
# ---------------------------------------------------------------------------

class TestDeviceIdentity:
    """Verify safe metadata collection."""

    def test_collect_returns_identity(self):
        """DeviceIdentity.collect() returns valid identity."""
        identity = DeviceIdentity.collect()
        assert identity.device_name
        assert identity.platform in ("macos", "windows", "linux")
        assert identity.architecture
        assert identity.agent_version == AGENT_VERSION

    def test_platform_normalization(self):
        """Platform is normalized to macos/windows/linux."""
        platform = _get_platform()
        assert platform in ("macos", "windows", "linux")

    def test_register_payload(self):
        """Register payload contains required fields."""
        identity = DeviceIdentity.collect()
        payload = identity.to_register_payload()
        assert "device_name" in payload
        assert "platform" in payload
        assert "agent_version" in payload
        # Must NOT contain sensitive data
        assert "home" not in payload
        assert "username" not in payload

    def test_no_sensitive_data_collected(self):
        """Identity does not collect sensitive system information."""
        identity = DeviceIdentity.collect()
        # Verify no file paths, no user info
        assert "/" not in identity.device_name or identity.device_name.startswith("/")
        # device_name should be hostname, not a path


# ---------------------------------------------------------------------------
# Credential Store Tests
# ---------------------------------------------------------------------------

class TestCredentialStore:
    """Verify secure credential storage."""

    def test_save_and_load(self, tmp_path: Path):
        """Credential round-trips correctly."""
        store = CredentialStore(tmp_path)
        cred = DeviceCredential(
            device_id="dev_test123",
            device_name="Test Device",
            credential="test_jwt_token",
            cloud_url="https://test.example.com",
        )
        store.save(cred)
        loaded = store.load()
        assert loaded.device_id == "dev_test123"
        assert loaded.device_name == "Test Device"
        assert loaded.credential == "test_jwt_token"

    def test_is_registered(self, tmp_path: Path):
        """is_registered returns correct state."""
        store = CredentialStore(tmp_path)
        assert not store.is_registered
        cred = DeviceCredential(
            device_id="dev_test123",
            device_name="Test",
            credential="token",
            cloud_url="https://test.com",
        )
        store.save(cred)
        assert store.is_registered

    def test_delete(self, tmp_path: Path):
        """delete removes credential file."""
        store = CredentialStore(tmp_path)
        cred = DeviceCredential(
            device_id="dev_test123",
            device_name="Test",
            credential="token",
            cloud_url="https://test.com",
        )
        store.save(cred)
        store.delete()
        assert not store.is_registered

    def test_load_raises_on_missing(self, tmp_path: Path):
        """load() raises FileNotFoundError when not registered."""
        store = CredentialStore(tmp_path)
        with pytest.raises(FileNotFoundError):
            store.load()

    def test_credential_file_permissions(self, tmp_path: Path):
        """Credential file has restrictive permissions (Unix only)."""
        store = CredentialStore(tmp_path)
        cred = DeviceCredential(
            device_id="dev_test123",
            device_name="Test",
            credential="token",
            cloud_url="https://test.com",
        )
        store.save(cred)
        cred_file = tmp_path / "device.json"
        # Check permissions if on Unix
        try:
            import os
            mode = os.stat(cred_file).st_mode
            # Owner read/write only (0o600)
            assert (mode & 0o777) == 0o600
        except (OSError, AttributeError):
            # Windows or unsupported — skip
            pass

    def test_bootstrap_token_not_persisted(self, tmp_path: Path):
        """Bootstrap token is never written to credential store."""
        store = CredentialStore(tmp_path)
        cred = DeviceCredential(
            device_id="dev_test123",
            device_name="Test",
            credential="device_jwt_only",
            cloud_url="https://test.com",
        )
        store.save(cred)
        # Read file and verify no bootstrap token field
        cred_file = tmp_path / "device.json"
        data = json.loads(cred_file.read_text())
        assert "bootstrap_token" not in data
        assert "la_boot_" not in json.dumps(data)


# ---------------------------------------------------------------------------
# API Client Tests
# ---------------------------------------------------------------------------

class TestApiClient:
    """Verify narrow API client."""

    def test_client_instantiation(self):
        """ApiClient creates with cloud URL."""
        client = ApiClient("https://test.example.com")
        assert client._cloud_url == "https://test.example.com"

    def test_client_strips_trailing_slash(self):
        """ApiClient strips trailing slash from URL."""
        client = ApiClient("https://test.example.com/")
        assert client._cloud_url == "https://test.example.com"

    @patch("evosia_agent.api_client.urllib.request.urlopen")
    def test_exchange_success(self, mock_urlopen):
        """Successful bootstrap exchange returns response."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "device_id": "dev_abc",
            "access_token": "jwt_token",
        }).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = ApiClient("https://test.example.com")
        result = client.exchange_bootstrap_token("la_boot_test", "device_token")
        assert result["device_id"] == "dev_abc"

    @patch("evosia_agent.api_client.urllib.request.urlopen")
    def test_heartbeat_sends_device_token(self, mock_urlopen):
        """Heartbeat sends device token in Authorization header."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "status": "ok",
            "pending_jobs": [],
        }).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = ApiClient("https://test.example.com")
        result = client.send_heartbeat("dev_abc", "jwt_token", "evosia-agent/0.1.0")
        assert result["status"] == "ok"

        # Verify Authorization header was sent
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        assert request.get_header("Authorization") == "Bearer jwt_token"

    @patch("evosia_agent.api_client.urllib.request.urlopen")
    def test_tls_verification_enabled(self, mock_urlopen):
        """TLS verification is not disabled."""
        # The client uses default urllib which verifies TLS
        # Verify we don't pass context with ssl._create_unverified_context
        client = ApiClient("https://test.example.com")
        # If TLS verification were disabled, we'd see ssl._create_unverified_context
        # This is a structural test — the code doesn't import ssl module
        import evosia_agent.api_client as mod
        assert "ssl" not in dir(mod)


# ---------------------------------------------------------------------------
# Heartbeat Tests
# ---------------------------------------------------------------------------

class TestHeartbeat:
    """Verify heartbeat loop with retry/backoff."""

    def test_heartbeat_stops_on_revoked(self):
        """Heartbeat stops when device is revoked."""
        api = MagicMock(spec=ApiClient)
        api.send_heartbeat.return_value = {"status": "revoked"}

        revoked_event = threading.Event()

        loop = HeartbeatLoop(
            api_client=api,
            device_id="dev_abc",
            device_credential="jwt_token",
            agent_version="evosia-agent/0.1.0",
            interval_seconds=1,
            on_revoked=lambda: revoked_event.set(),
        )

        # Run heartbeat in thread
        thread = threading.Thread(target=loop.start)
        thread.start()
        revoked_event.wait(timeout=5)
        loop.stop()
        thread.join(timeout=5)

        assert revoked_event.is_set()

    def test_heartbeat_stops_on_expired(self):
        """Heartbeat stops when credential expires."""
        api = MagicMock(spec=ApiClient)
        api.send_heartbeat.side_effect = ApiError(status_code=401, detail="Unauthorized")

        expired_event = threading.Event()

        loop = HeartbeatLoop(
            api_client=api,
            device_id="dev_abc",
            device_credential="expired_jwt",
            agent_version="evosia-agent/0.1.0",
            interval_seconds=1,
            on_expired=lambda: expired_event.set(),
        )

        thread = threading.Thread(target=loop.start)
        thread.start()
        expired_event.wait(timeout=5)
        loop.stop()
        thread.join(timeout=5)

        assert expired_event.is_set()

    def test_heartbeat_retries_on_network_error(self):
        """Heartbeat retries with backoff on network error."""
        api = MagicMock(spec=ApiClient)
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ApiError(status_code=0, detail="Connection failed")
            return {"status": "ok"}

        api.send_heartbeat.side_effect = side_effect

        loop = HeartbeatLoop(
            api_client=api,
            device_id="dev_abc",
            device_credential="jwt_token",
            agent_version="evosia-agent/0.1.0",
            interval_seconds=1,
        )

        # Run briefly — need enough time for retries with backoff
        loop._running = True
        thread = threading.Thread(target=loop.start)
        thread.start()
        time.sleep(8)  # Allow time for retries with backoff
        loop.stop()
        thread.join(timeout=5)

        assert call_count >= 2


# ---------------------------------------------------------------------------
# Config Tests
# ---------------------------------------------------------------------------

class TestConfig:
    """Verify configuration."""

    def test_default_cloud_url(self):
        """Default cloud URL is set."""
        config = AgentConfig()
        assert config.cloud_url

    def test_env_override(self, monkeypatch):
        """EVOSIA_CLOUD_URL overrides default."""
        monkeypatch.setenv("EVOSIA_CLOUD_URL", "https://custom.example.com")
        config = AgentConfig()
        assert config.cloud_url == "https://custom.example.com"

    def test_endpoints(self):
        """Endpoints are constructed correctly."""
        config = AgentConfig(cloud_url="https://test.example.com")
        assert config.devices_endpoint == "https://test.example.com/api/devices/exchange"
        assert config.heartbeat_endpoint == "https://test.example.com/api/agent/heartbeat"

    def test_default_data_dir_resolves_to_platform_default(self):
        """AgentConfig with no explicit data_dir resolves to platform default."""
        config = AgentConfig()
        assert config.data_dir is not None
        assert isinstance(config.data_dir, Path)
        # Must NOT be Path(".") — the old broken default
        assert str(config.data_dir) != "."

    def test_explicit_data_dir_preserved(self):
        """AgentConfig with an explicitly supplied data_dir preserves that directory."""
        custom = Path("/tmp/custom_evosia_data")
        config = AgentConfig(data_dir=custom)
        assert config.data_dir == custom

    def test_windows_default_data_dir(self):
        """Windows default resolves to %LOCALAPPDATA%\\EVOSIA."""
        import platform as _platform
        if _platform.system() != "Windows":
            pytest.skip("Windows-only test")
        config = AgentConfig()
        local_app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        assert config.data_dir == Path(local_app_data) / "EVOSIA"

    def test_credential_store_targets_device_json(self):
        """CredentialStore under default config targets device.json."""
        config = AgentConfig()
        store = CredentialStore(config.data_dir)
        assert store._credential_path == config.data_dir / "device.json"


# ---------------------------------------------------------------------------
# Authority Boundary Tests
# ---------------------------------------------------------------------------

class TestAuthorityBoundaries:
    """Verify LA2 does not exceed its authority."""

    def test_no_project_access(self):
        """LA2/3 code contains no project/filesystem scanning.

        LA3 adds explicit project authorization (user selects ONE root).
        This is authorization logic only — not scanning/reading.
        """
        import evosia_agent.agent as agent_mod
        import evosia_agent.api_client as api_mod
        import evosia_agent.config as config_mod
        import evosia_agent.credential_store as store_mod
        import evosia_agent.device_identity as identity_mod
        import evosia_agent.heartbeat as heartbeat_mod

        modules = [agent_mod, api_mod, config_mod, store_mod, identity_mod, heartbeat_mod]

        # These patterns indicate actual filesystem scanning/reading
        # NOTE: "scanner" removed — LA4 legitimately imports scanner module for
        # governed read-only project scanning.
        forbidden_patterns = [
            "os.walk",
            "rglob",
            "repository",
            "file_list",
        ]

        for mod in modules:
            source = open(mod.__file__).read()
            for pattern in forbidden_patterns:
                assert pattern not in source, (
                    f"LA2 module {mod.__name__} contains forbidden pattern: {pattern}"
                )

    def test_no_execute_shell_merge_deploy(self):
        """LA2 has no execute/shell/merge/deploy capability."""
        import evosia_agent.agent as agent_mod
        import evosia_agent.api_client as api_mod

        modules = [agent_mod, api_mod]
        forbidden = ["shell", "merge", "deploy", "prepare"]

        for mod in modules:
            source = open(mod.__file__).read()
            for word in forbidden:
                # Check for function definitions or imports, not just strings
                assert f"def {word}" not in source, (
                    f"LA2 module {mod.__name__} defines forbidden function: {word}"
                )
            # LA4 adds execute_job() for governed scan execution — allow it.
            # But bare "def execute(" (arbitrary command execution) is forbidden.
            assert "def execute(" not in source, (
                f"LA2 module {mod.__name__} defines forbidden function: execute"
            )

    def test_no_inbound_ports(self):
        """LA2 does not expose inbound network ports."""
        import evosia_agent.agent as agent_mod
        import evosia_agent.api_client as api_mod

        modules = [agent_mod, api_mod]
        for mod in modules:
            source = open(mod.__file__).read()
            assert "uvicorn" not in source
            assert "FastAPI" not in source
            assert "listen(" not in source
            assert "bind(" not in source

    def test_version_info(self):
        """Version is properly defined."""
        assert __version__
        assert "evosia-agent" in AGENT_VERSION
