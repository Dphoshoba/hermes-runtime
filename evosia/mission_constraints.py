from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .mission import Mission


# ---------------------------------------------------------------------------
# Constraint Result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConstraintResult:
    """Result of evaluating a single constraint."""
    constraint_type: str
    name: str
    satisfied: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "constraint_type": self.constraint_type,
            "name": self.name,
            "satisfied": self.satisfied,
            "message": self.message,
            "details": dict(self.details),
        }


# ---------------------------------------------------------------------------
# Constraint Base
# ---------------------------------------------------------------------------

class MissionConstraint:
    """Base class for mission constraints."""

    @property
    def constraint_type(self) -> str:
        return self.__class__.__name__

    def evaluate(self, mission: Mission, context: dict[str, Any] | None = None) -> ConstraintResult:
        """Evaluate this constraint against a mission and optional context.

        Context may contain:
            - capability_registry: CapabilityRegistry
            - working_directory: Path
            - repository: Path
            - runtime_root: Path
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Required Capabilities Constraint
# ---------------------------------------------------------------------------

class RequiredCapabilityConstraint(MissionConstraint):
    """Checks that all required capabilities are registered and enabled."""

    @property
    def constraint_type(self) -> str:
        return "required_capabilities"

    def evaluate(self, mission: Mission, context: dict[str, Any] | None = None) -> ConstraintResult:
        context = context or {}
        registry = context.get("capability_registry")

        required = set(mission.required_capabilities)
        for task in mission.tasks:
            required.update(task.required_capabilities)

        if not required:
            return ConstraintResult(
                constraint_type=self.constraint_type,
                name="required_capabilities",
                satisfied=True,
                message="no capabilities required",
            )

        if registry is None:
            return ConstraintResult(
                constraint_type=self.constraint_type,
                name="required_capabilities",
                satisfied=False,
                message=f"capability registry not available; cannot verify {len(required)} required capabilities",
                details={"missing": sorted(required)},
            )

        missing: list[str] = []
        disabled: list[str] = []
        for cap_name in sorted(required):
            try:
                state = registry.get(cap_name)
                if not state.metadata.enabled:
                    disabled.append(cap_name)
            except KeyError:
                missing.append(cap_name)

        if missing or disabled:
            parts: list[str] = []
            if missing:
                parts.append(f"missing: {', '.join(missing)}")
            if disabled:
                parts.append(f"disabled: {', '.join(disabled)}")
            return ConstraintResult(
                constraint_type=self.constraint_type,
                name="required_capabilities",
                satisfied=False,
                message=f"capability requirements not met: {'; '.join(parts)}",
                details={"missing": missing, "disabled": disabled},
            )

        return ConstraintResult(
            constraint_type=self.constraint_type,
            name="required_capabilities",
            satisfied=True,
            message=f"all {len(required)} required capabilities are registered and enabled",
            details={"capabilities": sorted(required)},
        )


# ---------------------------------------------------------------------------
# Runtime Version Constraint
# ---------------------------------------------------------------------------

class RuntimeVersionConstraint(MissionConstraint):
    """Checks that the Python runtime meets version requirements."""

    @property
    def constraint_type(self) -> str:
        return "runtime_version"

    def evaluate(self, mission: Mission, context: dict[str, Any] | None = None) -> ConstraintResult:
        context = context or {}
        min_version = context.get("min_python_version", "3.10")
        max_version = context.get("max_python_version")

        current = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

        def _parse_version(v: str) -> tuple[int, ...]:
            return tuple(int(x) for x in v.split(".")[:3])

        current_tuple = _parse_version(current)
        min_tuple = _parse_version(min_version)

        if current_tuple < min_tuple:
            return ConstraintResult(
                constraint_type=self.constraint_type,
                name="runtime_version",
                satisfied=False,
                message=f"Python {current} is below minimum required {min_version}",
                details={"current": current, "minimum": min_version},
            )

        if max_version:
            max_tuple = _parse_version(max_version)
            if current_tuple > max_tuple:
                return ConstraintResult(
                    constraint_type=self.constraint_type,
                    name="runtime_version",
                    satisfied=False,
                    message=f"Python {current} exceeds maximum allowed {max_version}",
                    details={"current": current, "maximum": max_version},
                )

        return ConstraintResult(
            constraint_type=self.constraint_type,
            name="runtime_version",
            satisfied=True,
            message=f"Python {current} meets version requirements",
            details={"current": current, "minimum": min_version, "maximum": max_version},
        )


# ---------------------------------------------------------------------------
# Repository Constraint
# ---------------------------------------------------------------------------

class RepositoryConstraint(MissionConstraint):
    """Checks that the repository path exists and is accessible."""

    @property
    def constraint_type(self) -> str:
        return "repository"

    def evaluate(self, mission: Mission, context: dict[str, Any] | None = None) -> ConstraintResult:
        context = context or {}

        repo_ref = mission.repository
        repo_path = context.get("repository")

        if repo_ref and not repo_path:
            return ConstraintResult(
                constraint_type=self.constraint_type,
                name="repository",
                satisfied=False,
                message=f"mission references repository '{repo_ref}' but no repository path provided",
                details={"repository_ref": repo_ref},
            )

        if repo_path is None:
            if repo_ref:
                return ConstraintResult(
                    constraint_type=self.constraint_type,
                    name="repository",
                    satisfied=False,
                    message="repository path not provided",
                )
            return ConstraintResult(
                constraint_type=self.constraint_type,
                name="repository",
                satisfied=True,
                message="no repository requirement specified",
            )

        repo = Path(repo_path)
        if not repo.exists():
            return ConstraintResult(
                constraint_type=self.constraint_type,
                name="repository",
                satisfied=False,
                message=f"repository path does not exist: {repo}",
                details={"path": str(repo)},
            )

        if not repo.is_dir():
            return ConstraintResult(
                constraint_type=self.constraint_type,
                name="repository",
                satisfied=False,
                message=f"repository path is not a directory: {repo}",
                details={"path": str(repo)},
            )

        return ConstraintResult(
            constraint_type=self.constraint_type,
            name="repository",
            satisfied=True,
            message=f"repository is accessible: {repo}",
            details={"path": str(repo)},
        )


# ---------------------------------------------------------------------------
# Working Directory Constraint
# ---------------------------------------------------------------------------

class WorkingDirectoryConstraint(MissionConstraint):
    """Checks that working directories exist and are writable."""

    @property
    def constraint_type(self) -> str:
        return "working_directory"

    def evaluate(self, mission: Mission, context: dict[str, Any] | None = None) -> ConstraintResult:
        context = context or {}

        wd_ref = mission.working_directory
        wd_path = context.get("working_directory")

        if wd_path is None and not wd_ref:
            return ConstraintResult(
                constraint_type=self.constraint_type,
                name="working_directory",
                satisfied=True,
                message="no working directory requirement specified",
            )

        check_path = Path(wd_path) if wd_path else (Path(wd_ref) if wd_ref else None)
        if check_path is None:
            return ConstraintResult(
                constraint_type=self.constraint_type,
                name="working_directory",
                satisfied=True,
                message="no working directory requirement specified",
            )

        if not check_path.exists():
            return ConstraintResult(
                constraint_type=self.constraint_type,
                name="working_directory",
                satisfied=False,
                message=f"working directory does not exist: {check_path}",
                details={"path": str(check_path)},
            )

        if not os.access(check_path, os.W_OK):
            return ConstraintResult(
                constraint_type=self.constraint_type,
                name="working_directory",
                satisfied=False,
                message=f"working directory is not writable: {check_path}",
                details={"path": str(check_path)},
            )

        return ConstraintResult(
            constraint_type=self.constraint_type,
            name="working_directory",
            satisfied=True,
            message=f"working directory is accessible and writable: {check_path}",
            details={"path": str(check_path)},
        )


# ---------------------------------------------------------------------------
# Resource Limit Constraint
# ---------------------------------------------------------------------------

class ResourceLimitConstraint(MissionConstraint):
    """Checks available system resources against limits."""

    @property
    def constraint_type(self) -> str:
        return "resource_limits"

    def evaluate(self, mission: Mission, context: dict[str, Any] | None = None) -> ConstraintResult:
        context = context or {}

        min_disk_mb = context.get("min_disk_space_mb", 0)
        min_memory_mb = context.get("min_memory_mb", 0)

        issues: list[str] = []
        details: dict[str, Any] = {}

        if min_disk_mb > 0:
            work_dir = context.get("working_directory") or Path.cwd()
            try:
                usage = shutil.disk_usage(Path(work_dir))
                free_mb = usage.free / (1024 * 1024)
                details["disk_free_mb"] = round(free_mb, 1)
                if free_mb < min_disk_mb:
                    issues.append(f"insufficient disk space: {free_mb:.1f}MB free, {min_disk_mb}MB required")
            except OSError as exc:
                issues.append(f"cannot check disk space: {exc}")

        if min_memory_mb > 0:
            try:
                with open("/proc/meminfo", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.startswith("MemAvailable:"):
                            avail_kb = int(line.split()[1])
                            avail_mb = avail_kb / 1024
                            details["memory_available_mb"] = round(avail_mb, 1)
                            if avail_mb < min_memory_mb:
                                issues.append(f"insufficient memory: {avail_mb:.1f}MB available, {min_memory_mb}MB required")
                            break
            except (FileNotFoundError, ValueError, IndexError):
                details["memory_check"] = "unavailable on this platform"

        if issues:
            return ConstraintResult(
                constraint_type=self.constraint_type,
                name="resource_limits",
                satisfied=False,
                message=f"resource constraints not met: {'; '.join(issues)}",
                details=details,
            )

        return ConstraintResult(
            constraint_type=self.constraint_type,
            name="resource_limits",
            satisfied=True,
            message="resource constraints satisfied",
            details=details,
        )


# ---------------------------------------------------------------------------
# Execution Window Constraint
# ---------------------------------------------------------------------------

class ExecutionWindowConstraint(MissionConstraint):
    """Checks whether the current time falls within allowed execution windows."""

    @property
    def constraint_type(self) -> str:
        return "execution_window"

    def evaluate(self, mission: Mission, context: dict[str, Any] | None = None) -> ConstraintResult:
        context = context or {}

        window_start = context.get("window_start")
        window_end = context.get("window_end")
        excluded_days = context.get("excluded_days", [])

        now = datetime.now(timezone.utc)

        if excluded_days:
            day_name = now.strftime("%A").lower()
            if day_name in [d.lower() for d in excluded_days]:
                return ConstraintResult(
                    constraint_type=self.constraint_type,
                    name="execution_window",
                    satisfied=False,
                    message=f"execution excluded on {now.strftime('%A')}",
                    details={"current_day": now.strftime("%A"), "excluded_days": excluded_days},
                )

        if window_start:
            try:
                start = datetime.fromisoformat(window_start.replace("Z", "+00:00"))
                if now < start:
                    return ConstraintResult(
                        constraint_type=self.constraint_type,
                        name="execution_window",
                        satisfied=False,
                        message=f"execution window has not opened yet (opens at {window_start})",
                        details={"current_time": now.isoformat(), "window_start": window_start},
                    )
            except ValueError:
                return ConstraintResult(
                    constraint_type=self.constraint_type,
                    name="execution_window",
                    satisfied=False,
                    message=f"invalid window_start format: {window_start}",
                )

        if window_end:
            try:
                end = datetime.fromisoformat(window_end.replace("Z", "+00:00"))
                if now > end:
                    return ConstraintResult(
                        constraint_type=self.constraint_type,
                        name="execution_window",
                        satisfied=False,
                        message=f"execution window has closed (closed at {window_end})",
                        details={"current_time": now.isoformat(), "window_end": window_end},
                    )
            except ValueError:
                return ConstraintResult(
                    constraint_type=self.constraint_type,
                    name="execution_window",
                    satisfied=False,
                    message=f"invalid window_end format: {window_end}",
                )

        return ConstraintResult(
            constraint_type=self.constraint_type,
            name="execution_window",
            satisfied=True,
            message="current time is within execution window",
            details={"current_time": now.isoformat()},
        )


# ---------------------------------------------------------------------------
# Dependency Policy Constraint
# ---------------------------------------------------------------------------

class DependencyPolicyConstraint(MissionConstraint):
    """Checks dependency policies (no external deps, allowed registries, etc.)."""

    @property
    def constraint_type(self) -> str:
        return "dependency_policy"

    def evaluate(self, mission: Mission, context: dict[str, Any] | None = None) -> ConstraintResult:
        context = context or {}

        allow_network = context.get("allow_network", True)
        require_deterministic = context.get("require_deterministic", False)

        warnings: list[str] = []

        if not allow_network:
            for task in mission.tasks:
                cmd_str = " ".join(task.command).lower()
                if any(kw in cmd_str for kw in ("curl", "wget", "git clone", "pip install", "npm install", "apt")):
                    warnings.append(f"task '{task.title}' may require network access")

        if require_deterministic:
            for task in mission.tasks:
                cmd_str = " ".join(task.command).lower()
                if any(kw in cmd_str for kw in ("date", "rand", "uuid", "time")):
                    warnings.append(f"task '{task.title}' may produce non-deterministic results")

        if warnings:
            return ConstraintResult(
                constraint_type=self.constraint_type,
                name="dependency_policy",
                satisfied=False,
                message=f"dependency policy violations: {'; '.join(warnings)}",
                details={"violations": warnings},
            )

        return ConstraintResult(
            constraint_type=self.constraint_type,
            name="dependency_policy",
            satisfied=True,
            message="dependency policy satisfied",
        )


# ---------------------------------------------------------------------------
# Constraint Engine
# ---------------------------------------------------------------------------

class ConstraintEngine:
    """Validates missions against a set of constraints.

    Constraints can be:
    1. Mission-level (from mission.constraints strings)
    2. Type-level (from MissionType.default_constraints)
    3. Explicit (passed as constraint objects)
    """

    CONSTRAINT_MAP: dict[str, type[MissionConstraint]] = {
        "required_capabilities": RequiredCapabilityConstraint,
        "runtime_version": RuntimeVersionConstraint,
        "repository": RepositoryConstraint,
        "working_directory": WorkingDirectoryConstraint,
        "resource_limits": ResourceLimitConstraint,
        "execution_window": ExecutionWindowConstraint,
        "dependency_policy": DependencyPolicyConstraint,
    }

    def __init__(self, context: dict[str, Any] | None = None) -> None:
        self.context = context or {}
        self._constraints: list[MissionConstraint] = []

    def add_constraint(self, constraint: MissionConstraint) -> None:
        """Add a specific constraint to check."""
        self._constraints.append(constraint)

    def add_constraints_by_name(self, names: list[str]) -> None:
        """Add constraints by their type name."""
        for name in names:
            cls = self.CONSTRAINT_MAP.get(name)
            if cls:
                self._constraints.append(cls())

    def validate(self, mission: Mission) -> list[ConstraintResult]:
        """Validate all constraints against the mission."""
        results: list[ConstraintResult] = []

        for constraint in self._constraints:
            result = constraint.evaluate(mission, self.context)
            results.append(result)

        return results

    def validate_mission_constraints(self, mission: Mission) -> tuple[list[str], list[str]]:
        """Validate constraints from mission.constraints and return (errors, warnings).

        This is the primary interface for integration with MissionPlanner.
        """
        errors: list[str] = []
        warnings: list[str] = []

        constraint_names = list(mission.constraints)
        self.add_constraints_by_name(constraint_names)

        results = self.validate(mission)

        for result in results:
            if not result.satisfied:
                if result.constraint_type in ("execution_window", "dependency_policy"):
                    warnings.append(result.message)
                else:
                    errors.append(result.message)

        return errors, warnings

    def get_results_summary(self, results: list[ConstraintResult]) -> dict[str, Any]:
        """Summarize constraint results."""
        satisfied = [r for r in results if r.satisfied]
        unsatisfied = [r for r in results if not r.satisfied]
        return {
            "total": len(results),
            "satisfied": len(satisfied),
            "unsatisfied": len(unsatisfied),
            "results": [r.as_dict() for r in results],
        }


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def validate_mission_constraints(
    mission: Mission,
    context: dict[str, Any] | None = None,
) -> tuple[list[str], list[str]]:
    """Validate a mission's constraints and return (errors, warnings).

    This is the primary public API for constraint validation.
    """
    engine = ConstraintEngine(context=context)
    return engine.validate_mission_constraints(mission)
