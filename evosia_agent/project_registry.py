"""Project registry — local storage for authorized projects."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from .path_validation import compute_local_root_fingerprint, validate_project_root

logger = logging.getLogger(__name__)


@dataclass
class LocalProject:
    """Local project registration record."""

    cloud_project_id: str
    canonical_local_root: str
    display_name: str
    local_root_fingerprint: str
    authority: str = "REVIEW_ONLY"
    status: str = "active"
    registered_at: str = ""
    revoked_at: str = ""


class ProjectRegistry:
    """Persistent local storage for authorized projects.

    Stores in a JSON file with restrictive permissions.
    """

    FILENAME = "projects.json"

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._registry_path = data_dir / self.FILENAME
        self._projects: dict[str, LocalProject] = {}
        self._load()

    def _load(self) -> None:
        """Load registry from disk."""
        if not self._registry_path.exists():
            return

        try:
            data = json.loads(self._registry_path.read_text(encoding="utf-8"))
            for pid, pdata in data.items():
                self._projects[pid] = LocalProject(**pdata)
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Corrupted project registry, starting fresh: %s", exc)
            self._projects = {}

    def _save(self) -> None:
        """Save registry to disk."""
        self._data_dir.mkdir(parents=True, exist_ok=True)

        data = {}
        for pid, proj in self._projects.items():
            data[pid] = {
                "cloud_project_id": proj.cloud_project_id,
                "canonical_local_root": proj.canonical_local_root,
                "display_name": proj.display_name,
                "local_root_fingerprint": proj.local_root_fingerprint,
                "authority": proj.authority,
                "status": proj.status,
                "registered_at": proj.registered_at,
                "revoked_at": proj.revoked_at,
            }

        self._registry_path.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )

        # Set restrictive permissions on Unix
        try:
            self._registry_path.chmod(0o600)
        except (OSError, AttributeError):
            pass

    @property
    def projects(self) -> list[LocalProject]:
        """Return list of all registered projects."""
        return list(self._projects.values())

    def get(self, project_id: str) -> LocalProject | None:
        """Get project by ID."""
        return self._projects.get(project_id)

    def get_by_path(self, canonical_path: str) -> LocalProject | None:
        """Get project by canonical local root path."""
        for proj in self._projects.values():
            if proj.canonical_local_root == canonical_path:
                return proj
        return None

    def add(
        self,
        cloud_project_id: str,
        canonical_local_root: Path,
        display_name: str,
        authority: str = "REVIEW_ONLY",
    ) -> LocalProject:
        """Add a new project to the registry."""
        from datetime import datetime, timezone

        canonical_str = str(canonical_local_root)
        fingerprint = compute_local_root_fingerprint(canonical_local_root)

        proj = LocalProject(
            cloud_project_id=cloud_project_id,
            canonical_local_root=canonical_str,
            display_name=display_name,
            local_root_fingerprint=fingerprint,
            authority=authority,
            status="active",
            registered_at=datetime.now(timezone.utc).isoformat(),
        )

        self._projects[cloud_project_id] = proj
        self._save()
        return proj

    def remove(self, project_id: str) -> bool:
        """Remove a project from the registry."""
        if project_id in self._projects:
            del self._projects[project_id]
            self._save()
            return True
        return False

    def revoke(self, project_id: str) -> bool:
        """Mark a project as revoked."""
        from datetime import datetime, timezone

        proj = self._projects.get(project_id)
        if proj:
            proj.status = "revoked"
            proj.revoked_at = datetime.now(timezone.utc).isoformat()
            self._save()
            return True
        return False
