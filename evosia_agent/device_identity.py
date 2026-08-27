"""Device identity — safe metadata collection for LA2."""

from __future__ import annotations

import platform
import socket
from dataclasses import dataclass

from .version import AGENT_VERSION


@dataclass(frozen=True)
class DeviceIdentity:
    """Immutable device metadata. No sensitive data included."""

    device_name: str
    platform: str
    platform_version: str
    architecture: str
    agent_version: str

    @classmethod
    def collect(cls) -> DeviceIdentity:
        """Collect safe device metadata.

        Only collects non-sensitive information required for LA2 registration.
        Does NOT collect: username, home directory, file lists, installed
        applications, IP history, browser info, SSH info, environment variables.
        """
        return cls(
            device_name=socket.gethostname(),
            platform=_get_platform(),
            platform_version=platform.version(),
            architecture=platform.machine(),
            agent_version=AGENT_VERSION,
        )

    def to_register_payload(self) -> dict[str, str]:
        """Convert to API registration payload."""
        return {
            "device_name": self.device_name,
            "platform": self.platform,
            "agent_version": self.agent_version,
        }


def _get_platform() -> str:
    """Return normalized platform identifier."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    if system == "linux":
        return "linux"
    return system
