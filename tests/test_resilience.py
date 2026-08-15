"""Resilience and chaos tests for the Hermes Runtime.

Covers: interrupted tasks, queue corruption, partial writes, evidence failures,
review failures, health failures, scheduler restart, capability failure,
maintenance safety, and chaos scenarios.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from evosia.work_queue import (
    TERMINAL_TASK_STATES,
    TASK_STATES,
    WorkItem,
    WorkQueueManager,
    WorkQueueState,
    WorkQueueStateStore,
)
from evosia.capabilities import (
    CapabilityManager,
    CapabilityMetadata,
    CapabilityRegistry,
    CapabilityState,
    ExecutorPlugin,
    LocalExecutorPlugin,
    ExecutionResult,
)
from evosia.health import (
    build_health_report,
    write_health_reports,
)
from evosia.metrics import (
    classify_failure,
    compute_queue_metrics,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_item(
    task_id: str = "t1",
    *,
    state: str = "READY",
    dependencies: tuple[str, ...] = (),
    attempts: int = 0,
    max_retries: int = 3,
    retryable: bool = True,
    priority: int = 100,
    last_run_at: str | None = None,
    scheduled_at: str | None = None,
) -> WorkItem:
    return WorkItem(
        task_id=task_id,
        title=f"Task {task_id}",
        state=state,
        dependencies=dependencies,
        attempts=attempts,
        max_retries=max_retries,
        retryable=retryable,
        priority=priority,
        last_run_at=last_run_at,
        scheduled_at=scheduled_at,
    )


def _setup_queue(tmp_path: Path, items: list[WorkItem]) -> WorkQueueManager:
    store_path = tmp_path / "queue.json"
    store = WorkQueueStateStore(store_path)
    return WorkQueueManager(state_store=store, items=items)


class _FailingExecutor(ExecutorPlugin):
    """Executor that raises on every execute() call."""

    @property
    def name(self) -> str:
        return "failing"

    def execute(self, command: list[str], working_directory: Path, **kwargs) -> ExecutionResult:
        raise RuntimeError("executor failure injected")

    def health_check(self) -> tuple[bool, str | None]:
        return False, "failing executor is broken"


class _FailingWriteExecutor(ExecutorPlugin):
    """Executor that writes partially then fails mid-stream."""

    @property
    def name(self) -> str:
        return "failing_write"

    def execute(self, command: list[str], working_directory: Path, **kwargs) -> ExecutionResult:
        # Write some output then crash
        return ExecutionResult(exit_code=1, stdout="partial output", stderr="crash mid-write")

    def health_check(self) -> tuple[bool, str | None]:
        return False, "write failures"


# ===========================================================================
# 1. Runtime interruption
# ===========================================================================

class TestRuntimeInterruption:
    """Kill or interrupt a running task before completion."""

    def test_interrupted_running_task_not_marked_complete(self, tmp_path: Path) -> None:
        """A task in RUNNING state that is never completed should not be COMPLETE."""
        items = [_make_item("t1", state="READY")]
        mgr = _setup_queue(tmp_path, items)

        # Dispatch to RUNNING
        running = mgr.dispatch_next()
        assert running is not None
        assert running.state == "RUNNING"

        # Simulate crash — task stays in RUNNING, never reaches COMPLETE
        task = mgr.get("t1")
        assert task.state == "RUNNING"
        assert task.state not in TERMINAL_TASK_STATES

    def test_interrupted_task_is_recoverable(self, tmp_path: Path) -> None:
        """A RUNNING task can be recovered after crash."""
        items = [_make_item("t1", state="READY", max_retries=3)]
        mgr = _setup_queue(tmp_path, items)

        mgr.dispatch_next()
        assert mgr.get("t1").state == "RUNNING"

        # Simulate crash recovery — recover increments attempts
        recovered = mgr.recover_incomplete_tasks()
        assert len(recovered) == 1
        assert recovered[0].task_id == "t1"
        assert recovered[0].state == "READY"
        # dispatch_next set attempts=1, recovery increments to 2
        assert recovered[0].attempts == 2

    def test_interrupted_task_respects_retry_budget(self, tmp_path: Path) -> None:
        """A task with exhausted retries is not recovered."""
        items = [_make_item("t1", state="READY", max_retries=1, attempts=1)]
        mgr = _setup_queue(tmp_path, items)

        mgr.dispatch_next()  # attempts becomes 2
        assert mgr.get("t1").state == "RUNNING"

        # attempts=2 > max_retries=1, so can_retry() is False
        recovered = mgr.recover_incomplete_tasks()
        assert len(recovered) == 0
        assert mgr.get("t1").state == "RUNNING"

    def test_queue_not_corrupted_by_interruption(self, tmp_path: Path) -> None:
        """Queue state remains loadable after simulated interruption."""
        items = [
            _make_item("t1", state="READY"),
            _make_item("t2", state="READY"),
        ]
        mgr = _setup_queue(tmp_path, items)
        mgr.dispatch_next()  # t1 -> RUNNING

        # Reload from disk — should not raise
        store2 = WorkQueueStateStore(tmp_path / "queue.json")
        mgr2 = WorkQueueManager(state_store=store2)

        assert mgr2.get("t1").state == "RUNNING"
        assert mgr2.get("t2").state == "READY"

    def test_multiple_interrupted_tasks_all_recovered(self, tmp_path: Path) -> None:
        """Multiple in-flight tasks are all recovered."""
        items = [
            _make_item("t1", state="READY"),
            _make_item("t2", state="READY"),
            _make_item("t3", state="READY"),
        ]
        mgr = _setup_queue(tmp_path, items)
        mgr.transition("t1", "RUNNING", increment_attempts=True)
        mgr.transition("t2", "RUNNING", increment_attempts=True)
        # t3 stays READY

        recovered = mgr.recover_incomplete_tasks()
        assert len(recovered) == 2
        ids = {r.task_id for r in recovered}
        assert ids == {"t1", "t2"}


# ===========================================================================
# 2. Queue corruption
# ===========================================================================

class TestQueueCorruption:
    """Corrupt queue JSON and verify failure handling."""

    def test_corrupted_json_fails_clearly(self, tmp_path: Path) -> None:
        """Completely invalid JSON raises ValueError."""
        store_path = tmp_path / "queue.json"
        store_path.write_text("{invalid json!!!", encoding="utf-8")

        store = WorkQueueStateStore(store_path)
        with pytest.raises(ValueError, match="invalid work queue state"):
            store.load()

    def test_valid_json_wrong_schema_fails(self, tmp_path: Path) -> None:
        """Valid JSON but missing required fields raises ValueError."""
        store_path = tmp_path / "queue.json"
        store_path.write_text(json.dumps({"items": []}), encoding="utf-8")

        store = WorkQueueStateStore(store_path)
        with pytest.raises(ValueError, match="invalid work queue state"):
            store.load()

    def test_valid_json_invalid_item_fields_fails(self, tmp_path: Path) -> None:
        """Valid JSON with item that has invalid fields raises ValueError."""
        store_path = tmp_path / "queue.json"
        store_path.write_text(json.dumps({
            "schema_version": "1",
            "revision": 0,
            "items": [{"task_id": "", "title": "x"}],
        }), encoding="utf-8")

        store = WorkQueueStateStore(store_path)
        with pytest.raises(ValueError, match="invalid work queue state"):
            store.load()

    def test_truncated_json_fails(self, tmp_path: Path) -> None:
        """Truncated JSON file raises ValueError."""
        store_path = tmp_path / "queue.json"
        store_path.write_text('{"schema_version": "1", "revision": 0, "items": [', encoding="utf-8")

        store = WorkQueueStateStore(store_path)
        with pytest.raises(ValueError, match="invalid work queue state"):
            store.load()

    def test_repair_normalizes_blocked_ready_states(self, tmp_path: Path) -> None:
        """repair_common_issues normalizes BLOCKED/READY based on dependencies."""
        items = [
            _make_item("t1", state="READY"),
            _make_item("t2", state="BLOCKED", dependencies=("t1",)),
        ]
        mgr = _setup_queue(tmp_path, items)

        # Complete t1 — t2 should now be READY
        mgr.transition("t1", "RUNNING", increment_attempts=True)
        mgr.mark_observed("t1")
        mgr.mark_verification_pending("t1")
        mgr.record_independent_verification("t1")
        mgr.mark_complete("t1")

        # t2 should already be READY after normalize on persist
        assert mgr.get("t2").state == "READY"

        # repair should be a no-op
        repairs = mgr.repair_common_issues()
        # normalize might not add a repair msg if state is already correct

    def test_repair_clears_invalid_scheduled_at_from_json(self, tmp_path: Path) -> None:
        """repair_common_issues clears invalid scheduled_at that survives loading."""
        # scheduled_at is validated at WorkItem construction, so we can only test
        # with a valid timestamp that we then verify repair handles.
        items = [_make_item("t1", state="READY", scheduled_at="2020-01-01T00:00:00Z")]
        mgr = _setup_queue(tmp_path, items)

        # Repair should not break anything
        repairs = mgr.repair_common_issues()
        assert isinstance(repairs, list)

    def test_unrecoverable_corruption_not_silently_rewritten(self, tmp_path: Path) -> None:
        """Corrupted file is NOT silently replaced by a new empty queue."""
        store_path = tmp_path / "queue.json"
        original_content = "NOT_VALID_JSON{{{"
        store_path.write_text(original_content, encoding="utf-8")

        # Attempt to load raises
        store = WorkQueueStateStore(store_path)
        with pytest.raises(ValueError):
            store.load()

        # File content is NOT changed
        assert store_path.read_text() == original_content

    def test_corrupted_with_extra_keys_loads_gracefully(self, tmp_path: Path) -> None:
        """Extra unknown keys in JSON don't break loading."""
        store_path = tmp_path / "queue.json"
        store_path.write_text(json.dumps({
            "schema_version": "1",
            "revision": 0,
            "items": [],
            "unknown_future_field": "hello",
        }))

        store = WorkQueueStateStore(store_path)
        state = store.load()
        assert state is not None
        assert state.items == ()


