from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .supervisor import AtomicJsonStateStore, SupervisorState
from .utils import atomic_write_json
from .work_queue import WorkQueueManager


@dataclass(frozen=True)
class RuntimeState:
    """Canonical, read-only view of the EVOSIA runtime's current state."""

    schema_version: str
    program: str
    phase: str
    repository: str
    output_dir: str
    supervisor_status: str
    cycle_count: int
    last_exit_code: int | None
    last_mission_status: str | None
    stop_reason: str | None
    current_milestone: str | None
    next_action: str
    blockers: tuple[str, ...]
    work_queue: dict[str, list[str]] | None = None

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["blockers"] = list(self.blockers)
        return data


class RuntimeStateStore:
    """Atomically persists the canonical runtime-state projection."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> RuntimeState | None:
        if not self.path.exists():
            return None
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data["blockers"] = tuple(data.get("blockers", ()))
        return RuntimeState(**data)

    def save(self, state: RuntimeState) -> None:
        atomic_write_json(self.path, state.as_dict())


def project_runtime_state(
    supervisor: SupervisorState,
    *,
    current_milestone: str | None = None,
    work_queue: WorkQueueManager | None = None,
) -> RuntimeState:
    blockers: list[str] = []

    repository = Path(supervisor.repository)
    if not repository.exists() or not repository.is_dir():
        blockers.append("REPOSITORY_UNAVAILABLE")

    if supervisor.last_exit_code not in (None, 0):
        blockers.append("LAST_VALIDATION_FAILED")

    if blockers:
        phase = "BLOCKED"
        next_action = "Resolve blockers and resume the supervisor."
    elif supervisor.status in {"STARTING", "RUNNING"}:
        phase = "EXECUTING"
        next_action = "Allow the active validation cycle to complete."
    elif supervisor.status == "QUIESCENT":
        phase = "QUIESCENT"
        next_action = "Wait for the next scheduled cycle."
    elif supervisor.status == "STOPPED":
        phase = "SUSPENDED"
        next_action = "Restart the supervisor when continued observation is required."
    else:
        phase = "UNKNOWN"
        next_action = "Inspect supervisor state."

    work_queue_summary = work_queue.summary() if work_queue is not None else None

    return RuntimeState(
        schema_version="1",
        program="PROGRAM_III",
        phase=phase,
        repository=supervisor.repository,
        output_dir=supervisor.output_dir,
        supervisor_status=supervisor.status,
        cycle_count=supervisor.cycle_count,
        last_exit_code=supervisor.last_exit_code,
        last_mission_status=supervisor.last_mission_status,
        stop_reason=supervisor.stop_reason,
        current_milestone=current_milestone,
        next_action=next_action,
        blockers=tuple(blockers),
        work_queue=work_queue_summary,
    )


def load_projected_state(
    supervisor_state_path: Path,
    *,
    current_milestone: str | None = None,
    work_queue: WorkQueueManager | None = None,
) -> RuntimeState:
    supervisor = AtomicJsonStateStore(supervisor_state_path).load()
    if supervisor is None:
        raise FileNotFoundError(f"Supervisor state not found: {supervisor_state_path}")
    return project_runtime_state(
        supervisor,
        current_milestone=current_milestone,
        work_queue=work_queue,
    )
