"""P3a Smoke tests for packaged EVOSIA Connector runtime.

These tests verify the packaged runtime can start, report version,
and resolve configuration without requiring real production device
registration.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


class TestConnectorPackageExists:
    """Verify the evosia_connector package is importable."""

    def test_connector_package_importable(self):
        """evosia_connector package can be imported."""
        import evosia_connector
        assert evosia_connector is not None

    def test_version_importable(self):
        """Version module is importable."""
        from evosia_connector.version import CONNECTOR_PRODUCT_VERSION, BUILD_CHANNEL
        assert CONNECTOR_PRODUCT_VERSION == "0.1.0"
        assert BUILD_CHANNEL == "production"

    def test_config_importable(self):
        """Config module is importable."""
        from evosia_connector.config import ConnectorConfig, PRODUCTION_CLOUD_URL
        assert PRODUCTION_CLOUD_URL == "https://evosia-cloud.fly.dev"

    def test_launcher_importable(self):
        """Launcher module is importable."""
        from evosia_connector.launcher import main, cli_status, cli_version
        assert callable(main)
        assert callable(cli_status)
        assert callable(cli_version)


class TestConnectorVersion:
    """Verify version reporting works."""

    def test_connector_version_string(self):
        """Connector version string is well-formed."""
        from evosia_connector.version import CONNECTOR_VERSION
        assert "EVOSIA Connector" in CONNECTOR_VERSION
        assert "0.1.0" in CONNECTOR_VERSION

    def test_agent_version_compatible(self):
        """Agent version is compatible with connector version."""
        from evosia_connector.version import RUNTIME_VERSION, AGENT_VERSION_STRING
        assert RUNTIME_VERSION == "0.1.0"
        assert "evosia-agent" in AGENT_VERSION_STRING


class TestConnectorConfiguration:
    """Verify production-safe configuration resolution."""

    def test_production_cloud_url(self):
        """Production build uses production cloud URL."""
        from evosia_connector.config import ConnectorConfig
        config = ConnectorConfig()
        assert config.cloud_url == "https://evosia-cloud.fly.dev"

    def test_production_no_localhost_fallback(self):
        """Production build cannot silently default to localhost."""
        from evosia_connector.config import ConnectorConfig
        config = ConnectorConfig()
        assert "localhost" not in config.cloud_url
        assert "127.0.0.1" not in config.cloud_url

    def test_connector_data_dir_resolves(self):
        """Data directory resolves to a valid path."""
        from evosia_connector.config import ConnectorConfig
        config = ConnectorConfig()
        assert config.data_dir is not None
        assert isinstance(config.data_dir, Path)

    def test_channel_identity(self):
        """Build channel is production."""
        from evosia_connector.config import ConnectorConfig
        config = ConnectorConfig()
        assert config.channel == "production"
        assert config.is_production

    def test_env_override_ignored_in_production(self):
        """Environment variable override is ignored in production builds."""
        from evosia_connector.config import ConnectorConfig
        with patch.dict(os.environ, {"EVOSIA_CLOUD_URL": "http://localhost:9999"}):
            config = ConnectorConfig()
            # Production build should ignore the override
            assert config.cloud_url == "https://evosia-cloud.fly.dev"

    def test_devices_endpoint(self):
        """Devices endpoint resolves correctly."""
        from evosia_connector.config import ConnectorConfig
        config = ConnectorConfig()
        assert config.devices_endpoint == "https://evosia-cloud.fly.dev/api/devices/exchange"

    def test_heartbeat_endpoint(self):
        """Heartbeat endpoint resolves correctly."""
        from evosia_connector.config import ConnectorConfig
        config = ConnectorConfig()
        assert config.heartbeat_endpoint == "https://evosia-cloud.fly.dev/api/agent/heartbeat"


class TestPackagedImports:
    """Verify all required evosia_agent imports resolve."""

    def test_agent_import(self):
        """evosia_agent is importable."""
        import evosia_agent
        assert evosia_agent is not None

    def test_agent_config_import(self):
        """evosia_agent.config is importable."""
        from evosia_agent.config import AgentConfig, DEFAULT_CLOUD_URL
        assert DEFAULT_CLOUD_URL == "https://evosia-cloud.fly.dev"

    def test_agent_version_import(self):
        """evosia_agent.version is importable."""
        from evosia_agent.version import __version__, AGENT_VERSION
        assert __version__ == "0.1.0"
        assert "evosia-agent" in AGENT_VERSION

    def test_credential_store_import(self):
        """evosia_agent.credential_store is importable."""
        from evosia_agent.credential_store import CredentialStore, DeviceCredential
        assert CredentialStore is not None

    def test_scanner_import(self):
        """evosia_agent.scanner is importable."""
        from evosia_agent.scanner import ScanLimits
        assert ScanLimits is not None

    def test_path_validation_import(self):
        """evosia_agent.path_validation is importable."""
        from evosia_agent.path_validation import canonicalize_path
        assert callable(canonicalize_path)


class TestNoSourceCheckoutRequired:
    """Verify runtime does not depend on source checkout."""

    def test_version_from_package_not_file(self):
        """Version is read from package, not from source file paths."""
        from evosia_agent.version import __version__
        # Should resolve without requiring __file__ to be in source tree
        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_config_resolves_without_cwd(self):
        """Configuration resolves independently of current working directory."""
        from evosia_connector.config import ConnectorConfig
        original_cwd = os.getcwd()
        try:
            os.chdir(Path.home())  # Change to home directory
            config = ConnectorConfig()
            assert config.cloud_url == "https://evosia-cloud.fly.dev"
        finally:
            os.chdir(original_cwd)


class TestBackgroundRuntimeReady:
    """Verify runtime is compatible with future background launch."""

    def test_no_interactive_input_required(self):
        """Agent does not require interactive terminal input during steady-state."""
        from evosia_agent.agent import LocalAgent
        import inspect
        source = inspect.getsource(LocalAgent.run)
        # Verify no input() calls in the run method
        assert "input(" not in source

    def test_signal_handlers_setup(self):
        """Agent sets up signal handlers for graceful shutdown."""
        from evosia_agent.agent import LocalAgent
        import inspect
        source = inspect.getsource(LocalAgent)
        assert "signal" in source