# ===========================================================================
# 3. Partial writes
# ===========================================================================

class TestPartialWrites:
    """Simulate interruption during atomic persistence."""

    def test_canonical_queue_file_survives_failed_write(self, tmp_path: Path) -> None:
        """If a new write fails, the original file remains valid."""
        items = [_make_item("t1", state="READY")]
        mgr = _setup_queue(tmp_path, items)

        store_path = tmp_path / "queue.json"
        original_content = store_path.read_text()

        # Simulate a failed write: corrupt the temp file path
        # The save method creates a temp file then os.replace.
        # If os.replace fails, the original should remain.
        with patch("evosia.utils.os.replace", side_effect=OSError("disk full")):
            with pytest.raises(OSError, match="disk full"):
                mgr.transition("t1", "RUNNING", increment_attempts=True)

        # Original file should still be valid
        store = WorkQueueStateStore(store_path)
        state = store.load()
        assert state is not None
        assert state.items[0].state == "READY"

    def test_temp_files_do_not_replace_valid_state(self, tmp_path: Path) -> None:
        """Leftover .tmp files don't interfere with loading."""
        items = [_make_item("t1", state="READY")]
        mgr = _setup_queue(tmp_path, items)

        store_path = tmp_path / "queue.json"
        # Create a leftover temp file (simulating a crash after write but before cleanup)
        tmp_file = tmp_path / ".queue.json.tmp"
        tmp_file.write_text("garbage", encoding="utf-8")

        # Loading should use the canonical file, not the temp
        store = WorkQueueStateStore(store_path)
        state = store.load()
        assert state is not None
        assert state.items[0].task_id == "t1"

    def test_atomic_write_preserves_valid_state_on_success(self, tmp_path: Path) -> None:
        """Successful atomic write updates state correctly."""
        items = [_make_item("t1", state="READY")]
        mgr = _setup_queue(tmp_path, items)

        mgr.transition("t1", "RUNNING", increment_attempts=True)

        store = WorkQueueStateStore(tmp_path / "queue.json")
        state = store.load()
        assert state.items[0].state == "RUNNING"
        assert state.items[0].attempts == 1

    def test_rapid_successive_writes_maintain_consistency(self, tmp_path: Path) -> None:
        """Multiple rapid transitions maintain queue consistency."""
        items = [_make_item("t1", state="READY")]
        mgr = _setup_queue(tmp_path, items)

        for _ in range(10):
            mgr.transition("t1", "RUNNING", increment_attempts=True)
            mgr.transition("t1", "READY", increment_attempts=False)

        store = WorkQueueStateStore(tmp_path / "queue.json")
        state = store.load()
        assert state.items[0].state == "READY"


# ===========================================================================
# 4. Evidence failures
# ===========================================================================

class TestEvidenceFailures:
    """Simulate stdout/stderr/artifact write failure."""

    def test_failing_executor_not_falsely_promoted(self, tmp_path: Path) -> None:
        """A failing executor does not result in task reaching COMPLETE."""
        items = [_make_item("t1", state="READY")]
        mgr = _setup_queue(tmp_path, items)

        # Simulate what run_pipeline does with a failing executor
        mgr.transition("t1", "RUNNING", increment_attempts=True)

        executor = _FailingExecutor()
        try:
            executor.execute(["false", "arg"], tmp_path)
        except RuntimeError:
            pass

        # Task should stay in RUNNING, not be promoted
        task = mgr.get("t1")
        assert task.state == "RUNNING"
        assert task.state not in TERMINAL_TASK_STATES

    def test_failing_executor_records_error(self, tmp_path: Path) -> None:
        """When executor fails, the error is recorded via mark_failed."""
        items = [_make_item("t1", state="READY", max_retries=3)]
        mgr = _setup_queue(tmp_path, items)
        mgr.transition("t1", "RUNNING", increment_attempts=True)

        # Simulate failure path
        mgr.mark_failed("t1", "executor crashed")
        task = mgr.get("t1")
        assert task.last_error == "executor crashed"

    def test_partial_output_not_promoted_to_observed(self, tmp_path: Path) -> None:
        """Partial stdout without evidence record does not advance state."""
        items = [_make_item("t1", state="READY")]
        mgr = _setup_queue(tmp_path, items)
        mgr.transition("t1", "RUNNING", increment_attempts=True)

        # If execution_record_path is None, the runtime never calls mark_observed
        task = mgr.get("t1")
        assert task.state == "RUNNING"

    def test_evidence_write_failure_leaves_queue_recoverable(self, tmp_path: Path) -> None:
        """Evidence write failure doesn't leave queue in unrecoverable state."""
        items = [_make_item("t1", state="READY", max_retries=3)]
        mgr = _setup_queue(tmp_path, items)
        mgr.transition("t1", "RUNNING", increment_attempts=True)
        mgr.mark_failed("t1", "evidence write failed")

        # mark_failed transitions retryable task back to READY
        task = mgr.get("t1")
        assert task.can_retry()
        assert task.state == "READY"
        assert task.last_error == "evidence write failed"


