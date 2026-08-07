"""Mission lifecycle state model and persistence.

MissionState is the authoritative observed state of a running or completed mission.
MissionControlStore handles the separate control-intent file (mission_control.json).
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .utils import utc_now_str


MISSION_STATES = ("READY", "RUNNING", "PAUSED", "CANCELLED", "ABORTED", "COMPLETED", "FAILED")
TERMINAL_MISSION_STATES = frozenset({"COMPLETED", "CANCELLED", "ABORTED", "FAILED"})

_VALID_TRANSITIONS: dict[str, set[str]] = {
    "READY": {"RUNNING"},
    "RUNNING": {"PAUSED", "CANCELLED", "ABORTED", "COMPLETED", "FAILED"},
    "PAUSED": {"RUNNING", "CANCELLED", "ABORTED"},
    "CANCELLED": set(),
    "ABORTED": set(),
    "COMPLETED": set(),
    "FAILED": set(),
}


def _validate_transition(current: str, target: str) -> None:
    if current not in _VALID_TRANSITIONS:
        raise ValueError(f"unknown current state: {current}")
    if target not in _VALID_TRANSITIONS[current]:
        raise ValueError(
            f"invalid lifecycle transition: {current} -> {target} "
            f"(allowed: {sorted(_VALID_TRANSITIONS[current]) or 'terminal'})"
        )


@dataclass(frozen=True)
class MissionState:
    """Authoritative observed state of a mission."""

    schema_version: str
    mission_id: str
    mission_title: str
    state: str
    started_at: str | None
    paused_at: str | None
    resumed_at: str | None
    cancelled_at: str | None
    aborted_at: str | None
    finished_at: str | None
    tasks_total: int
    tasks_completed: int
    tasks_failed: int
    tasks_remaining: int
    last_control_command_id: int
    pause_reason: str | None
    cancel_reason: str | None
    abort_reason: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def is_terminal(self) -> bool:
        return self.state in TERMINAL_MISSION_STATES


def create_initial_state(
    mission_id: str,
    mission_title: str,
    tasks_total: int,
) -> MissionState:
    """Create a fresh READY state for a new mission."""
    return MissionState(
        schema_version="1",
        mission_id=mission_id,
        mission_title=mission_title,
        state="READY",
        started_at=None,
        paused_at=None,
        resumed_at=None,
        cancelled_at=None,
        aborted_at=None,
        finished_at=None,
        tasks_total=tasks_total,
        tasks_completed=0,
        tasks_failed=0,
        tasks_remaining=tasks_total,
        last_control_command_id=0,
        pause_reason=None,
        cancel_reason=None,
        abort_reason=None,
    )


def transition_state(
    current: MissionState,
    target: str,
    *,
    reason: str | None = None,
    command_id: int | None = None,
) -> MissionState:
    """Return a new MissionState with the target state applied.

    Raises ValueError for invalid transitions.
    """
    _validate_transition(current.state, target)
    now = utc_now_str()
    cmd_id = command_id if command_id is not None else current.last_control_command_id

    kwargs: dict[str, Any] = {
        "state": target,
        "last_control_command_id": cmd_id,
    }

    if target == "RUNNING":
        if current.state == "READY":
            kwargs["started_at"] = now
        elif current.state == "PAUSED":
            kwargs["resumed_at"] = now
    elif target == "PAUSED":
        kwargs["paused_at"] = now
        kwargs["pause_reason"] = reason
    elif target == "CANCELLED":
        kwargs["cancelled_at"] = now
        kwargs["cancel_reason"] = reason
        kwargs["finished_at"] = now
    elif target == "ABORTED":
        kwargs["aborted_at"] = now
        kwargs["abort_reason"] = reason
        kwargs["finished_at"] = now
    elif target == "COMPLETED":
        kwargs["finished_at"] = now
        kwargs["tasks_completed"] = current.tasks_total
        kwargs["tasks_remaining"] = 0
    elif target == "FAILED":
        kwargs["finished_at"] = now

    # Apply counts from current state
    for attr in ("tasks_total", "tasks_completed", "tasks_failed", "tasks_remaining"):
        if attr not in kwargs:
            kwargs[attr] = getattr(current, attr)

    # Preserve timestamps not being set
    for attr in ("started_at", "paused_at", "resumed_at", "cancelled_at", "aborted_at", "finished_at"):
        if attr not in kwargs:
            kwargs[attr] = getattr(current, attr)

    # Preserve reasons
    for attr in ("pause_reason", "cancel_reason", "abort_reason"):
        if attr not in kwargs:
            kwargs[attr] = getattr(current, attr)

    return MissionState(
        schema_version=current.schema_version,
        mission_id=current.mission_id,
        mission_title=current.mission_title,
        **kwargs,
    )


def update_counts(
    state: MissionState,
    *,
    tasks_completed: int | None = None,
    tasks_failed: int | None = None,
) -> MissionState:
    """Return a new state with updated task counts."""
    completed = tasks_completed if tasks_completed is not None else state.tasks_completed
    failed = tasks_failed if tasks_failed is not None else state.tasks_failed
    remaining = state.tasks_total - completed - failed

    return MissionState(
        schema_version=state.schema_version,
        mission_id=state.mission_id,
        mission_title=state.mission_title,
        state=state.state,
        started_at=state.started_at,
        paused_at=state.paused_at,
        resumed_at=state.resumed_at,
        cancelled_at=state.cancelled_at,
        aborted_at=state.aborted_at,
        finished_at=state.finished_at,
        tasks_total=state.tasks_total,
        tasks_completed=completed,
        tasks_failed=failed,
        tasks_remaining=max(0, remaining),
        last_control_command_id=state.last_control_command_id,
        pause_reason=state.pause_reason,
        cancel_reason=state.cancel_reason,
        abort_reason=state.abort_reason,
    )


class MissionStateStore:
    """Atomically persists the authoritative mission state."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> MissionState | None:
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return MissionState(**data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def save(self, state: MissionState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(state.as_dict(), indent=2, sort_keys=True) + "\n"
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=str(self.path.parent),
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
