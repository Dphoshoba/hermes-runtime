"""Mission Planner — transforms high-level missions into validated WorkItem tasks.

The planner owns intent and task generation only. It does not execute,
dispatch, or modify runtime state. Execution remains the queue's responsibility.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .work_queue import WorkItem, WorkQueueManager, WorkQueueStateStore


MISSION_SCHEMA_VERSION = "1"
PLAN_SCHEMA_VERSION = "1"


# ---------------------------------------------------------------------------
# Mission data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    max_retry_delay_seconds: float = 60.0
    retry_backoff_multiplier: float = 2.0
    retryable: bool = True

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if self.retry_delay_seconds <= 0:
            raise ValueError("retry_delay_seconds must be > 0")
        if self.max_retry_delay_seconds < self.retry_delay_seconds:
            raise ValueError("max_retry_delay_seconds must be >= retry_delay_seconds")
        if self.retry_backoff_multiplier <= 1.0:
            raise ValueError("retry_backoff_multiplier must be > 1.0")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MissionTask:
    title: str
    command: list[str]
    task_id: str | None = None
    dependencies: tuple[str, ...] = ()
    priority: int = 100
    retry_policy: RetryPolicy | None = None
    required_capabilities: tuple[str, ...] = ()
    working_directory: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("task title must not be empty")
        if not self.command:
            raise ValueError("task command must not be empty")
        if self.task_id is not None and not self.task_id.strip():
            raise ValueError("task_id must not be empty if provided")

    def as_dict(self) -> dict[str, Any]:
        data = {
            "title": self.title,
            "command": self.command,
            "dependencies": list(self.dependencies),
            "priority": self.priority,
            "required_capabilities": list(self.required_capabilities),
            "metadata": self.metadata,
        }
        if self.task_id is not None:
            data["task_id"] = self.task_id
        if self.retry_policy is not None:
            data["retry_policy"] = self.retry_policy.as_dict()
        if self.working_directory is not None:
            data["working_directory"] = self.working_directory
        return data


@dataclass(frozen=True)
class Mission:
    mission_id: str
    title: str
    description: str
    tasks: tuple[MissionTask, ...]
    goals: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    default_retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    working_directory: str | None = None
    repository: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.mission_id.strip():
            raise ValueError("mission_id must not be empty")
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if not self.tasks:
            raise ValueError("mission must have at least one task")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": MISSION_SCHEMA_VERSION,
            "mission_id": self.mission_id,
            "title": self.title,
            "description": self.description,
            "goals": list(self.goals),
            "constraints": list(self.constraints),
            "tasks": [t.as_dict() for t in self.tasks],
            "required_capabilities": list(self.required_capabilities),
            "default_retry_policy": self.default_retry_policy.as_dict(),
            "working_directory": self.working_directory,
            "repository": self.repository,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Plan artifact
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PlanTask:
    task_id: str
    title: str
    command: list[str]
    dependencies: tuple[str, ...]
    priority: int
    retry_policy: RetryPolicy
    required_capabilities: tuple[str, ...]
    working_directory: str | None
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "command": self.command,
            "dependencies": list(self.dependencies),
            "priority": self.priority,
            "retry_policy": self.retry_policy.as_dict(),
            "required_capabilities": list(self.required_capabilities),
            "working_directory": self.working_directory,
            "metadata": self.metadata,
        }

    def to_work_item(self) -> WorkItem:
        return WorkItem(
            task_id=self.task_id,
            title=self.title,
            priority=self.priority,
            dependencies=self.dependencies,
            max_retries=self.retry_policy.max_retries,
            retry_delay_seconds=self.retry_policy.retry_delay_seconds,
            max_retry_delay_seconds=self.retry_policy.max_retry_delay_seconds,
            retry_backoff_multiplier=self.retry_policy.retry_backoff_multiplier,
            retryable=self.retry_policy.retryable,
        )


@dataclass(frozen=True)
class Plan:
    schema_version: str
    mission_id: str
    mission_title: str
    mission_description: str
    generated_at: str
    plan_hash: str
    tasks: tuple[PlanTask, ...]
    dependency_graph: dict[str, list[str]]
    required_capabilities: tuple[str, ...]
    working_directory: str | None
    repository: str | None
    warnings: tuple[str, ...]
    valid: bool
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "mission_id": self.mission_id,
            "mission_title": self.mission_title,
            "mission_description": self.mission_description,
            "generated_at": self.generated_at,
            "plan_hash": self.plan_hash,
            "tasks": [t.as_dict() for t in self.tasks],
            "dependency_graph": self.dependency_graph,
            "required_capabilities": list(self.required_capabilities),
            "working_directory": self.working_directory,
            "repository": self.repository,
            "warnings": list(self.warnings),
            "valid": self.valid,
            "errors": list(self.errors),
        }


# ---------------------------------------------------------------------------
# Mission loader
# ---------------------------------------------------------------------------

def load_mission(path: Path) -> Mission:
    """Load and parse a mission definition from a JSON file."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return parse_mission(raw)