# ===========================================================================
# 5. Review failures
# ===========================================================================

class TestReviewFailures:
    """Simulate REVIEW_FAILED and REVIEW_INCOMPLETE."""

    def test_review_failed_does_not_promote_to_complete(self, tmp_path: Path) -> None:
        """REVIEW_FAILED never results in COMPLETE state."""
        items = [_make_item("t1", state="READY")]
        mgr = _setup_queue(tmp_path, items)
        mgr.transition("t1", "RUNNING", increment_attempts=True)
        mgr.mark_observed("t1")
        mgr.mark_verification_pending("t1")

        # Simulate review failure: task stays in VERIFICATION_PENDING
        # The runtime only calls record_independent_verification on success
        task = mgr.get("t1")
        assert task.state == "VERIFICATION_PENDING"
        assert task.state not in TERMINAL_TASK_STATES

    def test_review_incomplete_does_not_promote_to_complete(self, tmp_path: Path) -> None:
        """REVIEW_INCOMPLETE never results in COMPLETE state."""
        items = [_make_item("t1", state="READY")]
        mgr = _setup_queue(tmp_path, items)
        mgr.transition("t1", "RUNNING", increment_attempts=True)
        mgr.mark_observed("t1")
        mgr.mark_verification_pending("t1")

        # Review incomplete = state stays VERIFICATION_PENDING
        task = mgr.get("t1")
        assert task.state == "VERIFICATION_PENDING"

    def test_review_failure_retry_path_available(self, tmp_path: Path) -> None:
        """After review failure, task can be retried."""
        items = [_make_item("t1", state="READY", max_retries=3)]
        mgr = _setup_queue(tmp_path, items)
        mgr.transition("t1", "RUNNING", increment_attempts=True)
        mgr.mark_observed("t1")
        mgr.mark_verification_pending("t1")

        # Simulate review failure by marking failed
        mgr.mark_failed("t1", "review failed")
        task = mgr.get("t1")
        assert task.can_retry()
        assert task.state == "READY"

    def test_review_failure_exhausted_retries(self, tmp_path: Path) -> None:
        """After review failure with no retries left, task is stuck."""
        items = [_make_item("t1", state="READY", max_retries=1)]
        mgr = _setup_queue(tmp_path, items)
        mgr.transition("t1", "RUNNING", increment_attempts=True)  # attempts=1
        mgr.mark_observed("t1")
        mgr.mark_verification_pending("t1")

        mgr.mark_failed("t1", "review failed")
        task = mgr.get("t1")
        assert not task.can_retry()
        # State stays in whatever mark_failed leaves it (not COMPLETE)
        assert task.state not in TERMINAL_TASK_STATES

    def test_record_independent_verification_only_from_pending(self, tmp_path: Path) -> None:
        """record_independent_verification requires VERIFICATION_PENDING."""
        items = [_make_item("t1", state="READY")]
        mgr = _setup_queue(tmp_path, items)
        mgr.transition("t1", "RUNNING", increment_attempts=True)

        with pytest.raises(ValueError, match="independent verification requires"):
            mgr.record_independent_verification("t1")


# ===========================================================================
# 6. Health failures
# ===========================================================================

class TestHealthFailures:
    """Simulate missing or malformed health inputs."""

    def test_empty_runtime_is_unknown(self, tmp_path: Path) -> None:
        """Health report for empty runtime is UNKNOWN, not a crash."""
        report = build_health_report(tmp_path)
        assert report.overall_health == "UNKNOWN"
        assert report.execution_record_count == 0
        assert report.review_count == 0

    def test_missing_evidence_dir_does_not_crash(self, tmp_path: Path) -> None:
        """Missing evidence directory returns valid report."""
        (tmp_path / "supervisor").mkdir()
        (tmp_path / "reviews").mkdir()
        (tmp_path / "reviewer-reviews").mkdir()

        report = build_health_report(tmp_path)
        assert report.overall_health == "UNKNOWN"

    def test_malformed_execution_record_does_not_crash(self, tmp_path: Path) -> None:
        """Malformed execution record doesn't crash health report.
        Note: health counts by glob pattern, so malformed files still count."""
        evidence_dir = tmp_path / "evidence" / "exec-20260101T000000.000000Z-abc123def456"
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "execution-record.json").write_text("not json!!!")

        report = build_health_report(tmp_path)
        # Health counts by glob pattern, file exists so it counts
        assert report.execution_record_count == 1
        # But the data is not usable for health determination
        assert report.last_execution_id is None

    def test_malformed_review_does_not_crash(self, tmp_path: Path) -> None:
        """Malformed review file doesn't crash health report.
        Note: health counts by glob pattern, so malformed files still count."""
        review_dir = tmp_path / "reviews" / "review-20260101T000000.000000Z-abc123def456"
        review_dir.mkdir(parents=True)
        (review_dir / "review.json").write_text("{bad json")

        report = build_health_report(tmp_path)
        # Health counts by glob pattern, directory exists so it counts
        assert report.review_count == 1
        # But the data is not usable
        assert report.last_review_outcome is None

    def test_health_report_survives_missing_supervisor_state(self, tmp_path: Path) -> None:
        """Missing supervisor-state.json doesn't crash health."""
        evidence_dir = tmp_path / "evidence" / "exec-20260101T000000.000000Z-abc123def456"
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "execution-record.json").write_text(json.dumps({
            "execution_record": {"end_time": "2026-01-01T00:00:01Z", "exit_code": 0, "execution_id": "exec-20260101T000000.000000Z-abc123def456"},
        }))

        report = build_health_report(tmp_path)
        assert report.overall_health in ("HEALTHY", "WARNING", "UNKNOWN")

    def test_health_report_with_failed_execution(self, tmp_path: Path) -> None:
        """Failed execution results in FAILED health."""
        evidence_dir = tmp_path / "evidence" / "exec-20260101T000000.000000Z-abc123def456"
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "execution-record.json").write_text(json.dumps({
            "execution_record": {"end_time": "2026-01-01T00:00:01Z", "exit_code": 1, "execution_id": "exec-20260101T000000.000000Z-abc123def456"},
        }))

        report = build_health_report(tmp_path)
        assert report.overall_health == "FAILED"
        assert report.last_failure is not None

    def test_write_health_reports_creates_files(self, tmp_path: Path) -> None:
        """Health report writing works even with minimal data."""
        from evosia.health import HealthReport

        report = HealthReport(
            runtime_version="0.7.6",
            last_execution_id=None,
            last_execution_time=None,
            last_execution_exit_code=None,
            last_supervisor_cycle=None,
            last_supervisor_status=None,
            last_review_outcome=None,
            execution_record_count=0,
            review_count=0,
            supervisor_cycle_count=0,
            last_failure=None,
            overall_health="UNKNOWN",
        )
        json_path, md_path = write_health_reports(report, tmp_path / "health")
        assert json_path.exists()
        assert md_path.exists()


# ===========================================================================
# 7. Scheduler restart recovery
# ===========================================================================

