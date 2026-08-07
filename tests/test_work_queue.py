from __future__ import annotations

import json
from dataclasses import replace
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


def test_work_item_retry_fields_defaults(tmp_path: Path) -> None:
    item = WorkItem("test", "Test Task")
    assert item.max_retries == 3
    assert item.retry_delay_seconds == 1.0
    assert item.max_retry_delay_seconds == 60.0
    assert item.retry_backoff_multiplier == 2.0
    assert item.retryable is True
    assert item.can_retry() is True


def test_work_item_retry_fields_custom(tmp_path: Path) -> None:
    item = WorkItem("test", "Test Task", max_retries=5, retry_delay_seconds=2.0,
                     max_retry_delay_seconds=120.0, retry_backoff_multiplier=3.0,
                     retryable=False)
    assert item.max_retries == 5
    assert item.retry_delay_seconds == 2.0
    assert item.max_retry_delay_seconds == 120.0
    assert item.retry_backoff_multiplier == 3.0
    assert item.retryable is False
    assert item.can_retry() is False


def test_work_item_next_retry_delay_exponential_backoff(tmp_path: Path) -> None:
    item = WorkItem("test", "Test Task", retry_delay_seconds=1.0,
                     max_retry_delay_seconds=60.0, retry_backoff_multiplier=2.0)
    # attempts=0 -> delay=1.0
    assert item.next_retry_delay() == 1.0
    # attempts=1 -> delay=2.0
    item2 = replace(item, attempts=1)
    assert item2.next_retry_delay() == 2.0
    # attempts=2 -> delay=4.0
    item3 = replace(item, attempts=2)
    assert item3.next_retry_delay() == 4.0
    # capped at max_retry_delay_seconds
    item4 = replace(item, attempts=10)
    assert item4.next_retry_delay() == 60.0


def test_work_item_can_retry_logic(tmp_path: Path) -> None:
    item = WorkItem("test", "Test Task", max_retries=2, retryable=True)
    assert item.can_retry() is True
    item2 = replace(item, attempts=1)
    assert item2.can_retry() is True
    item3 = replace(item, attempts=2)
    assert item3.can_retry() is False  # max retries reached
    item4 = replace(item, attempts=0, retryable=False)
    assert item4.can_retry() is False  # not retryable


def test_mark_failed_schedules_retry_when_retryable(tmp_path: Path) -> None:
    queue = WorkQueueManager(
        state_store=WorkQueueStateStore(tmp_path / "queue.json"),
        items=(WorkItem("task-1", "Task 1", max_retries=3, retryable=True),),
    )
    queue.dispatch_next()  # RUNNING
    queue.mark_observed("task-1")
    queue.mark_verification_pending("task-1")
    
    # Mark as failed - should schedule retry (back to READY)
    failed = queue.mark_failed("task-1", "execution error")
    assert failed.state == "READY"
    assert failed.last_error == "execution error"
    assert failed.attempts == 1  # attempt was incremented during dispatch


def test_mark_failed_no_retry_when_exhausted(tmp_path: Path) -> None:
    queue = WorkQueueManager(
        state_store=WorkQueueStateStore(tmp_path / "queue.json"),
        items=(WorkItem("task-1", "Task 1", max_retries=2, retryable=True),),
    )
    queue.dispatch_next()  # RUNNING, attempts=1
    queue.mark_observed("task-1")
    queue.mark_verification_pending("task-1")
    
    # First failure - should retry (attempts=1 < max_retries=2)
    failed1 = queue.mark_failed("task-1", "error 1")
    assert failed1.state == "READY"
    assert failed1.attempts == 1
    
    # Second attempt
    queue.dispatch_next()  # RUNNING, attempts=2
    queue.mark_observed("task-1")
    queue.mark_verification_pending("task-1")
    
    # Second failure - max retries exhausted (attempts=2 == max_retries=2)
    failed2 = queue.mark_failed("task-1", "error 2")
    assert failed2.state == "VERIFICATION_PENDING"  # stays in current state
    assert failed2.last_error == "error 2"
    assert failed2.attempts == 2


