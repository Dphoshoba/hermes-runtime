from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .mission import Mission, MissionPlanner, Plan


# ---------------------------------------------------------------------------
# Mission Type Metadata
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MissionTypeMetadata:
    """Describes a registered mission type."""
    name: str
    version: str
    description: str
    category: str  # maintenance, security, performance, documentation, release, testing
    required_capabilities: tuple[str, ...] = ()
    default_constraints: tuple[str, ...] = ()
    supported_task_patterns: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "category": self.category,
            "required_capabilities": list(self.required_capabilities),
            "default_constraints": list(self.default_constraints),
            "supported_task_patterns": list(self.supported_task_patterns),
            "metadata": dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# Mission Type ABC
# ---------------------------------------------------------------------------

class MissionType(ABC):
    """Base class for extensible mission types.

    Subclass this to define a new mission type. Implement:
    - get_metadata(): return type metadata
    - validate_mission(): type-specific validation beyond the base planner
    - build_tasks(): generate tasks for this mission type (optional override)
    """

    @abstractmethod
    def get_metadata(self) -> MissionTypeMetadata:
        """Return metadata describing this mission type."""

    def validate_mission(self, mission: Mission) -> tuple[list[str], list[str]]:
        """Type-specific validation. Returns (errors, warnings).

        Override to add type-specific checks beyond the base MissionPlanner.
        The base implementation returns empty lists (no additional validation).
        """
        return [], []

    def build_tasks(
        self,
        mission: Mission,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Generate task definitions for this mission type.

        Override to provide automated task generation from mission parameters.
        Returns a list of task dicts compatible with MissionTask.
        The base implementation returns the tasks already in the mission.
        """
        return [t.as_dict() for t in mission.tasks]

    def get_default_constraints(self) -> tuple[str, ...]:
        """Return default constraints for this mission type."""
        return self.get_metadata().default_constraints

    def get_required_capabilities(self) -> tuple[str, ...]:
        """Return required capabilities for this mission type."""
        return self.get_metadata().required_capabilities


# ---------------------------------------------------------------------------
# Mission Type Registry
# ---------------------------------------------------------------------------

class MissionTypeRegistry:
    """Singleton registry for mission types.

    Types can be registered:
    1. Programmatically via register()
    2. Via entry points under hermes_v01.mission_types
    """

    _instance: Optional[MissionTypeRegistry] = None

    def __init__(self) -> None:
        self._types: dict[str, MissionType] = {}
        self._metadata: dict[str, MissionTypeMetadata] = {}

    @classmethod
    def instance(cls) -> MissionTypeRegistry:
        """Get or create the singleton registry."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        cls._instance = None

    def register(self, mission_type: MissionType) -> None:
        """Register a mission type. Raises ValueError on duplicate name."""
        metadata = mission_type.get_metadata()
        if not metadata.name:
            raise ValueError("mission type name must not be empty")
        if metadata.name in self._types:
            raise ValueError(f"mission type already registered: {metadata.name}")
        self._types[metadata.name] = mission_type
        self._metadata[metadata.name] = metadata

    def unregister(self, name: str) -> None:
        """Unregister a mission type. Raises KeyError if not found."""
        if name not in self._types:
            raise KeyError(f"mission type not found: {name}")
        del self._types[name]
        del self._metadata[name]

    def get(self, name: str) -> MissionType:
        """Get a mission type by name. Raises KeyError if not found."""
        if name not in self._types:
            raise KeyError(f"mission type not found: {name}")
        return self._types[name]

    def get_metadata(self, name: str) -> MissionTypeMetadata:
        """Get metadata for a mission type. Raises KeyError if not found."""
        if name not in self._metadata:
            raise KeyError(f"mission type not found: {name}")
        return self._metadata[name]

    def list_types(self, category: Optional[str] = None) -> list[MissionTypeMetadata]:
        """List all registered mission types, optionally filtered by category."""
        items = list(self._metadata.values())
        if category is not None:
            items = [m for m in items if m.category == category]
        return sorted(items, key=lambda m: m.name)

    def list_names(self) -> list[str]:
        """Return sorted list of registered mission type names."""
        return sorted(self._types.keys())

    def is_registered(self, name: str) -> bool:
        """Check if a mission type is registered."""
        return name in self._types

    def discover_entry_points(self) -> int:
        """Discover and register mission types from entry points.

        Looks for entry points under 'hermes_v01.mission_types'.
        Returns the number of newly registered types.
        """
        count = 0
        try:
            from importlib.metadata import entry_points
            eps = entry_points()
            if hasattr(eps, "select"):
                mission_eps = eps.select(group="hermes_v01.mission_types")
            else:
                mission_eps = eps.get("hermes_v01.mission_types", [])
            for ep in mission_eps:
                try:
                    cls = ep.load()
                    if isinstance(cls, type) and issubclass(cls, MissionType) and cls is not MissionType:
                        instance = cls()
                        if not self.is_registered(instance.get_metadata().name):
                            self.register(instance)
                            count += 1
                except Exception:
                    continue
        except ImportError:
            pass
        return count


# ---------------------------------------------------------------------------
# Built-in Mission Types
# ---------------------------------------------------------------------------

class RepositoryMaintenance(MissionType):
    """Repository maintenance tasks (cleanup, formatting, linting)."""

    def get_metadata(self) -> MissionTypeMetadata:
        return MissionTypeMetadata(
            name="repository-maintenance",
            version="1.0.0",
            description="Repository maintenance: cleanup, formatting, linting, and housekeeping tasks",
            category="maintenance",
            default_constraints=(
                "repository must be accessible",
                "no uncommitted changes preferred",
            ),
            supported_task_patterns=("cleanup", "format", "lint", "housekeeping"),
        )

    def validate_mission(self, mission: Mission) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        if not mission.repository:
            warnings.append("repository-maintenance missions should specify a repository")
        return errors, warnings


class DependencyUpgrade(MissionType):
    """Dependency upgrade and management tasks."""

    def get_metadata(self) -> MissionTypeMetadata:
        return MissionTypeMetadata(
            name="dependency-upgrade",
            version="1.0.0",
            description="Dependency upgrade: update packages, verify compatibility, run tests",
            category="maintenance",
            default_constraints=(
                "repository must be accessible",
                "dependency lock file must be present",
            ),
            supported_task_patterns=("upgrade", "update", "dependency", "package"),
        )

    def validate_mission(self, mission: Mission) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        if not mission.repository:
            warnings.append("dependency-upgrade missions should specify a repository")
        return errors, warnings


class DocumentationRefresh(MissionType):
    """Documentation generation and refresh tasks."""

    def get_metadata(self) -> MissionTypeMetadata:
        return MissionTypeMetadata(
            name="documentation-refresh",
            version="1.0.0",
            description="Documentation refresh: regenerate docs, check links, update READMEs",
            category="documentation",
            default_constraints=(
                "documentation tools must be available",
            ),
            supported_task_patterns=("docs", "readme", "documentation", "changelog"),
        )


class SecurityAudit(MissionType):
    """Security audit and vulnerability scanning tasks."""

    def get_metadata(self) -> MissionTypeMetadata:
        return MissionTypeMetadata(
            name="security-audit",
            version="1.0.0",
            description="Security audit: vulnerability scanning, dependency audit, secret detection",
            category="security",
            required_capabilities=("security-scanner",),
            default_constraints=(
                "security scanning tools must be available",
                "network access may be required",
            ),
            supported_task_patterns=("audit", "scan", "security", "vulnerability"),
        )

    def validate_mission(self, mission: Mission) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        for task in mission.tasks:
            if "network" in str(task.metadata).lower():
                warnings.append(f"task '{task.title}' may require network access")
        return errors, warnings


class PerformanceAudit(MissionType):
    """Performance audit and benchmarking tasks."""

    def get_metadata(self) -> MissionTypeMetadata:
        return MissionTypeMetadata(
            name="performance-audit",
            version="1.0.0",
            description="Performance audit: benchmarking, profiling, regression detection",
            category="performance",
            default_constraints=(
                "performance tools must be available",
                "stable system state preferred",
            ),
            supported_task_patterns=("benchmark", "profile", "performance", "perf"),
        )


class ReleasePreparation(MissionType):
    """Release preparation and versioning tasks."""

    def get_metadata(self) -> MissionTypeMetadata:
        return MissionTypeMetadata(
            name="release-preparation",
            version="1.0.0",
            description="Release preparation: version bumps, changelog generation, artifact building",
            category="release",
            default_constraints=(
                "all tests must pass",
                "clean working tree preferred",
                "release tooling must be available",
            ),
            supported_task_patterns=("release", "version", "changelog", "publish"),
        )

    def validate_mission(self, mission: Mission) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        if not mission.repository:
            warnings.append("release-preparation missions should specify a repository")
        if not mission.metadata.get("version"):
            warnings.append("release-preparation missions should specify a version in metadata")
        return errors, warnings


class CITask(MissionType):
    """CI/CD verification and pipeline tasks."""

    def get_metadata(self) -> MissionTypeMetadata:
        return MissionTypeMetadata(
            name="ci-verification",
            version="1.0.0",
            description="CI verification: pipeline checks, test runs, build verification",
            category="testing",
            default_constraints=(
                "CI environment must be available",
            ),
            supported_task_patterns=("ci", "test", "build", "verify"),
        )


# ---------------------------------------------------------------------------
# Default type registration
# ---------------------------------------------------------------------------

def register_built_in_types(registry: MissionTypeRegistry) -> None:
    """Register all built-in mission types into the given registry."""
    built_ins = [
        RepositoryMaintenance(),
        DependencyUpgrade(),
        DocumentationRefresh(),
        SecurityAudit(),
        PerformanceAudit(),
        ReleasePreparation(),
        CITask(),
    ]
    for mt in built_ins:
        if not registry.is_registered(mt.get_metadata().name):
            registry.register(mt)