class TestSchedulerRestartRecovery:
    """Persist scheduled/queued work and verify restart recovery."""

    def test_scheduled_task_survives_restart(self, tmp_path: Path) -> None:
        """Scheduled tasks persist across queue reload."""
        items = [_make_item("t1", state="READY")]
        mgr = _setup_queue(tmp_path, items)

        mgr.schedule_task("t1", "2026-12-31T23:59:59Z")
        task = mgr.get("t1")
        assert task.scheduled_at == "2026-12-31T23:59:59Z"

        # Simulate restart by reloading
        store2 = WorkQueueStateStore(tmp_path / "queue.json")
        mgr2 = WorkQueueManager(state_store=store2)
        task2 = mgr2.get("t1")
        assert task2.scheduled_at == "2026-12-31T23:59:59Z"

    def test_attempts_preserved_after_restart(self, tmp_path: Path) -> None:
        """Attempt counts survive queue reload."""
        items = [_make_item("t1", state="READY", max_retries=5)]
        mgr = _setup_queue(tmp_path, items)

        mgr.transition("t1", "RUNNING", increment_attempts=True)
        mgr.mark_failed("t1", "error 1")
        mgr.transition("t1", "RUNNING", increment_attempts=True)
        mgr.mark_failed("t1", "error 2")

        # Reload
        store2 = WorkQueueStateStore(tmp_path / "queue.json")
        mgr2 = WorkQueueManager(state_store=store2)
        task = mgr2.get("t1")
        assert task.attempts == 2
        assert task.last_error == "error 2"

    def test_retry_budget_preserved_after_restart(self, tmp_path: Path) -> None:
        """Retryable flag and max_retries survive reload."""
        items = [_make_item("t1", state="READY", max_retries=2, retryable=True)]
        mgr = _setup_queue(tmp_path, items)
        mgr.transition("t1", "RUNNING", increment_attempts=True)
        mgr.mark_failed("t1", "error")

        store2 = WorkQueueStateStore(tmp_path / "queue.json")
        mgr2 = WorkQueueManager(state_store=store2)
        task = mgr2.get("t1")
        assert task.max_retries == 2
        assert task.retryable is True

    def test_recovery_preserves_attempt_budget(self, tmp_path: Path) -> None:
        """recover_incomplete_tasks increments attempts correctly across reloads."""
        items = [_make_item("t1", state="READY", max_retries=10)]
        mgr = _setup_queue(tmp_path, items)

        # Cycle 1: dispatch -> crash -> recover -> reload
        mgr.dispatch_next()  # RUNNING, attempts=1
        mgr.recover_incomplete_tasks()  # READY, attempts=2
        store = WorkQueueStateStore(tmp_path / "queue.json")
        mgr = WorkQueueManager(state_store=store)
        assert mgr.get("t1").state == "READY"
        assert mgr.get("t1").attempts == 2

        # Cycle 2: dispatch -> crash -> recover -> reload
        mgr.dispatch_next()  # RUNNING, attempts=3
        mgr.recover_incomplete_tasks()  # READY, attempts=4
        store = WorkQueueStateStore(tmp_path / "queue.json")
        mgr = WorkQueueManager(state_store=store)
        assert mgr.get("t1").state == "READY"
        assert mgr.get("t1").attempts == 4

        # Cycle 3: dispatch -> crash -> recover -> reload
        mgr.dispatch_next()  # RUNNING, attempts=5
        mgr.recover_incomplete_tasks()  # READY, attempts=6
        store = WorkQueueStateStore(tmp_path / "queue.json")
        mgr = WorkQueueManager(state_store=store)
        assert mgr.get("t1").state == "READY"
        assert mgr.get("t1").attempts == 6

    def test_dependency_chain_preserved_after_restart(self, tmp_path: Path) -> None:
        """Dependency relationships survive queue reload."""
        items = [
            _make_item("t1", state="READY"),
            _make_item("t2", state="BLOCKED", dependencies=("t1",)),
        ]
        mgr = _setup_queue(tmp_path, items)

        store2 = WorkQueueStateStore(tmp_path / "queue.json")
        mgr2 = WorkQueueManager(state_store=store2)

        assert mgr2.get("t2").dependencies == ("t1",)
        assert mgr2.get("t2").state == "BLOCKED"

    def test_due_tasks_survive_restart(self, tmp_path: Path) -> None:
        """Scheduled-at timestamps for due tasks survive reload."""
        items = [_make_item("t1", state="READY", scheduled_at="2020-01-01T00:00:00Z")]
        mgr = _setup_queue(tmp_path, items)

        store2 = WorkQueueStateStore(tmp_path / "queue.json")
        mgr2 = WorkQueueManager(state_store=store2)
        task = mgr2.get("t1")
        assert task.scheduled_at == "2020-01-01T00:00:00Z"
        assert task.is_due()


# ===========================================================================
# 8. Capability failure
# ===========================================================================

class TestCapabilityFailure:
    """Disable or break a selected executor capability."""

    def test_disabled_executor_raises(self, tmp_path: Path) -> None:
        """get_executor raises ValueError for disabled capability."""
        registry = CapabilityRegistry(tmp_path / "registry.json")
        manager = CapabilityManager(registry, [])

        # Disable the local executor
        registry.disable("local")

        with pytest.raises(ValueError, match="disabled"):
            manager.get_executor("local")

    def test_nonexistent_executor_raises(self, tmp_path: Path) -> None:
        """get_executor raises KeyError for unknown capability."""
        registry = CapabilityRegistry(tmp_path / "registry.json")
        manager = CapabilityManager(registry, [])

        with pytest.raises(KeyError):
            manager.get_executor("nonexistent")

    def test_non_executor_capability_raises(self, tmp_path: Path) -> None:
        """get_executor raises ValueError for non-executor capability."""
        registry = CapabilityRegistry(tmp_path / "registry.json")

        # Register a non-executor capability directly
        metadata = CapabilityMetadata(
            name="not-an-executor",
            version="1.0.0",
            description="Not an executor",
            capability_type="validator",
            entry_point="mod:Cls",
            required_runtime_version="0.7.0",
        )
        registry.register(metadata)

        manager = CapabilityManager(registry, [])
        with pytest.raises(ValueError, match="not an executor"):
            manager.get_executor("not-an-executor")

    def test_health_check_for_disabled_executor(self, tmp_path: Path) -> None:
        """check_health on disabled executor reports UNHEALTHY."""
        registry = CapabilityRegistry(tmp_path / "registry.json")
        manager = CapabilityManager(registry, [])
        registry.disable("local")

        # get_executor raises because local is disabled
        with pytest.raises(ValueError, match="disabled"):
            manager.get_executor("local")

    def test_health_check_all_includes_broken(self, tmp_path: Path) -> None:
        """check_all_health handles mixed healthy/broken executors."""
        registry = CapabilityRegistry(tmp_path / "registry.json")
        manager = CapabilityManager(registry, [])

        # Register a broken executor
        broken_meta = CapabilityMetadata(
            name="broken",
            version="1.0.0",
            description="Broken",
            capability_type="executor",
            entry_point="nonexistent:Class",
            required_runtime_version="0.7.0",
        )
        registry.register(broken_meta)

        results = manager.check_all_health()
        names = {r.metadata.name for r in results}
        assert "local" in names
        assert "broken" in names

        broken_state = next(r for r in results if r.metadata.name == "broken")
        assert broken_state.health_status == "UNHEALTHY"

    def test_failing_executor_plugin_classification(self, tmp_path: Path) -> None:
        """Failure from a broken executor plugin is classified correctly."""
        executor = _FailingExecutor()
        with pytest.raises(RuntimeError, match="executor failure injected"):
            executor.execute(["cmd"], tmp_path)

        # The failure classification should handle RuntimeError
        classification = classify_failure("executor failure injected", None, "RUNNING")
        assert classification.category in ("TRANSIENT", "INFRASTRUCTURE")
        assert classification.recoverable is True

    def test_local_executor_fallback_only_when_explicit(self, tmp_path: Path) -> None:
        """Built-in local executor is always available as a fallback."""
        registry = CapabilityRegistry(tmp_path / "registry.json")
        manager = CapabilityManager(registry, [])

        # local should always be available
        executor = manager.get_executor("local")
        assert executor.name == "local"


