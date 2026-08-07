from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_v01.metrics import (
    FailureClassification,
    classify_failure,
    compute_queue_metrics,
    compute_runtime_metrics,
    QueueMetrics,
    RuntimeMetrics,
)
from hermes_v01.work_queue import WorkItem, WorkQueueManager, WorkQueueStateStore


def test_classify_failure_infrastructure_connection_refused(tmp_path: Path) -> None:
    result = classify_failure("Connection refused to localhost:8080", None, "RUNNING")
    assert isinstance(result, FailureClassification)
    assert result.category == "INFRASTRUCTURE"
    assert result.recoverable is True


def test_classify_failure_infrastructure_timeout(tmp_path: Path) -> None:
    result = classify_failure("Request timeout after 30s", 124, "RUNNING")
    assert result.category == "INFRASTRUCTURE"
    assert result.recoverable is True


def test_classify_failure_dependency_modulenotfound(tmp_path: Path) -> None:
    result = classify_failure("ModuleNotFoundError: No module named requests", None, "RUNNING")
    assert result.category == "DEPENDENCY"
    assert result.recoverable is False


def test_classify_failure_dependency_import_error(tmp_path: Path) -> None:
    result = classify_failure("ImportError: cannot import name foo", None, "RUNNING")
    assert result.category == "DEPENDENCY"
    assert result.recoverable is False


def test_classify_failure_transient_rate_limit(tmp_path: Path) -> None:
    result = classify_failure("Rate limit exceeded, retry later", None, "RUNNING")
    assert result.category == "TRANSIENT"
    assert result.recoverable is True


def test_classify_failure_validation_assertion(tmp_path: Path) -> None:
    result = classify_failure("AssertionError: expected 1 got 2", 1, "VERIFICATION_PENDING")
    assert result.category == "VALIDATION"
    assert result.recoverable is False


def test_classify_failure_validation_test_failed(tmp_path: Path) -> None:
    result = classify_failure("test failed: expected True got False", 1, "VERIFICATION_PENDING")
    assert result.category == "VALIDATION"
    assert result.recoverable is False


def test_classify_failure_sigterm(tmp_path: Path) -> None:
    result = classify_failure("", 143, "RUNNING")
    assert result.category == "INFRASTRUCTURE"
    assert result.recoverable is True


def test_classify_failure_unknown_defaults_transient(tmp_path: Path) -> None:
    result = classify_failure("Something went wrong", 1, "RUNNING")
    assert result.category == "TRANSIENT"
    assert result.recoverable is True


def test_compute_queue_metrics_empty(tmp_path: Path) -> None:
    queue = WorkQueueManager(state_store=WorkQueueStateStore(tmp_path / "queue.json"))
    metrics = compute_queue_metrics(queue)
    
    assert isinstance(metrics, QueueMetrics)
    assert metrics.total_tasks == 0
    assert metrics.tasks_by_state == {}


def test_compute_queue_metrics_with_tasks(tmp_path: Path) -> None:
    queue = WorkQueueManager(
        state_store=WorkQueueStateStore(tmp_path / "queue.json"),
        items=(
            WorkItem("task-1", "Task 1", priority=10, state="READY"),
            WorkItem("task-2", "Task 2", priority=20, state="BLOCKED", dependencies=("dep",)),
            WorkItem("task-3", "Task 3", priority=30, state="COMPLETE"),
            WorkItem("task-4", "Task 4", priority=40, state="VERIFICATION_PENDING"),
            WorkItem("task-5", "Task 5", priority=50, state="RUNNING", attempts=2),
            WorkItem("dep", "Dependency", priority=1, state="RUNNING"),
        ),
    )
    metrics = compute_queue_metrics(queue)
    
    assert metrics.total_tasks == 6
    assert metrics.tasks_by_state["READY"] == 1
    assert metrics.tasks_by_state["BLOCKED"] == 1
    assert metrics.tasks_by_state["COMPLETE"] == 1
    assert metrics.tasks_by_state["VERIFICATION_PENDING"] == 1
    assert metrics.tasks_by_state["RUNNING"] == 2  # task-5 + dep
    assert metrics.ready_tasks == 1
    assert metrics.blocked_tasks == 1
    assert metrics.completed_tasks == 1
    assert metrics.pending_verification_tasks == 1
    assert metrics.running_tasks == 2
    assert metrics.max_attempts == 2
    assert metrics.retryable_tasks == 6  # default retryable=True


def test_compute_queue_metrics_non_retryable(tmp_path: Path) -> None:
    queue = WorkQueueManager(
        state_store=WorkQueueStateStore(tmp_path / "queue.json"),
        items=(
            WorkItem("retryable", "Retryable", retryable=True),
            WorkItem("non-retryable", "Non-Retryable", retryable=False),
        ),
    )
    metrics = compute_queue_metrics(queue)
    
    assert metrics.retryable_tasks == 1
    assert metrics.non_retryable_tasks == 1


def test_compute_runtime_metrics_empty(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    
    metrics = compute_runtime_metrics(runtime_root)
    
    assert isinstance(metrics, RuntimeMetrics)
    assert metrics.total_executions == 0
    assert metrics.execution_metrics == []


def test_compute_runtime_metrics_with_executions(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    evidence_dir = runtime_root / "evidence"
    
    # Create two execution records
    for i in range(2):
        exec_dir = evidence_dir / f"exec-20260807T115540.897622Z-test{i}"
        exec_dir.mkdir(parents=True)
        record = {
            "execution_record": {
                "execution_id": f"exec-test{i}",
                "command": f"python3 -c 'print({i})'",
                "start_time": f"2026-08-07T11:55:{40+i:02d}.000000Z",
                "end_time": f"2026-08-07T11:55:{41+i:02d}.000000Z",
                "exit_code": 0,
            }
        }
        (exec_dir / "execution-record.json").write_text(json.dumps(record))
    
    metrics = compute_runtime_metrics(runtime_root)
    
    assert metrics.total_executions == 2
    assert metrics.successful_executions == 2
    assert metrics.failed_executions == 0
    assert metrics.average_duration_seconds > 0
    assert metrics.first_execution_time is not None
    assert metrics.last_execution_time is not None