def parse_mission(data: dict[str, Any]) -> Mission:
    """Parse a mission from a raw dictionary."""
    default_retry = RetryPolicy(**data.get("default_retry_policy", {}))

    tasks: list[MissionTask] = []
    for t in data.get("tasks", []):
        retry_raw = t.get("retry_policy")
        retry_policy = RetryPolicy(**retry_raw) if retry_raw else None
        tasks.append(MissionTask(
            task_id=t.get("task_id"),
            title=t["title"],
            command=t["command"],
            dependencies=tuple(t.get("dependencies", ())),
            priority=t.get("priority", 100),
            retry_policy=retry_policy,
            required_capabilities=tuple(t.get("required_capabilities", ())),
            working_directory=t.get("working_directory"),
            metadata=t.get("metadata", {}),
        ))

    return Mission(
        mission_id=data["mission_id"],
        title=data["title"],
        description=data.get("description", ""),
        goals=tuple(data.get("goals", ())),
        constraints=tuple(data.get("constraints", ())),
        tasks=tuple(tasks),
        required_capabilities=tuple(data.get("required_capabilities", ())),
        default_retry_policy=default_retry,
        working_directory=data.get("working_directory"),
        repository=data.get("repository"),
        metadata=data.get("metadata", {}),
    )


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

class MissionPlanner:
    """Transforms a mission into a validated, deterministic plan."""

    def validate(self, mission: Mission) -> tuple[list[str], list[str]]:
        """Validate a mission. Returns (errors, warnings)."""
        errors: list[str] = []
        warnings: list[str] = []

        task_ids: list[str] = []
        for i, task in enumerate(mission.tasks):
            tid = task.task_id or _generated_task_id(mission.mission_id, i)
            if tid in task_ids:
                errors.append(f"Duplicate task ID: {tid}")
            task_ids.append(tid)

        known_ids = set(task_ids)
        for task in mission.tasks:
            tid = task.task_id or _generated_task_id(mission.mission_id, mission.tasks.index(task))
            for dep in task.dependencies:
                if dep not in known_ids:
                    errors.append(f"Task {tid} depends on unknown task: {dep}")

        if _has_cycle(mission):
            errors.append("Dependency cycle detected")

        for task in mission.tasks:
            if task.priority < 0:
                errors.append(f"Task {task.task_id or task.title} has negative priority")
            if task.retry_policy is not None:
                try:
                    task.retry_policy.__post_init__()
                except ValueError as e:
                    errors.append(f"Task {task.task_id or task.title} has invalid retry policy: {e}")

        return errors, warnings

    def validate_recommendation(
        self,
        mission: Mission,
    ) -> tuple[list[str], list[str]]:
        """Validate that a mission is eligible for planning as a recommendation.

        Checks:
        - Mission metadata must indicate recommendation_generated
        - Mission metadata must have traceability
        - Mission metadata must have governance_approval_reference
        - Mission state must not be DRAFT or REJECTED
        """
        errors: list[str] = []
        warnings: list[str] = []
        meta = mission.metadata

        if not meta.get("recommendation_generated"):
            errors.append(f"Mission {mission.mission_id} is not a recommendation artifact")
            return errors, warnings

        if not meta.get("traceability"):
            errors.append(f"Mission {mission.mission_id} is missing governance traceability")

        if not meta.get("governance_approval_reference"):
            errors.append(f"Mission {mission.mission_id} is missing governance approval reference")

        state = meta.get("recommendation_state", "")
        if state == "DRAFT":
            errors.append(f"Mission {mission.mission_id} is in DRAFT state; must be APPROVED")
        elif state == "REJECTED":
            errors.append(f"Mission {mission.mission_id} is in REJECTED state; cannot plan")

        return errors, warnings

    def build(
        self,
        mission: Mission,
        capability_registry: Any | None = None,
        constraint_context: dict[str, Any] | None = None,
    ) -> Plan:
        """Build a plan from a mission.

        Validates capabilities if registry provided.
        Validates constraints if constraint_context provided or mission has constraints.
        """
        errors, warnings = self.validate(mission)

        # If this is a recommendation artifact, validate eligibility
        if mission.metadata.get("recommendation_generated"):
            rec_errors, rec_warnings = self.validate_recommendation(mission)
            errors.extend(rec_errors)
            warnings.extend(rec_warnings)

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Check capabilities
        all_caps: set[str] = set(mission.required_capabilities)
        for task in mission.tasks:
            all_caps.update(task.required_capabilities)

        if capability_registry is not None:
            for cap_name in sorted(all_caps):
                try:
                    state = capability_registry.get(cap_name)
                    if not state.metadata.enabled:
                        errors.append(f"Required capability is disabled: {cap_name}")
                except KeyError:
                    errors.append(f"Required capability not found: {cap_name}")

        # Validate constraints
        if mission.constraints or constraint_context:
            from .mission_constraints import validate_mission_constraints
            ctx = dict(constraint_context or {})
            if capability_registry is not None:
                ctx.setdefault("capability_registry", capability_registry)
            if mission.working_directory:
                ctx.setdefault("working_directory", Path(mission.working_directory))
            if mission.repository:
                ctx.setdefault("repository", Path(mission.repository))
            constraint_errors, constraint_warnings = validate_mission_constraints(mission, ctx)
            errors.extend(constraint_errors)
            warnings.extend(constraint_warnings)

        # Build tasks
        plan_tasks: list[PlanTask] = []
        dep_graph: dict[str, list[str]] = {}
        task_id_map: dict[str, str] = {}  # index -> assigned id

        for i, task in enumerate(mission.tasks):
            tid = task.task_id or _generated_task_id(mission.mission_id, i)
            task_id_map[i] = tid

            effective_retry = task.retry_policy or mission.default_retry_policy
            dep_graph[tid] = list(task.dependencies)

            plan_tasks.append(PlanTask(
                task_id=tid,
                title=task.title,
                command=task.command,
                dependencies=task.dependencies,
                priority=task.priority,
                retry_policy=effective_retry,
                required_capabilities=task.required_capabilities,
                working_directory=task.working_directory or mission.working_directory,
                metadata=task.metadata,
            ))

        # Compute plan hash (deterministic from tasks only)
        plan_content = json.dumps(
            {"tasks": [t.as_dict() for t in plan_tasks]},
            sort_keys=True,
            indent=2,
        )
        plan_hash = hashlib.sha256(plan_content.encode("utf-8")).hexdigest()

        return Plan(
            schema_version=PLAN_SCHEMA_VERSION,
            mission_id=mission.mission_id,
            mission_title=mission.title,
            mission_description=mission.description,
            generated_at=now,
            plan_hash=plan_hash,
            tasks=tuple(plan_tasks),
            dependency_graph=dep_graph,
            required_capabilities=tuple(sorted(all_caps)),
            working_directory=mission.working_directory,
            repository=mission.repository,
            warnings=tuple(warnings),
            valid=len(errors) == 0,
            errors=tuple(errors),
        )