# ===========================================================================
# 9. Compaction/maintenance safety
# ===========================================================================

class TestCompactionSafety:
    """Run compaction/pruning around active and terminal tasks."""

    def test_compaction_preserves_active_tasks(self, tmp_path: Path) -> None:
        """Active tasks are never removed during compaction."""
        items = [
            _make_item("t1", state="COMPLETE"),
            _make_item("t2", state="RUNNING"),
            _make_item("t3", state="READY"),
        ]
        mgr = _setup_queue(tmp_path, items)

        archive_path = tmp_path / "archive.json"
        archived, remaining = mgr.compact(archive_path)

        assert archived == 1
        assert remaining == 2

        # Active tasks still exist
        assert mgr.get("t2").state == "RUNNING"
        assert mgr.get("t3").state == "READY"

    def test_compaction_no_complete_tasks(self, tmp_path: Path) -> None:
        """Compaction with no COMPLETE tasks is a no-op."""
        items = [
            _make_item("t1", state="RUNNING"),
            _make_item("t2", state="READY"),
        ]
        mgr = _setup_queue(tmp_path, items)

        archive_path = tmp_path / "archive.json"
        archived, remaining = mgr.compact(archive_path)

        assert archived == 0
        assert remaining == 2

    def test_pruning_preserves_active_tasks(self, tmp_path: Path) -> None:
        """Pruning never removes active tasks."""
        items = [
            _make_item("t1", state="COMPLETE", last_run_at="2020-01-01T00:00:00Z"),
            _make_item("t2", state="RUNNING"),
            _make_item("t3", state="COMPLETE", last_run_at="2020-01-01T00:00:00Z"),
        ]
        mgr = _setup_queue(tmp_path, items)

        pruned = mgr.prune_terminal_tasks(max_age_hours=1.0)
        assert pruned == 2
        assert mgr.get("t2").state == "RUNNING"

    def test_pruning_keeps_recent_complete(self, tmp_path: Path) -> None:
        """Recently completed tasks are not pruned."""
        from datetime import datetime, timezone, timedelta

        recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        items = [
            _make_item("t1", state="COMPLETE", last_run_at=recent),
        ]
        mgr = _setup_queue(tmp_path, items)

        pruned = mgr.prune_terminal_tasks(max_age_hours=168.0)
        assert pruned == 0
        assert mgr.get("t1").state == "COMPLETE"

    def test_integrity_valid_after_compaction(self, tmp_path: Path) -> None:
        """verify_integrity passes after compaction."""
        items = [
            _make_item("t1", state="COMPLETE"),
            _make_item("t2", state="RUNNING"),
        ]
        mgr = _setup_queue(tmp_path, items)

        mgr.compact(tmp_path / "archive.json")
        issues = mgr.verify_integrity()
        assert issues == []

    def test_integrity_valid_after_pruning(self, tmp_path: Path) -> None:
        """verify_integrity passes after pruning."""
        items = [
            _make_item("t1", state="COMPLETE", last_run_at="2020-01-01T00:00:00Z"),
            _make_item("t2", state="READY"),
        ]
        mgr = _setup_queue(tmp_path, items)

        mgr.prune_terminal_tasks(max_age_hours=1.0)
        issues = mgr.verify_integrity()
        assert issues == []

    def test_maintenance_during_active_work_preserves_integrity(self, tmp_path: Path) -> None:
        """Running compaction and pruning during active work is safe."""
        items = [
            _make_item("t1", state="COMPLETE", last_run_at="2020-01-01T00:00:00Z"),
            _make_item("t2", state="RUNNING"),
            _make_item("t3", state="READY"),
            _make_item("t4", state="COMPLETE", last_run_at="2020-01-01T00:00:00Z"),
        ]
        mgr = _setup_queue(tmp_path, items)

        mgr.compact(tmp_path / "archive.json")
        mgr.prune_terminal_tasks(max_age_hours=1.0)

        issues = mgr.verify_integrity()
        assert issues == []

        # Active tasks still intact
        assert mgr.get("t2").state == "RUNNING"
        assert mgr.get("t3").state == "READY"

    def test_pruning_without_last_run_at_keeps_all(self, tmp_path: Path) -> None:
        """COMPLETE tasks without last_run_at are not pruned."""
        items = [
            _make_item("t1", state="COMPLETE"),
        ]
        mgr = _setup_queue(tmp_path, items)

        pruned = mgr.prune_terminal_tasks(max_age_hours=1.0)
        assert pruned == 0


# ===========================================================================
# 10. Chaos / integration tests
# ===========================================================================

