"""Connector pairing — browser-assisted device pairing for P3c."""

from __future__ import annotations

import json
import logging
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass

from .config import AgentConfig

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 2
POLL_TIMEOUT_SECONDS = 300  # 5 minutes
POLL_MAX_ATTEMPTS = POLL_TIMEOUT_SECONDS // POLL_INTERVAL_SECONDS


@dataclass
class PairingState:
    """Connector pairing state."""

    UNPAIRED = "unpaired"
    REQUESTING = "requesting"
    WAITING_FOR_BROWSER = "waiting_for_browser"
    PAIRED = "paired"
    DENIED = "denied"
    EXPIRED = "expired"
    FAILED = "failed"


class PairingClient:
    """Client for browser-assisted pairing flow.

    Handles: request creation, browser launch, polling, credential exchange.
    Uses outbound HTTPS only — no inbound ports.
    """

    def __init__(self, cloud_url: str) -> None:
        self._cloud_url = cloud_url.rstrip("/")

    def create_pairing_request(
        self, device_name: str, platform: str, agent_version: str
    ) -> dict:
        """Create a pairing request and get the browser URL."""
        url = f"{self._cloud_url}/api/pairing/request"
        body = {
            "device_name": device_name,
            "platform": platform,
            "agent_version": agent_version,
        }
        return self._post(url, body)

    def poll_pairing_status(self, pairing_id: str) -> dict:
        """Poll pairing status."""
        url = f"{self._cloud_url}/api/pairing/{pairing_id}/status"
        return self._get(url)

    def consume_pairing(self, pairing_id: str) -> dict:
        """Consume an approved pairing to get device credential."""
        url = f"{self._cloud_url}/api/pairing/{pairing_id}/consume"
        return self._post(url, {})

    def open_browser(self, pairing_url: str) -> bool:
        """Open the default browser to the pairing URL."""
        try:
            webbrowser.open(pairing_url)
            return True
        except Exception as exc:
            logger.warning("Failed to open browser: %s", exc)
            return False

    def _post(self, url: str, body: dict) -> dict:
        """POST request to cloud API."""
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise Exception(f"API error {exc.code}: {detail}") from exc

    def _get(self, url: str) -> dict:
        """GET request to cloud API."""
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise Exception(f"API error {exc.code}: {detail}") from exc


def run_pairing_flow(
    config: AgentConfig,
    device_name: str,
    platform: str,
    agent_version: str,
) -> tuple[str, str] | None:
    """Execute the browser-assisted pairing flow.

    Returns (device_id, device_token) on success, None on failure.
    """
    client = PairingClient(config.cloud_url)

    print()
    print("Connecting to EVOSIA...")
    print()

    # Step 1: Create pairing request
    try:
        result = client.create_pairing_request(device_name, platform, agent_version)
    except Exception as exc:
        print(f"Error creating pairing request: {exc}")
        return None

    pairing_id = result["pairing_id"]
    pairing_url = result["pairing_url"]

    print(f"Open this URL in your browser to connect:")
    print()
    print(f"  {pairing_url}")
    print()

    # Step 2: Try to open browser
    if client.open_browser(pairing_url):
        print("Browser opened. Please sign in and approve the connection.")
    else:
        print("Please open the URL above in your browser.")

    print()
    print("Waiting for approval...")

    # Step 3: Poll for approval
    for attempt in range(POLL_MAX_ATTEMPTS):
        time.sleep(POLL_INTERVAL_SECONDS)

        try:
            status_result = client.poll_pairing_status(pairing_id)
        except Exception as exc:
            logger.warning("Poll error (attempt %d): %s", attempt + 1, exc)
            continue

        current_status = status_result.get("status", "")

        if current_status == "APPROVED":
            print("Approved! Completing connection...")
            # Step 4: Consume the pairing to get credential
            try:
                consume_result = client.consume_pairing(pairing_id)
                device_id = consume_result["device_id"]
                device_token = consume_result["device_credential"]
                print("Connected successfully!")
                return device_id, device_token
            except Exception as exc:
                print(f"Error completing connection: {exc}")
                return None

        elif current_status == "DENIED":
            print("Pairing denied by user.")
            return None

        elif current_status == "EXPIRED":
            print("Pairing request expired. Please try again.")
            return None

        elif current_status == "CONSUMED":
            print("Pairing request already used.")
            return None

        # Still PENDING — keep polling
        remaining = POLL_TIMEOUT_SECONDS - (attempt + 1) * POLL_INTERVAL_SECONDS
        if remaining <= 0:
            break

    print("Pairing timed out. Please try again.")
    return None
