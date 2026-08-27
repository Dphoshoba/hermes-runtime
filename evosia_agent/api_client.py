"""API client — narrow HTTPS client for LA2 cloud operations."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .version import AGENT_VERSION

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 10


@dataclass
class ApiError(Exception):
    """Structured API error with status code and detail."""

    status_code: int
    detail: str

    def __str__(self) -> str:
        return f"API error {self.status_code}: {self.detail}"


class ApiClient:
    """Narrow HTTPS client for LA2 operations.

    Only supports: registration exchange, heartbeat.
    No generic method that exposes arbitrary cloud requests.
    """

    def __init__(self, cloud_url: str) -> None:
        self._cloud_url = cloud_url.rstrip("/")

    def exchange_bootstrap_token(
        self, bootstrap_token: str, device_token: str
    ) -> dict[str, Any]:
        """Exchange bootstrap token for device credential.

        POST /api/devices/exchange
        Body: {"bootstrap_token": "..."}
        """
        url = f"{self._cloud_url}/api/devices/exchange"
        body = {"bootstrap_token": bootstrap_token}

        return self._post(url, body, auth_header=None)

    def send_heartbeat(
        self, device_id: str, device_credential: str, agent_version: str
    ) -> dict[str, Any]:
        """Send heartbeat with device credential.

        POST /api/agent/heartbeat
        Body: {"device_id": "...", "agent_version": "..."}
        Authorization: Bearer <device_credential>
        """
        url = f"{self._cloud_url}/api/agent/heartbeat"
        body = {
            "device_id": device_id,
            "agent_version": agent_version,
        }

        return self._post(url, body, auth_header=f"Bearer {device_credential}")

    def _post(
        self,
        url: str,
        body: dict[str, Any],
        auth_header: str | None = None,
    ) -> dict[str, Any]:
        """Make a POST request with TLS verification enabled."""
        data = json.dumps(body).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "User-Agent": AGENT_VERSION,
        }
        if auth_header:
            headers["Authorization"] = auth_header

        request = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                response_data = response.read().decode("utf-8")
                return json.loads(response_data) if response_data else {}
        except urllib.error.HTTPError as exc:
            detail = _safe_error_detail(exc)
            raise ApiError(status_code=exc.code, detail=detail) from exc
        except urllib.error.URLError as exc:
            raise ApiError(status_code=0, detail=f"Connection failed: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise ApiError(status_code=0, detail="Invalid JSON response") from exc


def _safe_error_detail(exc: urllib.error.HTTPError) -> str:
    """Extract error detail without leaking secrets."""
    try:
        body = exc.read().decode("utf-8")
        data = json.loads(body)
        return data.get("detail", f"HTTP {exc.code}")
    except Exception:
        return f"HTTP {exc.code}"