def test_mark_failed_non_retryable_stays_in_state(tmp_path: Path) -> None:
    queue = WorkQueueManager(
        state_store=WorkQueueStateStore(tmp_path / "queue.json"),
        items=(WorkItem("task-1", "Task 1", max_retries=3, retryable=False),),
    )
    queue.dispatch_next()
    queue.mark_observed("task-1")
    
    failed = queue.mark_failed("task-1", "fatal error")
    assert failed.state == "OBSERVED"  # stays in current state
    assert failed.last_error == "fatal error"


def test_retry_task_manual_retry(tmp_path: Path) -> None:
    queue = WorkQueueManager(
        state_store=WorkQueueStateStore(tmp_path / "queue.json"),
        items=(WorkItem("task-1", "Task 1", max_retries=3, retryable=True),),
    )
    queue.dispatch_next()
    queue.mark_observed("task-1")
    queue.mark_verification_pending("task-1")
    queue.mark_failed("task-1", "error")  # back to READY
    
    # Manual retry
    retried = queue.retry_task("task-1")
    assert retried.state == "READY"
    assert retried.attempts == 2  # incremented


def test_retry_task_rejects_when_exhausted(tmp_path: Path) -> None:
    queue = WorkQueueManager(
        state_store=WorkQueueStateStore(tmp_path / "queue.json"),
        items=(WorkItem("task-1", "Task 1", max_retries=1, retryable=True),),
    )
    queue.dispatch_next()
    queue.mark_observed("task-1")
    queue.mark_verification_pending("task-1")
    queue.mark_failed("task-1", "error")  # back to READY
    queue.dispatch_next()  # attempts=2
    queue.mark_observed("task-1")
    queue.mark_verification_pending("task-1")
    queue.mark_failed("task-1", "error 2")  # exhausted
    
    with pytest.raises(ValueError, match="cannot be retried"):
        queue.retry_task("task-1")


def test_recover_incomplete_tasks_after_crash(tmp_path: Path) -> None:
    # Simulate a queue with tasks in progress
    queue = WorkQueueManager(
        state_store=WorkQueueStateStore(tmp_path / "queue.json"),
        items=(
            WorkItem("running-task", "Running Task", max_retries=3, retryable=True),
            WorkItem("observed-task", "Observed Task", max_retries=3, retryable=True),
            WorkItem("pending-task", "Pending Task", max_retries=3, retryable=True),
            WorkItem("complete-task", "Complete Task", max_retries=3, retryable=True),
        ),
    )
    # Manually set states to simulate crash mid-execution
    from hermes_v01.work_queue import WorkQueueState
    items = list(queue.state.items)
    items[0] = replace(items[0], state="RUNNING", attempts=1)
    items[1] = replace(items[1], state="OBSERVED", attempts=1)
    items[2] = replace(items[2], state="VERIFICATION_PENDING", attempts=1)
    items[3] = replace(items[3], state="COMPLETE", attempts=1)
    new_state = WorkQueueState(schema_version="1", revision=1, items=tuple(items))
    queue._persist(new_state)
    
    # Now recover
    recovered = queue.recover_incomplete_tasks()
    
    assert len(recovered) == 3
    assert queue.get("running-task").state == "READY"
    assert queue.get("running-task").attempts == 2
    assert queue.get("observed-task").state == "READY"
    assert queue.get("observed-task").attempts == 2
    assert queue.get("pending-task").state == "READY"
    assert queue.get("pending-task").attempts == 2
    # Complete task should not be recovered
    assert queue.get("complete-task").state == "COMPLETE"
    assert queue.get("complete-task").attempts == 1


def test_recover_incomplete_tasks_respects_retry_limits(tmp_path: Path) -> None:
    queue = WorkQueueManager(
        state_store=WorkQueueStateStore(tmp_path / "queue.json"),
        items=(
            WorkItem("exhausted-task", "Exhausted Task", max_retries=1, retryable=True),
        ),
    )
    from hermes_v01.work_queue import WorkQueueState
    items = list(queue.state.items)
    items[0] = replace(items[0], state="RUNNING", attempts=1)  # already at max
    new_state = WorkQueueState(schema_version="1", revision=1, items=tuple(items))
    queue._persist(new_state)
    
    recovered = queue.recover_incomplete_tasks()
    
    assert len(recovered) == 0  # cannot retry
    assert queue.get("exhausted-task").state == "RUNNING"  # unchanged