# ---------------------------------------------------------------------------
# Enqueue
# ---------------------------------------------------------------------------

def enqueue_plan(
    plan: Plan,
    queue_path: Path,
) -> list[str]:
    """Convert a validated plan into WorkItems and enqueue them.

    Returns list of enqueued task IDs.
    Raises ValueError if plan is invalid or queue already contains tasks from this plan.
    """
    if not plan.valid:
        raise ValueError(f"Cannot enqueue invalid plan: {plan.errors}")

    store = WorkQueueStateStore(queue_path)
    mgr = WorkQueueManager(state_store=store)

    existing_ids = {item.task_id for item in mgr.items()}
    enqueued: list[str] = []

    for plan_task in plan.tasks:
        if plan_task.task_id in existing_ids:
            raise ValueError(f"Task already exists in queue: {plan_task.task_id}")

    for plan_task in plan.tasks:
        work_item = plan_task.to_work_item()
        # Use WorkQueueManager's internal state manipulation
        # We add to the state directly, then persist via normalize
        mgr._state = type(mgr._state)(
            schema_version=mgr._state.schema_version,
            revision=mgr._state.revision,
            items=mgr._state.items + (work_item,),
        )
        enqueued.append(plan_task.task_id)

    # Validate and persist the final state
    from .work_queue import WorkQueueState
    normalized = mgr._normalize(mgr._state)
    mgr._persist(normalized)

    return enqueued


