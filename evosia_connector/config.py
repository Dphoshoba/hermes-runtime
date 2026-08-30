"""EVOSIA Connector — production-safe configuration.

Configuration precedence (highest to lowest):
    1. Explicit developer override (EVOSIA_CLOUD_URL env var, development only)
    2. Packaged channel configuration (BUILD_CHANNEL)
    3. Safe production default

Production builds MUST NOT silently default to localhost.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .version import BUILD_CHANNEL


# Production cloud endpoint — embedded in packaged builds
PRODUCTION_CLOUD_URL = "https://evosia-cloud.fly.dev"

# Development cloud endpoint — only reachable with explicit override
DEVELOPMENT_CLOUD_URL = "http://localhost:8000"

# Safe default — production
DEFAULT_CLOUD_URL = PRODUCTION_CLOUD_URL


def _resolve_cloud_url() -> str:
    """Resolve the cloud endpoint using the precedence model.

    Production builds:
        - If EVOSIA_CLOUD_URL is set AND channel is 'development', use override
        - Otherwise, always use production endpoint

    This prevents accidental connection to development endpoints.
    """
    env_override = os.environ.get("EVOSIA_CLOUD_URL", "")

    if env_override and BUILD_CHANNEL == "development":
        return env_override

    if env_override and BUILD_CHANNEL != "development":
        # In production builds, ignore env var override for safety
        return PRODUCTION_CLOUD_URL

    return PRODUCTION_CLOUD_URL


def _default_data_dir() -> Path:
    r"""Return platform-appropriate data directory.

    Windows: %LOCALAPPDATA%\EVOSIA\Connector\
    macOS: ~/Library/Application Support/EVOSIA/Connector/
    Linux: ~/.local/share/EVOSIA/Connector/
    """
    system = __import__("platform").system()
    home = Path.home()

    if system == "Darwin":
        return home / "Library" / "Application Support" / "EVOSIA" / "Connector"
    if system == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local"))
        return Path(local_app_data) / "EVOSIA" / "Connector"
    # Linux / fallback
    return home / ".local" / "share" / "EVOSIA" / "Connector"


@dataclass
class ConnectorConfig:
    """Connector configuration. Production-safe defaults."""

    cloud_url: str = ""
    data_dir: Path | None = None
    channel: str = BUILD_CHANNEL

    def __post_init__(self) -> None:
        if not self.cloud_url:
            self.cloud_url = _resolve_cloud_url()
        if self.data_dir is None:
            self.data_dir = _default_data_dir()

    @property
    def is_production(self) -> bool:
        """Check if this is a production build."""
        return self.channel == "production"

    @property
    def devices_endpoint(self) -> str:
        return f"{self.cloud_url}/api/devices/exchange"

    @property
    def heartbeat_endpoint(self) -> str:
        return f"{self.cloud_url}/api/agent/heartbeat"
