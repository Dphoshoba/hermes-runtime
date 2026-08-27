"""Project API — cloud API client for project registration."""

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
    """Structured API error."""

    status_code: int
    detail: str

    def __str__(self) -> str:
        return f"API error {self._status_code}: {self.detail}"


class ProjectApiClient:
    """Narrow HTTPS client for LA3 project operations.

    Only supports: project authorization, registration, list, revoke.
    No generic method for arbitrary cloud requests.
    """

    def __init__(self, cloud_url: str, device_credential: str) -> None:
        self._cloud_url = cloud_url.rstrip("/")
        self._credential = device_credential

    def request_project_authorization_token(self, device_id: str) -> dict[str, Any]:
        """Request a short-lived project authorization token.

        POST /api/devices/{device_id}/project-auth-token
        """
        url = f"{self._cloud_url}/api/devices/{device_id}/project-auth-token"
        return self._post(url, {})

    def register_project(
        self, device_id: str, display_name: str, local_root_fingerprint: str,
        project_authorization_token: str,
    ) -> dict[str, Any]:
        """Register a project with EVOSIA Cloud.

        POST /api/device-projects
        """
        url = f"{self._cloud_url}/api/device-projects"
        body = {
            "device_id": device_id,
            "display_name": display_name,
            "local_root_fingerprint": local_root_fingerprint,
            "project_authorization_token": project_authorization_token,
        }

        return self._post(url, body)

    def list_projects(self, device_id: str) -> list[dict[str, Any]]:
        """List projects for a device.

        GET /api/device-projects?device_id=...
        """
        url = f"{self._cloud_url}/api/device-projects?device_id={device_id}"
        return self._get(url)

    def revoke_project(self, project_id: str) -> dict[str, Any]:
        """Revoke a project.

        POST /api/device-projects/{id}/revoke
        """
        url = f"{self._cloud_url}/api/device-projects/{project_id}/revoke"
        return self._post(url, {})

    def _post(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        """Make POST request with device credential."""
        data = json.dumps(body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._credential}",
            "User-Agent": AGENT_VERSION,
        }
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

    def _get(self, url: str) -> Any:
        """Make GET request with device credential."""
        headers = {
            "Authorization": f"Bearer {self._credential}",
            "User-Agent": AGENT_VERSION,
        }
        request = urllib.request.Request(url, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                response_data = response.read().decode("utf-8")
                return json.loads(response_data) if response_data else []
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
