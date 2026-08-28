"""Configuration — cloud URL, data directory, and agent settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


# Default cloud URL — overridable via EVOSIA_CLOUD_URL env var
DEFAULT_CLOUD_URL = "https://evosia-cloud.fly.dev"

# Heartbeat interval in seconds
HEARTBEAT_INTERVAL_SECONDS = 60

# Retry backoff parameters
RETRY_BASE_SECONDS = 5
RETRY_MAX_SECONDS = 60
RETRY_MULTIPLIER = 2


@dataclass
class AgentConfig:
    """Agent configuration. Loaded from environment and platform conventions."""

    cloud_url: str = ""
    data_dir: Path | None = None

    def __post_init__(self) -> None:
        if not self.cloud_url:
            self.cloud_url = os.environ.get("EVOSIA_CLOUD_URL", DEFAULT_CLOUD_URL)
        if self.data_dir is None:
            self.data_dir = _default_data_dir()

    @property
    def devices_endpoint(self) -> str:
        return f"{self.cloud_url}/api/devices/exchange"

    @property
    def heartbeat_endpoint(self) -> str:
        return f"{self.cloud_url}/api/agent/heartbeat"


def _default_data_dir() -> Path:
    r"""Return platform-appropriate data directory for LA2.

    macOS: ~/Library/Application Support/EVOSIA/
    Windows: %LOCALAPPDATA%\EVOSIA\
    Linux: ~/.local/share/EVOSIA/
    """
    system = __import__("platform").system()
    home = Path.home()

    if system == "Darwin":
        return home / "Library" / "Application Support" / "EVOSIA"
    if system == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local"))
        return Path(local_app_data) / "EVOSIA"
    # Linux / fallback
    return home / ".local" / "share" / "EVOSIA"
