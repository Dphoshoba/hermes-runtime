from __future__ import annotations

import json
from pathlib import Path

import pytest

from evosia.runtime_state import (
    RuntimeStateStore,
    load_projected_state,
    project_runtime_state,
)
from evosia.supervisor import AtomicJsonStateStore, SupervisorState
from evosia.work_queue import WorkItem, WorkQueueManager, WorkQueueStateStore


def supervisor_state(tmp_path: Path, **overrides: object) -> SupervisorState:
    base = dict(
        schema_version="1",
        status="QUIESCENT",
        repository=str(tmp_path / "repo"),
        output_dir=str(tmp_path / "out"),
        cycle_count=3,
        last_cycle_started_at_utc="2026-01-01T00:00:00+00:00",
        last_cycle_finished_at_utc="2026-01-01T00:00:01+00:00",
        last_exit_code=0,
        last_mission_status="Observation Complete",
        stop_reason=None,
    )
    base.update(overrides)
    return SupervisorState(**base)


def _make_queue(tmp_path: Path, items: tuple[WorkItem, ...] = ()) -> WorkQueueManager:
    return WorkQueueManager(state_store=WorkQueueStateStore(tmp_path / "queue.json"), items=items)


def test_projection_reports_quiescent_state(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    state = project_runtime_state(supervisor_state(tmp_path), current_milestone="Runtime State Manager")

    assert state.program == "PROGRAM_III"
    assert state.phase == "QUIESCENT"
    assert state.current_milestone == "Runtime State Manager"
    assert state.blockers == ()
    assert state.next_action == "Wait for the next scheduled cycle."


def test_projection_reports_repository_blocker(tmp_path: Path) -> None:
    state = project_runtime_state(supervisor_state(tmp_path))

    assert state.phase == "BLOCKED"
    assert state.blockers == ("REPOSITORY_UNAVAILABLE",)


def test_projection_reports_failed_validation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    state = project_runtime_state(supervisor_state(tmp_path, last_exit_code=2))

    assert state.phase == "BLOCKED"
    assert state.blockers == ("LAST_VALIDATION_FAILED",)


def test_runtime_state_store_round_trip(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    expected = project_runtime_state(supervisor_state(tmp_path))
    store = RuntimeStateStore(tmp_path / "runtime-state.json")

    store.save(expected)

    assert store.load() == expected
    data = json.loads((tmp_path / "runtime-state.json").read_text(encoding="utf-8"))
    assert data["blockers"] == []
    assert not list(tmp_path.glob("*.tmp"))


def test_load_projected_state_uses_supervisor_state(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    path = tmp_path / "supervisor-state.json"
    AtomicJsonStateStore(path).save(supervisor_state(tmp_path, status="STOPPED", stop_reason="MAX_CYCLES"))

    state = load_projected_state(path, current_milestone="Supervisor")

    assert state.phase == "SUSPENDED"
    assert state.stop_reason == "MAX_CYCLES"
    assert state.current_milestone == "Supervisor"


def test_load_projected_state_requires_supervisor_state(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_projected_state(tmp_path / "missing.json")


def test_projection_populates_work_queue_summary(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    queue = _make_queue(tmp_path, items=(
        WorkItem("task-1", "Task One", priority=10),
        WorkItem("task-2", "Task Two", priority=20, dependencies=("task-1",)),
    ))
    state = project_runtime_state(supervisor_state(tmp_path), work_queue=queue)

    assert state.work_queue is not None
    assert "READY" in state.work_queue
    assert state.work_queue["READY"] == ["task-1"]
    assert state.work_queue["BLOCKED"] == ["task-2"]


def test_projection_with_empty_queue(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    queue = _make_queue(tmp_path)
    state = project_runtime_state(supervisor_state(tmp_path), work_queue=queue)

    assert state.work_queue is not None
    for status_list in state.work_queue.values():
        assert status_list == []


def test_projection_without_queue_returns_none(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    state = project_runtime_state(supervisor_state(tmp_path), work_queue=None)

    assert state.work_queue is None


def test_load_projected_state_with_queue(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    path = tmp_path / "supervisor-state.json"
    AtomicJsonStateStore(path).save(supervisor_state(tmp_path))
    queue = _make_queue(tmp_path, items=(WorkItem("task-1", "Task One"),))

    state = load_projected_state(path, work_queue=queue)

    assert state.work_queue is not None
    assert state.work_queue["READY"] == ["task-1"]
