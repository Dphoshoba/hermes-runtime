from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from evosia.work_queue import WorkItem, WorkQueueManager, WorkQueueStateStore, WorkQueueState


def test_compact_archives_complete_tasks(tmp_path: Path) -> None:
    queue = WorkQueueManager(
        state_store=WorkQueueStateStore(tmp_path / "queue.json"),
        items=(
            WorkItem("active", "Active Task", state="READY"),
            WorkItem("complete-1", "Complete 1", state="COMPLETE", last_run_at="2026-01-01T00:00:00Z"),
            WorkItem("complete-2", "Complete 2", state="COMPLETE", last_run_at="2026-01-01T00:00:00Z"),
            WorkItem("running", "Running Task", state="RUNNING"),
        ),
    )
    
    archive_path = tmp_path / "archive.json"
    archived, remaining = queue.compact(archive_path)
    
    assert archived == 2
    assert remaining == 2
    assert queue.get("active").state == "READY"
    assert queue.get("running").state == "RUNNING"
    with pytest.raises(KeyError):
        queue.get("complete-1")
    
    # Verify archive file
    archive_data = json.loads(archive_path.read_text())
    assert archive_data["schema_version"] == "1"
    assert len(archive_data["items"]) == 2
    archived_ids = {item["task_id"] for item in archive_data["items"]}
    assert archived_ids == {"complete-1", "complete-2"}


def test_compact_no_complete_tasks(tmp_path: Path) -> None:
    queue = WorkQueueManager(
        state_store=WorkQueueStateStore(tmp_path / "queue.json"),
        items=(
            WorkItem("active", "Active Task", state="READY"),
            WorkItem("running", "Running Task", state="RUNNING"),
        ),
    )
    
    archive_path = tmp_path / "archive.json"
    archived, remaining = queue.compact(archive_path)
    
    assert archived == 0
    assert remaining == 2
    assert not archive_path.exists()  # No archive created if nothing to archive


def test_prune_terminal_tasks_removes_old_complete(tmp_path: Path) -> None:
    old_time = "2020-01-01T00:00:00Z"
    recent_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    queue = WorkQueueManager(
        state_store=WorkQueueStateStore(tmp_path / "queue.json"),
        items=(
            WorkItem("old-complete", "Old Complete", state="COMPLETE", last_run_at=old_time),
            WorkItem("recent-complete", "Recent Complete", state="COMPLETE", last_run_at=recent_time),
            WorkItem("no-timestamp", "No Timestamp", state="COMPLETE"),
            WorkItem("active", "Active", state="READY"),
        ),
    )
    
    pruned = queue.prune_terminal_tasks(max_age_hours=24.0)
    
    assert pruned == 1
    with pytest.raises(KeyError):
        queue.get("old-complete")
    # Recent and no-timestamp should remain
    assert queue.get("recent-complete").state == "COMPLETE"
    assert queue.get("no-timestamp").state == "COMPLETE"
    assert queue.get("active").state == "READY"


def test_prune_terminal_tasks_no_last_run_at_keeps_all(tmp_path: Path) -> None:
    queue = WorkQueueManager(
        state_store=WorkQueueStateStore(tmp_path / "queue.json"),
        items=(
            WorkItem("complete-1", "Complete 1", state="COMPLETE"),
            WorkItem("complete-2", "Complete 2", state="COMPLETE"),
        ),
    )
    
    pruned = queue.prune_terminal_tasks(max_age_hours=1.0)
    
    assert pruned == 0
    assert queue.get("complete-1").state == "COMPLETE"
    assert queue.get("complete-2").state == "COMPLETE"


def test_verify_integrity_healthy_queue(tmp_path: Path) -> None:
    queue = WorkQueueManager(
        state_store=WorkQueueStateStore(tmp_path / "queue.json"),
        items=(
            WorkItem("task-1", "Task 1", state="READY"),
            WorkItem("task-2", "Task 2", state="BLOCKED", dependencies=("task-1",)),
        ),
    )
    
    issues = queue.verify_integrity()
    
    assert issues == []


def test_verify_integrity_detects_duplicate_ids(tmp_path: Path) -> None:
    queue = WorkQueueManager(
        state_store=WorkQueueStateStore(tmp_path / "queue.json"),
        items=(WorkItem("task-1", "Task 1"),),
    )
    
    # Manually add duplicate by directly modifying _state
    items = list(queue._state.items)
    items.append(replace(items[0], task_id="task-1"))
    queue._state = WorkQueueState(schema_version="1", revision=1, items=tuple(items))
    
    issues = queue.verify_integrity()
    
    assert any("Duplicate task_id" in issue for issue in issues)


def test_verify_integrity_detects_missing_dependency(tmp_path: Path) -> None:
    queue = WorkQueueManager(
        state_store=WorkQueueStateStore(tmp_path / "queue.json"),
        items=(
            WorkItem("task-1", "Task 1", state="READY"),
        ),
    )
    
    # Add task with missing dependency by directly modifying _state
    items = list(queue._state.items)
    items.append(WorkItem("task-2", "Task 2", state="BLOCKED", dependencies=("missing",)))
    queue._state = WorkQueueState(schema_version="1", revision=1, items=tuple(items))
    
    issues = queue.verify_integrity()
    
    assert any("missing task: missing" in issue for issue in issues)


