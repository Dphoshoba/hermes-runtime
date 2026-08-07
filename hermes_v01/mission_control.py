"""Mission lifecycle control-intent persistence.

mission_control.json holds the *requested* lifecycle action, separate from
the observed state in mission_state.json.  The running MissionRunner is the
only authority for state transitions.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .utils import utc_now_str


CONTROL_ACTIONS = ("pause", "resume", "cancel", "abort")


@dataclass(frozen=True)
class MissionControlCommand:
    """A requested lifecycle action written by the CLI."""

    schema_version: str
    mission_id: str
    command_id: int
    action: str
    reason: str | None
    requested_at: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def __post_init__(self) -> None:
        if self.action not in CONTROL_ACTIONS:
            raise ValueError(f"unknown control action: {self.action!r} (valid: {CONTROL_ACTIONS})")
        if self.command_id < 0:
            raise ValueError("command_id must be >= 0")


class MissionControlStore:
    """Atomic read/write for the mission control file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> MissionControlCommand | None:
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return MissionControlCommand(**data)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None

    def save(self, command: MissionControlCommand) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(command.as_dict(), indent=2, sort_keys=True) + "\n"
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

    def next_command_id(self, current_state_last_id: int) -> int:
        existing = self.load()
        if existing is None:
            return current_state_last_id + 1
        return max(existing.command_id, current_state_last_id) + 1

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()


def write_control_command(
    store: MissionControlStore,
    mission_id: str,
    action: str,
    last_control_command_id: int,
    reason: str | None = None,
) -> MissionControlCommand:
    """Write a new control command atomically.

    Returns the created command.
    """
    cmd_id = store.next_command_id(last_control_command_id)
    command = MissionControlCommand(
        schema_version="1",
        mission_id=mission_id,
        command_id=cmd_id,
        action=action,
        reason=reason,
        requested_at=utc_now_str(),
    )
    store.save(command)
    return command