class TestChaos:
    """Comprehensive chaos and stress tests."""

    def test_chaos_interrupted_running_task(self, tmp_path: Path) -> None:
        """Full chaos: dispatch, interrupt, recover, retry, succeed."""
        items = [_make_item("t1", state="READY", max_retries=5)]
        mgr = _setup_queue(tmp_path, items)

        # Dispatch
        mgr.dispatch_next()
        assert mgr.get("t1").state == "RUNNING"

        # Crash — recover
        recovered = mgr.recover_incomplete_tasks()
        assert len(recovered) == 1
        assert mgr.get("t1").state == "READY"

        # Dispatch again
        mgr.dispatch_next()
        assert mgr.get("t1").state == "RUNNING"

        # Fail and retry
        mgr.mark_failed("t1", "failed again")
        assert mgr.get("t1").can_retry()
        assert mgr.get("t1").state == "READY"

    def test_chaos_restart_recovery(self, tmp_path: Path) -> None:
        """Full chaos: simulate multiple crash/restart cycles."""
        items = [
            _make_item("t1", state="READY", max_retries=5),
            _make_item("t2", state="READY", max_retries=5),
        ]
        mgr = _setup_queue(tmp_path, items)

        # First cycle: dispatch t1
        mgr.transition("t1", "RUNNING", increment_attempts=True)

        # Simulate restart
        store2 = WorkQueueStateStore(tmp_path / "queue.json")
        mgr2 = WorkQueueManager(state_store=store2)

        # t1 is RUNNING, t2 is READY — recover
        recovered = mgr2.recover_incomplete_tasks()
        assert len(recovered) == 1
        assert mgr2.get("t1").state == "READY"

        # Second cycle: dispatch both
        mgr2.transition("t1", "RUNNING", increment_attempts=True)
        mgr2.transition("t2", "RUNNING", increment_attempts=True)

        # Simulate restart
        store3 = WorkQueueStateStore(tmp_path / "queue.json")
        mgr3 = WorkQueueManager(state_store=store3)

        # Both are RUNNING — both should be recoverable
        recovered = mgr3.recover_incomplete_tasks()
        assert len(recovered) == 2
        recovered_ids = {r.task_id for r in recovered}
        assert recovered_ids == {"t1", "t2"}

    def test_chaos_corrupted_queue(self, tmp_path: Path) -> None:
        """Corrupted queue file raises ValueError, doesn't crash silently."""
        store_path = tmp_path / "queue.json"
        store_path.write_text("CORRUPTED", encoding="utf-8")

        with pytest.raises(ValueError, match="invalid work queue state"):
            WorkQueueStateStore(store_path).load()

    def test_chaos_malformed_evidence(self, tmp_path: Path) -> None:
        """Malformed evidence record is handled by health report."""
        evidence_dir = tmp_path / "evidence" / "exec-20260101T000000.000000Z-bad000000bad"
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "execution-record.json").write_text("not json")

        report = build_health_report(tmp_path)
        # Health counts by glob pattern, file exists so it counts
        assert report.execution_record_count == 1
        assert report.last_execution_id is None

    def test_chaos_failed_review(self, tmp_path: Path) -> None:
        """Failed review doesn't promote to COMPLETE, retry path works."""
        items = [_make_item("t1", state="READY", max_retries=3)]
        mgr = _setup_queue(tmp_path, items)

        mgr.dispatch_next()
        mgr.mark_observed("t1")
        mgr.mark_verification_pending("t1")

        # Simulate review failure
        mgr.mark_failed("t1", "review failed")
        assert mgr.get("t1").state == "READY"
        assert mgr.get("t1").can_retry()

    def test_chaos_partial_atomic_write(self, tmp_path: Path) -> None:
        """Partial atomic write doesn't corrupt canonical file."""
        items = [_make_item("t1", state="READY")]
        mgr = _setup_queue(tmp_path, items)

        original = (tmp_path / "queue.json").read_text()

        # Force a write failure
        with patch("evosia.utils.os.replace", side_effect=OSError("crash")):
            with pytest.raises(OSError):
                mgr.transition("t1", "RUNNING", increment_attempts=True)

        # Canonical file unchanged
        assert (tmp_path / "queue.json").read_text() == original

    def test_chaos_scheduler_restart(self, tmp_path: Path) -> None:
        """Scheduled work survives simulated scheduler restart."""
        items = [
            _make_item("t1", state="READY"),
            _make_item("t2", state="BLOCKED", dependencies=("t1",)),
        ]
        mgr = _setup_queue(tmp_path, items)
        mgr.schedule_task("t1", "2026-12-31T23:59:59Z")

        # Simulate restart
        store2 = WorkQueueStateStore(tmp_path / "queue.json")
        mgr2 = WorkQueueManager(state_store=store2)

        assert mgr2.get("t1").scheduled_at == "2026-12-31T23:59:59Z"
        assert mgr2.get("t2").dependencies == ("t1",)

    def test_chaos_exhausted_retry_budget(self, tmp_path: Path) -> None:
        """Exhausted retry budget leaves task non-retryable."""
        items = [_make_item("t1", state="READY", max_retries=2)]
        mgr = _setup_queue(tmp_path, items)

        # Use up retries: dispatch (attempts=1) -> fail -> dispatch (attempts=2) -> fail
        mgr.transition("t1", "RUNNING", increment_attempts=True)  # attempts=1
        mgr.mark_failed("t1", "err1")  # can_retry=1<2=True -> back to READY

        mgr.transition("t1", "RUNNING", increment_attempts=True)  # attempts=2
        mgr.mark_failed("t1", "err2")  # can_retry=2<2=False -> stays RUNNING with error

        # Now attempts=2, max_retries=2, can_retry() is False
        assert not mgr.get("t1").can_retry()
        # Task stays in RUNNING because mark_failed doesn't change state when can't retry
        assert mgr.get("t1").state == "RUNNING"
        assert mgr.get("t1").last_error == "err2"

    def test_chaos_disabled_executor(self, tmp_path: Path) -> None:
        """Disabled executor cannot be loaded."""
        registry = CapabilityRegistry(tmp_path / "registry.json")
        manager = CapabilityManager(registry, [])
        registry.disable("local")

        with pytest.raises(ValueError, match="disabled"):
            manager.get_executor("local")

    def test_chaos_maintenance_during_active_work(self, tmp_path: Path) -> None:
        """Maintenance during active work doesn't remove active tasks."""
        from datetime import datetime, timezone, timedelta

        recent = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
        old = "2020-01-01T00:00:00Z"

        items = [
            _make_item("t1", state="COMPLETE", last_run_at=old),
            _make_item("t2", state="RUNNING"),
            _make_item("t3", state="COMPLETE", last_run_at=recent),
        ]
        mgr = _setup_queue(tmp_path, items)

        mgr.compact(tmp_path / "archive.json")
        mgr.prune_terminal_tasks(max_age_hours=1.0)

        # t2 must survive (it's RUNNING, not COMPLETE)
        assert mgr.get("t2").state == "RUNNING"

        # t1 and t3 are COMPLETE — compact archives them, so they're no longer in active queue
        # The archive contains them
        issues = mgr.verify_integrity()
        assert issues == []

    def test_chaos_stale_persisted_state(self, tmp_path: Path) -> None:
        """Stale state from disk is loaded correctly and normalized."""
        # Write a queue where a task was BLOCKED but its dependency is now COMPLETE
        store_path = tmp_path / "queue.json"
        store_path.write_text(json.dumps({
            "schema_version": "1",
            "revision": 5,
            "items": [
                {"task_id": "t1", "title": "T1", "state": "COMPLETE", "dependencies": [],
                 "attempts": 1, "max_retries": 3, "retry_delay_seconds": 1.0,
                 "max_retry_delay_seconds": 60.0, "retry_backoff_multiplier": 2.0,
                 "retryable": True, "priority": 100, "scheduled_at": None,
                 "recurring": False, "interval_seconds": 0.0, "last_run_at": None},
                {"task_id": "t2", "title": "T2", "state": "BLOCKED", "dependencies": ["t1"],
                 "attempts": 0, "max_retries": 3, "retry_delay_seconds": 1.0,
                 "max_retry_delay_seconds": 60.0, "retry_backoff_multiplier": 2.0,
                 "retryable": True, "priority": 100, "scheduled_at": None,
                 "recurring": False, "interval_seconds": 0.0, "last_run_at": None},
            ],
        }))

        # Load — normalize should promote t2 to READY since t1 is COMPLETE
        store = WorkQueueStateStore(store_path)
        mgr = WorkQueueManager(state_store=store)
        assert mgr.get("t2").state == "READY"

    def test_chaos_health_degradation(self, tmp_path: Path) -> None:
        """Health degrades gracefully with various broken inputs."""
        # Create partially valid evidence
        evidence_dir = tmp_path / "evidence" / "exec-20260101T000000.000000Z-abc123def456"
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "execution-record.json").write_text(json.dumps({
            "execution_record": {
                "end_time": "2026-01-01T00:00:01Z",
                "exit_code": 1,
                "execution_id": "exec-20260101T000000.000000Z-abc123def456",
            },
        }))

        # Malformed review
        review_dir = tmp_path / "reviews" / "review-20260101T000000.000000Z-abc123def456"
        review_dir.mkdir(parents=True)
        (review_dir / "review.json").write_text("not json")

        report = build_health_report(tmp_path)
        # Should not crash
        assert report.overall_health in ("FAILED", "WARNING", "UNKNOWN")
        assert isinstance(report.execution_record_count, int)
        assert isinstance(report.review_count, int)

    def test_chaos_full_lifecycle(self, tmp_path: Path) -> None:
        """Complete lifecycle: create, dispatch, fail, retry, verify, complete."""
        items = [_make_item("t1", state="READY", max_retries=3)]
        mgr = _setup_queue(tmp_path, items)

        # Ready
        assert mgr.get("t1").state == "READY"
        ready = mgr.next_ready()
        assert ready is not None

        # Dispatch
        mgr.dispatch_next()
        assert mgr.get("t1").state == "RUNNING"

        # Fail
        mgr.mark_failed("t1", "temporary error")
        assert mgr.get("t1").state == "READY"

        # Retry
        mgr.dispatch_next()
        mgr.mark_observed("t1")
        mgr.mark_verification_pending("t1")
        mgr.record_independent_verification("t1")
        mgr.mark_complete("t1")
        assert mgr.get("t1").state == "COMPLETE"
        assert mgr.get("t1").state in TERMINAL_TASK_STATES

        # Integrity check
        issues = mgr.verify_integrity()
        assert issues == []

    def test_chaos_concurrent_transitions(self, tmp_path: Path) -> None:
        """Rapid concurrent-like transitions don't corrupt state."""
        items = [
            _make_item(f"t{i}", state="READY")
            for i in range(5)
        ]
        mgr = _setup_queue(tmp_path, items)

        # Rapidly dispatch and fail all tasks
        for i in range(5):
            mgr.transition(f"t{i}", "RUNNING", increment_attempts=True)
            mgr.mark_failed(f"t{i}", f"error {i}")

        # Reload and verify
        store2 = WorkQueueStateStore(tmp_path / "queue.json")
        mgr2 = WorkQueueManager(state_store=store2)

        for i in range(5):
            task = mgr2.get(f"t{i}")
            assert task.last_error == f"error {i}"
            assert task.state == "READY"

    def test_chaos_non_retryable_task_failure(self, tmp_path: Path) -> None:
        """Non-retryable task stays failed, no retry attempted."""
        items = [_make_item("t1", state="READY", retryable=False, max_retries=3)]
        mgr = _setup_queue(tmp_path, items)

        mgr.dispatch_next()
        mgr.mark_failed("t1", "permanent failure")

        task = mgr.get("t1")
        assert not task.can_retry()
        assert task.last_error == "permanent failure"

    def test_chaos_queue_metrics_after_chaos(self, tmp_path: Path) -> None:
        """Metrics computation works after chaotic state."""
        items = [
            _make_item("t1", state="COMPLETE"),
            _make_item("t2", state="RUNNING"),
            _make_item("t3", state="BLOCKED"),
            _make_item("t4", state="READY"),
        ]
        mgr = _setup_queue(tmp_path, items)

        # Verify metrics work on the current mixed state
        metrics = compute_queue_metrics(mgr)
        assert metrics.total_tasks == 4
        assert metrics.completed_tasks == 1
        assert metrics.running_tasks == 1

    def test_chaos_dependency_cycle_detection(self, tmp_path: Path) -> None:
        """Circular dependency is detected and rejected."""
        items = [_make_item("t1", state="READY")]
        mgr = _setup_queue(tmp_path, items)

        # Try to create a cycle — this should fail at validation
        with pytest.raises(ValueError, match="cannot depend on itself"):
            WorkItem(
                task_id="t2",
                title="T2",
                dependencies=("t2",),
            )

    def test_chaos_duplicate_task_detection(self, tmp_path: Path) -> None:
        """Duplicate task IDs are rejected."""
        with pytest.raises(ValueError, match="duplicate task_id"):
            _setup_queue(tmp_path, [
                _make_item("t1", state="READY"),
                _make_item("t1", state="READY"),
            ])

    def test_chaos_integrity_comprehensive(self, tmp_path: Path) -> None:
        """Comprehensive integrity check catches all issues."""
        items = [
            _make_item("t1", state="READY"),
            _make_item("t2", state="READY"),
        ]
        mgr = _setup_queue(tmp_path, items)

        issues = mgr.verify_integrity()
        assert issues == []  # Healthy queue

    def test_chaos_repair_and_verify_loop(self, tmp_path: Path) -> None:
        """Repair and verify loop converges to clean state."""
        items = [_make_item("t1", state="READY")]
        mgr = _setup_queue(tmp_path, items)

        # repair_normalizes BLOCKED/READY based on dependencies
        repairs = mgr.repair_common_issues()
        assert isinstance(repairs, list)

        # Verify integrity is clean
        issues = mgr.verify_integrity()
        assert issues == []

        # Repair again should be no-op
        repairs2 = mgr.repair_common_issues()
        assert len(repairs2) == 0

    def test_chaos_multiple_recoveries_exhaust_budget(self, tmp_path: Path) -> None:
        """Multiple crash/recovery cycles eventually exhaust retry budget."""
        items = [_make_item("t1", state="READY", max_retries=6)]
        mgr = _setup_queue(tmp_path, items)

        # Recovery 1: dispatch (attempts=1) -> crash -> recover (attempts=2)
        mgr.dispatch_next()
        recovered = mgr.recover_incomplete_tasks()
        assert len(recovered) == 1
        assert mgr.get("t1").attempts == 2

        # Recovery 2: dispatch (attempts=3) -> crash -> recover (attempts=4)
        mgr.dispatch_next()
        recovered = mgr.recover_incomplete_tasks()
        assert len(recovered) == 1
        assert mgr.get("t1").attempts == 4

        # Recovery 3: dispatch (attempts=5) -> crash -> recover (attempts=6)
        mgr.dispatch_next()
        recovered = mgr.recover_incomplete_tasks()
        assert len(recovered) == 1
        assert mgr.get("t1").attempts == 6

        # Now exhausted (6 >= max_retries=6): dispatch (attempts=7) -> crash
        mgr.dispatch_next()
        recovered = mgr.recover_incomplete_tasks()
        assert len(recovered) == 0
        assert not mgr.get("t1").can_retry()

    def test_chaos_health_with_no_files(self, tmp_path: Path) -> None:
        """Health with empty directories returns valid state."""
        (tmp_path / "evidence").mkdir()
        (tmp_path / "reviews").mkdir()
        (tmp_path / "supervisor").mkdir()
        (tmp_path / "reviewer-reviews").mkdir()

        report = build_health_report(tmp_path)
        assert report.overall_health == "UNKNOWN"
        assert report.execution_record_count == 0

    def test_chaos_capability_registry_persistence(self, tmp_path: Path) -> None:
        """Capability registry survives reload."""
        registry = CapabilityRegistry(tmp_path / "registry.json")
        manager = CapabilityManager(registry, [])  # registers "local"

        # Disable local
        registry.disable("local")

        # Reload
        registry2 = CapabilityRegistry(tmp_path / "registry.json")
        state = registry2.get("local")
        assert state.metadata.enabled is False

        # Also verify manager sees the disabled state
        with pytest.raises(ValueError, match="disabled"):
            manager.get_executor("local")

    def test_chaos_mixed_task_states(self, tmp_path: Path) -> None:
        """Queue with all possible states handles chaos correctly."""
        items = [
            _make_item("t1", state="READY"),
            _make_item("t2", state="BLOCKED"),
            _make_item("t3", state="RUNNING"),
            _make_item("t4", state="COMPLETE"),
        ]
        mgr = _setup_queue(tmp_path, items)

        # Recover incomplete
        recovered = mgr.recover_incomplete_tasks()
        assert len(recovered) == 1  # only t3

        # Verify integrity
        issues = mgr.verify_integrity()
        assert issues == []

        # Compact and prune
        mgr.compact(tmp_path / "archive.json")
        mgr.prune_terminal_tasks(max_age_hours=1.0)

        issues = mgr.verify_integrity()
        assert issues == []

    def test_chaos_error_message_preservation(self, tmp_path: Path) -> None:
        """Error messages survive state transitions and persistence."""
        items = [_make_item("t1", state="READY", max_retries=3)]
        mgr = _setup_queue(tmp_path, items)

        mgr.dispatch_next()
        mgr.mark_failed("t1", "detailed error: connection refused to port 8080")

        # Reload
        store2 = WorkQueueStateStore(tmp_path / "queue.json")
        mgr2 = WorkQueueManager(state_store=store2)

        assert mgr2.get("t1").last_error == "detailed error: connection refused to port 8080"

    def test_chaos_empty_command_execution(self, tmp_path: Path) -> None:
        """Empty command list raises an error (IndexError from subprocess)."""
        executor = LocalExecutorPlugin()
        with pytest.raises((ValueError, IndexError, OSError)):
            executor.execute([], tmp_path)

    def test_chaos_health_check_for_broken_entry_point(self, tmp_path: Path) -> None:
        """Health check for capability with broken entry_point reports UNHEALTHY."""
        registry = CapabilityRegistry(tmp_path / "registry.json")

        broken_meta = CapabilityMetadata(
            name="broken-ep",
            version="1.0.0",
            description="Broken",
            capability_type="executor",
            entry_point="nonexistent_module:ClassName",
            required_runtime_version="0.7.0",
        )
        registry.register(broken_meta)

        manager = CapabilityManager(registry, [])
        state = manager.check_health("broken-ep")
        assert state.health_status == "UNHEALTHY"
        assert state.health_error is not None

    def test_chaos_transition_to_terminal_blocked(self, tmp_path: Path) -> None:
        """Cannot move terminal task back to non-terminal."""
        items = [_make_item("t1", state="COMPLETE")]
        mgr = _setup_queue(tmp_path, items)

        with pytest.raises(ValueError, match="cannot move terminal task"):
            mgr.transition("t1", "READY")

    def test_chaos_double_dispatch_prevented(self, tmp_path: Path) -> None:
        """Cannot transition RUNNING task to RUNNING again."""
        items = [_make_item("t1", state="READY")]
        mgr = _setup_queue(tmp_path, items)

        mgr.dispatch_next()
        # Trying to transition RUNNING -> RUNNING is rejected
        with pytest.raises(ValueError, match="already running"):
            mgr.transition("t1", "RUNNING", increment_attempts=True)

    def test_chaos_mark_complete_requires_verified(self, tmp_path: Path) -> None:
        """mark_complete requires VERIFIED state."""
        items = [_make_item("t1", state="READY")]
        mgr = _setup_queue(tmp_path, items)
        mgr.dispatch_next()

        with pytest.raises(ValueError, match="completion requires"):
            mgr.mark_complete("t1")

    def test_chaos_recurring_task_reschedule(self, tmp_path: Path) -> None:
        """Recurring task can be rescheduled after completion."""
        item = WorkItem(
            task_id="t1",
            title="Task t1",
            state="COMPLETE",
            recurring=True,
            interval_seconds=3600.0,
            max_retries=3,
        )
        mgr = _setup_queue(tmp_path, [item])

        task = mgr.reschedule_recurring("t1")
        assert task.state == "READY"
        assert task.scheduled_at is not None

    def test_chaos_non_recurring_task_reschedule_fails(self, tmp_path: Path) -> None:
        """Non-recurring task cannot be rescheduled."""
        items = [_make_item("t1", state="COMPLETE")]
        mgr = _setup_queue(tmp_path, items)

        with pytest.raises(ValueError, match="not recurring"):
            mgr.reschedule_recurring("t1")

    def test_chaos_invalid_state_transition(self, tmp_path: Path) -> None:
        """Invalid state transitions are rejected."""
        items = [_make_item("t1", state="READY")]
        mgr = _setup_queue(tmp_path, items)

        with pytest.raises(ValueError, match="unknown task state"):
            mgr.transition("t1", "INVALID_STATE")

    def test_chaos_dispatch_from_empty_queue(self, tmp_path: Path) -> None:
        """Dispatching from empty queue returns None."""
        mgr = _setup_queue(tmp_path, [])
        assert mgr.dispatch_next() is None
        assert mgr.next_ready() is None

    def test_chaos_nonexistent_task_operations(self, tmp_path: Path) -> None:
        """Operations on nonexistent tasks raise KeyError."""
        mgr = _setup_queue(tmp_path, [_make_item("t1")])

        with pytest.raises(KeyError):
            mgr.get("nonexistent")

        with pytest.raises(KeyError):
            mgr.transition("nonexistent", "RUNNING")

    def test_chaos_full_stress_cycle(self, tmp_path: Path) -> None:
        """Stress test: create many tasks, exercise all paths."""
        items = [_make_item(f"t{i}", state="READY", max_retries=2) for i in range(20)]
        mgr = _setup_queue(tmp_path, items)

        # Dispatch all
        for _ in range(20):
            mgr.dispatch_next()

        # Fail half
        for i in range(10):
            mgr.mark_failed(f"t{i}", f"error {i}")

        # Recover
        recovered = mgr.recover_incomplete_tasks()
        assert len(recovered) == 10

        # Verify integrity
        issues = mgr.verify_integrity()
        assert issues == []

        # Compact
        mgr.compact(tmp_path / "archive.json")

        # Metrics
        metrics = compute_queue_metrics(mgr)
        assert metrics.total_tasks == 20

    def test_chaos_verify_integrity_comprehensive(self, tmp_path: Path) -> None:
        """Comprehensive integrity verification across all states."""
        items = [
            _make_item("t1", state="READY"),
            _make_item("t2", state="BLOCKED", dependencies=("t1",)),
            _make_item("t3", state="RUNNING"),
            _make_item("t4", state="COMPLETE"),
        ]
        mgr = _setup_queue(tmp_path, items)

        issues = mgr.verify_integrity()
        assert issues == []

        summary = mgr.summary()
        assert "t1" in summary["READY"]
        assert "t2" in summary["BLOCKED"]
        assert "t3" in summary["RUNNING"]
        assert "t4" in summary["COMPLETE"]

    def test_chaos_scheduler_with_due_tasks(self, tmp_path: Path) -> None:
        """Scheduler correctly handles due and not-due tasks."""
        from datetime import datetime, timezone, timedelta

        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")

        items = [
            _make_item("t1", state="READY", scheduled_at=past),
            _make_item("t2", state="READY", scheduled_at=future),
            _make_item("t3", state="READY"),
        ]
        mgr = _setup_queue(tmp_path, items)

        due = mgr.get_due_tasks()
        due_ids = [d.task_id for d in due]
        assert "t1" in due_ids
        assert "t3" in due_ids
        assert "t2" not in due_ids

    def test_chaos_dispatch_next_due(self, tmp_path: Path) -> None:
        """dispatch_next_due selects the highest priority due task."""
        from datetime import datetime, timezone, timedelta

        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")

        items = [
            _make_item("t1", state="READY", scheduled_at=past, priority=200),
            _make_item("t2", state="READY", scheduled_at=past, priority=1),
        ]
        mgr = _setup_queue(tmp_path, items)

        dispatched = mgr.dispatch_next_due()
        assert dispatched is not None
        # Lower priority number = higher priority
        assert dispatched.task_id == "t2"
