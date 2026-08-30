"""Connector project authorization — browser-assisted project authorization for P3d."""

from __future__ import annotations

import json
import logging
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path

from .config import ConnectorConfig

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 2
POLL_TIMEOUT_SECONDS = 600  # 10 minutes
POLL_MAX_ATTEMPTS = POLL_TIMEOUT_SECONDS // POLL_INTERVAL_SECONDS


@dataclass
class ProjectAuthorizationState:
    """Connector project authorization state."""

    NO_PROJECT = "no_project"
    SELECTING = "selecting"
    VALIDATING = "validating"
    READY_FOR_CONFIRMATION = "ready_for_confirmation"
    AUTHORIZING = "authorizing"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    AUTHORIZED = "authorized"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ProjectAuthorizationClient:
    """Client for browser-assisted project authorization flow.

    Handles: request creation, browser launch, polling, DeviceProject creation.
    Uses outbound HTTPS only — no inbound ports.
    """

    def __init__(self, cloud_url: str) -> None:
        self._cloud_url = cloud_url.rstrip("/")

    def create_authorization_request(
        self,
        display_name: str,
        local_root_fingerprint: str,
        platform: str,
        agent_version: str,
        device_credential: str,
    ) -> dict:
        """Create a project authorization request and get the browser URL."""
        url = f"{self._cloud_url}/api/project-authorization/request"
        body = {
            "display_name": display_name,
            "local_root_fingerprint": local_root_fingerprint,
            "platform": platform,
            "agent_version": agent_version,
        }
        return self._post(url, body, device_credential)

    def poll_authorization_status(self, request_id: str, device_credential: str) -> dict:
        """Poll project authorization status."""
        url = f"{self._cloud_url}/api/project-authorization/{request_id}/status"
        return self._get(url, device_credential)

    def consume_authorization(self, request_id: str, device_credential: str) -> dict:
        """Consume an approved authorization to create DeviceProject."""
        url = f"{self._cloud_url}/api/project-authorization/{request_id}/consume"
        return self._post(url, {}, device_credential)

    def open_browser(self, authorization_url: str) -> bool:
        """Open the default browser to the authorization URL."""
        try:
            webbrowser.open(authorization_url)
            return True
        except Exception as exc:
            logger.warning("Failed to open browser: %s", exc)
            return False

    def _post(self, url: str, body: dict, device_credential: str) -> dict:
        """POST request to cloud API with device credential."""
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {device_credential}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise Exception(f"API error {exc.code}: {detail}") from exc

    def _get(self, url: str, device_credential: str) -> dict:
        """GET request to cloud API with device credential."""
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {device_credential}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise Exception(f"API error {exc.code}: {detail}") from exc


def compute_local_root_fingerprint(canonical_path: Path) -> str:
    """Compute project fingerprint from canonical path."""
    import hashlib
    path_str = canonical_path.as_posix()
    return hashlib.sha256(path_str.encode()).hexdigest()


def validate_project_folder(folder_path: Path) -> tuple[bool, str, Path | None]:
    """Validate a project folder locally.

    Returns (is_valid, message, canonical_path).
    """
    if not folder_path.exists():
        return False, "Folder does not exist", None

    if not folder_path.is_dir():
        return False, "Path is not a directory", None

    try:
        canonical = folder_path.resolve()
    except Exception as exc:
        return False, f"Cannot resolve path: {exc}", None

    if not canonical.is_absolute():
        return False, "Path is not absolute after resolution", None

    return True, "Valid", canonical


def run_project_authorization_flow(
    config: ConnectorConfig,
    folder_path: Path,
    device_credential: str,
    device_name: str,
    platform: str,
    agent_version: str,
) -> str | None:
    """Execute the browser-assisted project authorization flow.

    Returns device_project_id on success, None on failure.
    """
    import hashlib
    from evosia_agent.path_validation import validate_project_root, has_symlink_escape, compute_local_root_fingerprint

    client = ProjectAuthorizationClient(config.cloud_url)

    print()
    print("Authorizing project for review...")
    print()

    # Step 1: Validate folder locally
    print("Validating folder...")
    is_valid, message, canonical = validate_project_folder(folder_path)
    if not is_valid:
        print(f"Error: {message}")
        return None

    # Step 2: Check for symlink escapes
    print("Checking for symlink escapes...")
    escape_results = has_symlink_escape(canonical)
    non_safe = [r for r in escape_results if r.status.value != "SAFE_INTERNAL"]
    if non_safe:
        print("Error: Project contains symlinks that escape the root directory")
        for r in non_safe:
            print(f"  - {r.symlink_path}: {r.status.value}")
        return None

    # Step 3: Compute fingerprint
    fingerprint = compute_local_root_fingerprint(canonical)
    display_name = canonical.name

    print(f"Project: {display_name}")
    print(f"Authority: Review Only")
    print(f"EVOSIA can: inspect this project when you explicitly start a review")
    print(f"EVOSIA cannot: change files, prepare changes, execute commands, deploy")
    print()

    # Step 4: Create authorization request
    try:
        result = client.create_authorization_request(
            display_name=display_name,
            local_root_fingerprint=fingerprint,
            platform=platform,
            agent_version=agent_version,
            device_credential=device_credential,
        )
    except Exception as exc:
        print(f"Error creating authorization request: {exc}")
        return None

    request_id = result["request_id"]
    authorization_url = result["authorization_url"]

    print(f"Open this URL in your browser to authorize the project:")
    print()
    print(f"  {authorization_url}")
    print()

    # Step 5: Try to open browser
    if client.open_browser(authorization_url):
        print("Browser opened. Please sign in and authorize the project.")
    else:
        print("Please open the URL above in your browser.")

    print()
    print("Waiting for authorization...")

    # Step 6: Poll for approval
    for attempt in range(POLL_MAX_ATTEMPTS):
        time.sleep(POLL_INTERVAL_SECONDS)

        try:
            status_result = client.poll_authorization_status(request_id, device_credential)
        except Exception as exc:
            logger.warning("Poll error (attempt %d): %s", attempt + 1, exc)
            continue

        current_status = status_result.get("status", "")

        if current_status == "APPROVED":
            print("Approved! Completing authorization...")
            # Step 7: Consume the authorization to create DeviceProject
            try:
                consume_result = client.consume_authorization(request_id, device_credential)
                device_project_id = consume_result["device_project_id"]
                print("Project authorized successfully!")
                print()
                print(f"Project ID: {device_project_id}")
                print(f"Authority: Review Only")
                print()
                print("No scan has been created. Choose 'Review Project' when you want to start a review.")
                return device_project_id
            except Exception as exc:
                print(f"Error completing authorization: {exc}")
                return None

        elif current_status == "DENIED":
            print("Authorization denied by user.")
            return None

        elif current_status == "EXPIRED":
            print("Authorization request expired. Please try again.")
            return None

        elif current_status == "CONSUMED":
            print("Authorization request already used.")
            return None

        # Still PENDING — keep polling
        remaining = POLL_TIMEOUT_SECONDS - (attempt + 1) * POLL_INTERVAL_SECONDS
        if remaining <= 0:
            break

    print("Authorization timed out. Please try again.")
    return None