def test_verify_integrity_detects_cycle(tmp_path: Path) -> None:
    queue = WorkQueueManager(
        state_store=WorkQueueStateStore(tmp_path / "queue.json"),
        items=(WorkItem("task-1", "Task 1"),),
    )
    
    # Manually create cycle
    items = [
        WorkItem("a", "A", dependencies=("b",)),
        WorkItem("b", "B", dependencies=("a",)),
    ]
    queue._state = WorkQueueState(schema_version="1", revision=1, items=tuple(items))
    
    issues = queue.verify_integrity()
    
    assert any("Cycle detected" in issue for issue in issues)


def test_verify_integrity_detects_negative_attempts(tmp_path: Path) -> None:
    queue = WorkQueueManager(
        state_store=WorkQueueStateStore(tmp_path / "queue.json"),
        items=(WorkItem("task-1", "Task 1"),),
    )
    
    # Manually set negative attempts by creating WorkItem dict and bypassing validation
    import dataclasses
    items = list(queue._state.items)
    item_dict = dataclasses.asdict(items[0])
    item_dict["attempts"] = -1
    # Create new WorkItem without validation by using object.__new__
    new_item = object.__new__(WorkItem)
    for k, v in item_dict.items():
        object.__setattr__(new_item, k, v)
    items[0] = new_item
    queue._state = WorkQueueState(schema_version="1", revision=1, items=tuple(items))
    
    issues = queue.verify_integrity()
    
    assert any("negative attempts" in issue for issue in issues)


def test_verify_integrity_detects_invalid_scheduled_at(tmp_path: Path) -> None:
    queue = WorkQueueManager(
        state_store=WorkQueueStateStore(tmp_path / "queue.json"),
        items=(WorkItem("task-1", "Task 1"),),
    )
    
    # Manually set invalid scheduled_at
    import dataclasses
    items = list(queue._state.items)
    item_dict = dataclasses.asdict(items[0])
    item_dict["scheduled_at"] = "invalid-timestamp"
    new_item = object.__new__(WorkItem)
    for k, v in item_dict.items():
        object.__setattr__(new_item, k, v)
    items[0] = new_item
    queue._state = WorkQueueState(schema_version="1", revision=1, items=tuple(items))
    
    issues = queue.verify_integrity()
    
    assert any("invalid scheduled_at" in issue for issue in issues)


def test_repair_common_issues_fixes_negative_attempts(tmp_path: Path) -> None:
    queue = WorkQueueManager(
        state_store=WorkQueueStateStore(tmp_path / "queue.json"),
        items=(WorkItem("task-1", "Task 1"),),
    )
    
    # Manually set negative attempts
    import dataclasses
    items = list(queue._state.items)
    item_dict = dataclasses.asdict(items[0])
    item_dict["attempts"] = -5
    new_item = object.__new__(WorkItem)
    for k, v in item_dict.items():
        object.__setattr__(new_item, k, v)
    items[0] = new_item
    queue._state = WorkQueueState(schema_version="1", revision=1, items=tuple(items))
    
    repairs = queue.repair_common_issues()
    
    assert any("Reset negative attempts" in r for r in repairs)
    assert queue.get("task-1").attempts == 0


def test_repair_common_issues_clears_invalid_scheduled_at(tmp_path: Path) -> None:
    queue = WorkQueueManager(
        state_store=WorkQueueStateStore(tmp_path / "queue.json"),
        items=(WorkItem("task-1", "Task 1"),),
    )
    
    # Manually set invalid scheduled_at
    import dataclasses
    items = list(queue._state.items)
    item_dict = dataclasses.asdict(items[0])
    item_dict["scheduled_at"] = "invalid-timestamp"
    new_item = object.__new__(WorkItem)
    for k, v in item_dict.items():
        object.__setattr__(new_item, k, v)
    items[0] = new_item
    queue._state = WorkQueueState(schema_version="1", revision=1, items=tuple(items))
    
    repairs = queue.repair_common_issues()
    
    assert any("Cleared invalid scheduled_at" in r for r in repairs)
    assert queue.get("task-1").scheduled_at is None


def test_repair_common_issues_normalizes_states(tmp_path: Path) -> None:
    from evosia.work_queue import WorkQueueState
    queue = WorkQueueManager(
        state_store=WorkQueueStateStore(tmp_path / "queue.json"),
        items=(WorkItem("task-1", "Task 1"),),
    )
    
    # Manually set to BLOCKED when it should be READY (no deps)
    items = list(queue.state.items)
    items[0] = replace(items[0], state="BLOCKED")
    new_state = WorkQueueState(schema_version="1", revision=1, items=tuple(items))
    queue._persist(new_state)
    
    repairs = queue.repair_common_issues()
    
    assert any("Normalized BLOCKED/READY states" in r for r in repairs)
    assert queue.get("task-1").state == "READY"