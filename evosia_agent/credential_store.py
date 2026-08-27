"""Credential store — secure local storage for device identity and credentials."""

from __future__ import annotations

import json
import logging
import stat
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DeviceCredential:
    """Stored device credential. Plaintext JWT is stored with restricted permissions."""

    device_id: str
    device_name: str
    credential: str  # JWT — stored with restrictive file permissions
    cloud_url: str


class CredentialStore:
    """Persistent local storage for device identity and credential.

    Stores in a JSON file with restrictive permissions (owner-only read/write).
    Future enhancement: migrate to OS keychain via abstract interface.
    """

    FILENAME = "device.json"
    FILE_PERMISSIONS = 0o600  # Owner read/write only

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._credential_path = data_dir / self.FILENAME

    @property
    def is_registered(self) -> bool:
        """Check if device has stored credentials."""
        return self._credential_path.exists()

    def load(self) -> DeviceCredential:
        """Load stored credential. Raises FileNotFoundError if not registered."""
        if not self.is_registered:
            raise FileNotFoundError("Device not registered")
        try:
            data = json.loads(self._credential_path.read_text(encoding="utf-8"))
            return DeviceCredential(
                device_id=data["device_id"],
                device_name=data["device_name"],
                credential=data["credential"],
                cloud_url=data["cloud_url"],
            )
        except (json.JSONDecodeError, KeyError) as exc:
            raise FileNotFoundError("Corrupted credential store") from exc

    def save(self, cred: DeviceCredential) -> None:
        """Save credential with restrictive file permissions."""
        self._data_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "device_id": cred.device_id,
            "device_name": cred.device_name,
            "credential": cred.credential,
            "cloud_url": cred.cloud_url,
        }

        # Write with restrictive permissions
        self._credential_path.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )

        # Enforce owner-only permissions (Unix-like systems)
        try:
            self._credential_path.chmod(self.FILE_PERMISSIONS)
        except (OSError, AttributeError):
            # Windows or unsupported platforms — document limitation
            logger.warning(
                "Could not set restrictive file permissions on %s. "
                "Credential file may be readable by other users.",
                self._credential_path,
            )

    def delete(self) -> None:
        """Remove stored credential (logout)."""
        if self._credential_path.exists():
            self._credential_path.unlink()
            logger.info("Local credential removed")
