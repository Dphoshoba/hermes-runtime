from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_v01.work_queue import WorkItem, WorkQueueManager, WorkQueueStateStore


def manager(tmp_path: Path) -> WorkQueueManager:
    return WorkQueueManager(
        state_store=WorkQueueStateStore(tmp_path / "work-queue.json"),
        items=(
            WorkItem("supervisor", "Supervisor", priority=10),
            WorkItem("runtime-state", "Runtime State Manager", priority=20, dependencies=("supervisor",)),
            WorkItem("work-queue", "Work Queue Manager", priority=30, dependencies=("runtime-state",)),
            WorkItem("evidence", "Evidence Recorder", priority=40, dependencies=("work-queue",)),
        ),
    )


def verify_and_complete(queue: WorkQueueManager, task_id: str) -> None:
    queue.dispatch_next()
    queue.mark_observed(task_id)
    queue.mark_verification_pending(task_id)
    queue.record_independent_verification(task_id)
    queue.mark_complete(task_id)


def test_initial_states_are_dependency_derived(tmp_path: Path) -> None:
    queue = manager(tmp_path)

    assert queue.summary()["READY"] == ["supervisor"]
    assert queue.summary()["BLOCKED"] == ["runtime-state", "work-queue", "evidence"]


def test_deterministic_priority_then_task_id_ordering(tmp_path: Path) -> None:
    queue = WorkQueueManager(
        state_store=WorkQueueStateStore(tmp_path / "queue.json"),
        items=(
            WorkItem("z-task", "Z", priority=1),
            WorkItem("a-task", "A", priority=1),
            WorkItem("later", "Later", priority=2),
        ),
    )

    assert queue.next_ready().task_id == "a-task"


def test_dependency_completion_unblocks_next_task(tmp_path: Path) -> None:
    queue = manager(tmp_path)
    verify_and_complete(queue, "supervisor")

    assert queue.get("runtime-state").state == "READY"
    assert queue.get("work-queue").state == "BLOCKED"


def test_duplicate_dispatch_is_prevented(tmp_path: Path) -> None:
    queue = manager(tmp_path)
    dispatched = queue.dispatch_next()

    assert dispatched is not None
    assert dispatched.state == "RUNNING"
    assert dispatched.attempts == 1
    assert queue.dispatch_next() is None
    with pytest.raises(ValueError, match="already running"):
        queue.transition("supervisor", "RUNNING", increment_attempts=True)


def test_completed_work_cannot_be_replayed(tmp_path: Path) -> None:
    queue = manager(tmp_path)
    verify_and_complete(queue, "supervisor")

    with pytest.raises(ValueError, match="cannot move terminal task"):
        queue.transition("supervisor", "READY")


def test_independent_verification_boundary_is_enforced(tmp_path: Path) -> None:
    queue = manager(tmp_path)
    queue.dispatch_next()
    queue.mark_observed("supervisor")

    with pytest.raises(ValueError, match="requires VERIFICATION_PENDING"):
        queue.record_independent_verification("supervisor")

    queue.mark_verification_pending("supervisor")
    assert queue.record_independent_verification("supervisor").state == "VERIFIED"


def test_state_is_persisted_atomically_and_restored(tmp_path: Path) -> None:
    path = tmp_path / "work-queue.json"
    queue = manager(tmp_path)
    queue.dispatch_next()
    queue.mark_observed("supervisor")

    restored = WorkQueueManager(state_store=WorkQueueStateStore(path))

    assert restored.get("supervisor").state == "OBSERVED"
    assert restored.state.revision == queue.state.revision
    assert not list(tmp_path.glob("*.tmp"))
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1"


def test_corrupted_state_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "queue.json"
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid work queue state"):
        WorkQueueManager(state_store=WorkQueueStateStore(path))


def test_unknown_dependency_and_cycle_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown dependencies"):
        WorkQueueManager(
            state_store=WorkQueueStateStore(tmp_path / "unknown.json"),
            items=(WorkItem("a", "A", dependencies=("missing",)),),
        )

    with pytest.raises(ValueError, match="cyclic"):
        WorkQueueManager(
            state_store=WorkQueueStateStore(tmp_path / "cycle.json"),
            items=(
                WorkItem("a", "A", dependencies=("b",)),
                WorkItem("b", "B", dependencies=("a",)),
            ),
        )