# ---------------------------------------------------------------------------
# Plan persistence
# ---------------------------------------------------------------------------

def save_plan(plan: Plan, path: Path) -> None:
    """Save a plan artifact to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(plan.as_dict(), indent=2, sort_keys=True) + "\n"
    path.write_text(payload, encoding="utf-8")


def load_plan(path: Path) -> Plan:
    """Load a plan artifact from a JSON file."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    tasks = tuple(
        PlanTask(
            task_id=t["task_id"],
            title=t["title"],
            command=t["command"],
            dependencies=tuple(t["dependencies"]),
            priority=t["priority"],
            retry_policy=RetryPolicy(**t["retry_policy"]),
            required_capabilities=tuple(t["required_capabilities"]),
            working_directory=t.get("working_directory"),
            metadata=t.get("metadata", {}),
        )
        for t in raw["tasks"]
    )
    return Plan(
        schema_version=raw["schema_version"],
        mission_id=raw["mission_id"],
        mission_title=raw["mission_title"],
        mission_description=raw["mission_description"],
        generated_at=raw["generated_at"],
        plan_hash=raw["plan_hash"],
        tasks=tasks,
        dependency_graph=raw["dependency_graph"],
        required_capabilities=tuple(raw["required_capabilities"]),
        working_directory=raw.get("working_directory"),
        repository=raw.get("repository"),
        warnings=tuple(raw["warnings"]),
        valid=raw["valid"],
        errors=tuple(raw["errors"]),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generated_task_id(mission_id: str, index: int) -> str:
    """Generate a deterministic task ID from mission_id and index."""
    return f"{mission_id}-task-{index:04d}"


def _has_cycle(mission: Mission) -> bool:
    """Check if the mission's dependency graph has a cycle."""
    task_ids = set()
    for task in mission.tasks:
        tid = task.task_id or _generated_task_id(mission.mission_id, mission.tasks.index(task))
        task_ids.add(tid)

    deps: dict[str, list[str]] = {}
    for task in mission.tasks:
        tid = task.task_id or _generated_task_id(mission.mission_id, mission.tasks.index(task))
        deps[tid] = [d for d in task.dependencies if d in task_ids]

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(tid: str) -> bool:
        if tid in visited:
            return False
        if tid in visiting:
            return True
        visiting.add(tid)
        for dep in deps.get(tid, []):
            if visit(dep):
                return True
        visiting.discard(tid)
        visited.add(tid)
        return False

    return any(visit(tid) for tid in deps)
