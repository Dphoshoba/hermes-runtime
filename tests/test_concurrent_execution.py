"""Comprehensive tests for concurrent mission execution."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from evosia.work_queue import WorkItem, WorkQueueManager, WorkQueueState, WorkQueueStateStore
from evosia.mission import Mission, MissionPlanner, MissionTask, Plan, parse_mission
from evosia.mission_runner import MissionRunner, MissionReport, save_mission_report, load_mission_report
from evosia.metrics import ConcurrentMissionMetrics, compute_concurrent_mission_metrics


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_work_item(
    task_id: str,
    state: str = "READY",
    dependencies: tuple[str, ...] = (),
    max_retries: int = 3,
    retryable: bool = True,
) -> WorkItem:
    return WorkItem(
        task_id=task_id,
        title=f"Task {task_id}",
        state=state,
        dependencies=dependencies,
        max_retries=max_retries,
        retryable=retryable,
    )


def _make_queue(store_path: Path, items: list[WorkItem]) -> WorkQueueManager:
    store = WorkQueueStateStore(store_path)
    return WorkQueueManager(state_store=store, items=tuple(items))


def _minimal_plan() -> dict:
    return {
        "mission_id": "concurrent-test-001",
        "title": "Concurrent Test Mission",
        "tasks": [
            {"title": "Task A", "command": ["echo", "a"]},
            {"title": "Task B", "command": ["echo", "b"]},
        ],
    }


def _diamond_plan() -> dict:
    return {
        "mission_id": "diamond-test-001",
        "title": "Diamond Dependency Mission",
        "tasks": [
            {"title": "Task A", "command": ["echo", "a"]},
            {"title": "Task B", "command": ["echo", "b"], "dependencies": ["task-0"]},
            {"title": "Task C", "command": ["echo", "c"], "dependencies": ["task-0"]},
            {"title": "Task D", "command": ["echo", "d"], "dependencies": ["task-1", "task-2"]},
        ],
    }


def _chain_plan() -> dict:
    return {
        "mission_id": "chain-test-001",
        "title": "Chain Dependency Mission",
        "tasks": [
            {"title": "Task A", "command": ["echo", "a"]},
            {"title": "Task B", "command": ["echo", "b"], "dependencies": ["task-0"]},
            {"title": "Task C", "command": ["echo", "c"], "dependencies": ["task-1"]},
        ],
    }


# ---------------------------------------------------------------------------
# WorkQueueManager.dispatch_ready Tests
# ---------------------------------------------------------------------------

class TestDispatchReady:
    def test_dispatch_ready_single(self, tmp_path: Path) -> None:
        q = _make_queue(tmp_path / "q.json", [_make_work_item("t1"), _make_work_item("t2")])
        dispatched = q.dispatch_ready(max_concurrent=1)
        assert len(dispatched) == 1
        assert dispatched[0].task_id == "t1"
        assert dispatched[0].state == "RUNNING"
        assert q.get("t2").state == "READY"

    def test_dispatch_ready_multiple(self, tmp_path: Path) -> None:
        q = _make_queue(tmp_path / "q.json", [_make_work_item("t1"), _make_work_item("t2"), _make_work_item("t3")])
        dispatched = q.dispatch_ready(max_concurrent=3)
        assert len(dispatched) == 3
        assert all(d.state == "RUNNING" for d in dispatched)
        ids = {d.task_id for d in dispatched}
        assert ids == {"t1", "t2", "t3"}

    def test_dispatch_ready_respects_priority(self, tmp_path: Path) -> None:
        q = _make_queue(tmp_path / "q.json", [
            WorkItem(task_id="low", title="Low", priority=200),
            WorkItem(task_id="high", title="High", priority=10),
            WorkItem(task_id="mid", title="Mid", priority=100),
        ])
        dispatched = q.dispatch_ready(max_concurrent=2)
        assert [d.task_id for d in dispatched] == ["high", "mid"]
        assert q.get("low").state == "READY"

    def test_dispatch_ready_fewer_than_requested(self, tmp_path: Path) -> None:
        q = _make_queue(tmp_path / "q.json", [_make_work_item("t1")])
        dispatched = q.dispatch_ready(max_concurrent=5)
        assert len(dispatched) == 1

    def test_dispatch_ready_no_ready_tasks(self, tmp_path: Path) -> None:
        q = _make_queue(tmp_path / "q.json", [
            _make_work_item("t1"),
            _make_work_item("t2", dependencies=("t1",)),
        ])
        q.dispatch_ready(max_concurrent=1)
        q.refresh()
        dispatched = q.dispatch_ready(max_concurrent=3)
        assert len(dispatched) == 0

    def test_dispatch_ready_invalid_max(self, tmp_path: Path) -> None:
        q = _make_queue(tmp_path / "q.json", [_make_work_item("t1")])
        with pytest.raises(ValueError, match="max_concurrent must be >= 1"):
            q.dispatch_ready(max_concurrent=0)

    def test_dispatch_ready_respects_dependencies(self, tmp_path: Path) -> None:
        q = _make_queue(tmp_path / "q.json", [
            _make_work_item("t1"),
            _make_work_item("t2", dependencies=("t1",)),
            _make_work_item("t3", dependencies=("t1",)),
        ])
        dispatched = q.dispatch_ready(max_concurrent=3)
        assert len(dispatched) == 1
        assert dispatched[0].task_id == "t1"
        assert q.get("t2").state == "BLOCKED"
        assert q.get("t3").state == "BLOCKED"

    def test_dispatch_ready_atomic_state(self, tmp_path: Path) -> None:
        q = _make_queue(tmp_path / "q.json", [_make_work_item("t1"), _make_work_item("t2")])
        dispatched = q.dispatch_ready(max_concurrent=2)
        items = q.items()
        assert all(item.state == "RUNNING" for item in items)
        assert q.state.revision > 0

    def test_dispatch_ready_empty_queue(self, tmp_path: Path) -> None:
        q = _make_queue(tmp_path / "q.json", [])
        dispatched = q.dispatch_ready(max_concurrent=3)
        assert len(dispatched) == 0

    def test_dispatch_ready_preserves_non_ready(self, tmp_path: Path) -> None:
        q = _make_queue(tmp_path / "q.json", [
            _make_work_item("t1"),
            _make_work_item("t2", dependencies=("t1",)),
            _make_work_item("t3"),
        ])
        dispatched = q.dispatch_ready(max_concurrent=1)
        assert len(dispatched) == 1
        assert q.get("t2").state == "BLOCKED"
        assert q.get("t3").state == "READY"


# ---------------------------------------------------------------------------
# MissionRunner Concurrency Tests
# ---------------------------------------------------------------------------

class TestMissionRunnerConcurrency:
    def test_concurrency_default_is_one(self, tmp_path: Path) -> None:
        runner = MissionRunner(
            runtime_root=tmp_path / "runtime",
            repository=tmp_path / "repo",
            working_directory=tmp_path / "work",
            queue_path=tmp_path / "queue.json",
        )
        assert runner.max_concurrency == 1

    def test_concurrency_can_be_set(self, tmp_path: Path) -> None:
        runner = MissionRunner(
            runtime_root=tmp_path / "runtime",
            repository=tmp_path / "repo",
            working_directory=tmp_path / "work",
            queue_path=tmp_path / "queue.json",
            max_concurrency=4,
        )
        assert runner.max_concurrency == 4

    def test_concurrency_minimum_is_one(self, tmp_path: Path) -> None:
        runner = MissionRunner(
            runtime_root=tmp_path / "runtime",
            repository=tmp_path / "repo",
            working_directory=tmp_path / "work",
            queue_path=tmp_path / "queue.json",
            max_concurrency=0,
        )
        assert runner.max_concurrency == 1

    def test_concurrency_negative_is_one(self, tmp_path: Path) -> None:
        runner = MissionRunner(
            runtime_root=tmp_path / "runtime",
            repository=tmp_path / "repo",
            working_directory=tmp_path / "work",
            queue_path=tmp_path / "queue.json",
            max_concurrency=-5,
        )
        assert runner.max_concurrency == 1

    def test_report_includes_concurrency_fields(self, tmp_path: Path) -> None:
        report = MissionReport(
            schema_version="1",
            mission_id="test",
            mission_title="Test",
            mission_type="generic",
            status="COMPLETED",
            started_at="2024-01-01T00:00:00Z",
            finished_at="2024-01-01T00:00:01Z",
            duration_seconds=1.0,
            tasks_planned=2,
            tasks_completed=2,
            tasks_failed=0,
            tasks_skipped=0,
            evidence_records=(),
            independent_reviews=(),
            queue_summary={},
            runtime_health="UNKNOWN",
            metrics_summary={},
            warnings=(),
            errors=(),
            artifacts_produced=(),
            max_concurrency=4,
            peak_concurrent_tasks=2,
        )
        d = report.as_dict()
        assert d["max_concurrency"] == 4
        assert d["peak_concurrent_tasks"] == 2


# ---------------------------------------------------------------------------
# ConcurrentMissionMetrics Tests
# ---------------------------------------------------------------------------

class TestConcurrentMissionMetrics:
    def test_metrics_from_report(self) -> None:
        report = {
            "max_concurrency": 4,
            "peak_concurrent_tasks": 3,
            "tasks_planned": 10,
            "tasks_completed": 8,
            "tasks_failed": 2,
        }
        metrics = compute_concurrent_mission_metrics(report)
        assert metrics.max_concurrency == 4
        assert metrics.peak_concurrent_tasks == 3
        assert metrics.total_tasks == 10
        assert metrics.tasks_completed == 8
        assert metrics.tasks_failed == 2
        assert metrics.parallelism_ratio == 0.75
        assert metrics.sequential_equivalent is False

    def test_metrics_sequential(self) -> None:
        report = {
            "max_concurrency": 1,
            "peak_concurrent_tasks": 1,
            "tasks_planned": 5,
            "tasks_completed": 5,
            "tasks_failed": 0,
        }
        metrics = compute_concurrent_mission_metrics(report)
        assert metrics.sequential_equivalent is True
        assert metrics.parallelism_ratio == 1.0

    def test_metrics_as_dict(self) -> None:
        report = {"max_concurrency": 2, "peak_concurrent_tasks": 2, "tasks_planned": 4, "tasks_completed": 4, "tasks_failed": 0}
        metrics = compute_concurrent_mission_metrics(report)
        d = metrics.as_dict()
        assert "max_concurrency" in d
        assert "parallelism_ratio" in d
        assert "sequential_equivalent" in d

    def test_metrics_defaults(self) -> None:
        metrics = compute_concurrent_mission_metrics({})
        assert metrics.max_concurrency == 1
        assert metrics.peak_concurrent_tasks == 0
        assert metrics.total_tasks == 0


# ---------------------------------------------------------------------------
# Dependency Ordering Tests
# ---------------------------------------------------------------------------

class TestDependencyOrdering:
    def test_dispatch_ready_blocks_dependents(self, tmp_path: Path) -> None:
        q = _make_queue(tmp_path / "q.json", [
            _make_work_item("t1"),
            _make_work_item("t2", dependencies=("t1",)),
            _make_work_item("t3", dependencies=("t1", "t2")),
        ])
        batch1 = q.dispatch_ready(max_concurrent=3)
        assert len(batch1) == 1
        assert batch1[0].task_id == "t1"

        q.mark_observed("t1")
        q.mark_verification_pending("t1")
        q.record_independent_verification("t1")
        q.mark_complete("t1")
        q.refresh()
        batch2 = q.dispatch_ready(max_concurrent=3)
        assert len(batch2) == 1
        assert batch2[0].task_id == "t2"

        q.mark_observed("t2")
        q.mark_verification_pending("t2")
        q.record_independent_verification("t2")
        q.mark_complete("t2")
        q.refresh()
        batch3 = q.dispatch_ready(max_concurrent=3)
        assert len(batch3) == 1
        assert batch3[0].task_id == "t3"

    def test_independent_tasks_dispatched_together(self, tmp_path: Path) -> None:
        q = _make_queue(tmp_path / "q.json", [
            _make_work_item("t1"),
            _make_work_item("t2"),
            _make_work_item("t3"),
        ])
        dispatched = q.dispatch_ready(max_concurrent=3)
        assert len(dispatched) == 3
        assert {d.task_id for d in dispatched} == {"t1", "t2", "t3"}


# ---------------------------------------------------------------------------
# Failure Isolation Tests
# ---------------------------------------------------------------------------

class TestFailureIsolation:
    def test_failed_task_does_not_block_independent_siblings(self, tmp_path: Path) -> None:
        q = _make_queue(tmp_path / "q.json", [
            _make_work_item("t1"),
            _make_work_item("t2"),
            _make_work_item("t3", dependencies=("t1",)),
        ])
        dispatched = q.dispatch_ready(max_concurrent=2)
        assert len(dispatched) == 2

        q.mark_failed("t1", "test error")

        q.mark_observed("t2")
        q.mark_verification_pending("t2")
        q.record_independent_verification("t2")
        q.mark_complete("t2")
        q.refresh()

        failed_ids = {"t1"}
        blocked = [tid for tid in q.summary().get("BLOCKED", [])]
        blocked_without_failed = [
            tid for tid in blocked
            if not any(d in failed_ids for d in q.get(tid).dependencies)
        ]
        assert "t3" not in blocked_without_failed

    def test_retry_after_failure(self, tmp_path: Path) -> None:
        q = _make_queue(tmp_path / "q.json", [_make_work_item("t1", max_retries=3)])
        q.dispatch_ready(max_concurrent=1)
        q.mark_failed("t1", "transient error")
        q.refresh()
        assert q.get("t1").state == "READY"
        assert q.get("t1").attempts == 1

    def test_non_retryable_stays_failed(self, tmp_path: Path) -> None:
        q = _make_queue(tmp_path / "q.json", [_make_work_item("t1", max_retries=3, retryable=False)])
        q.dispatch_ready(max_concurrent=1)
        q.mark_failed("t1", "permanent error")
        q.refresh()
        assert q.get("t1").last_error == "permanent error"


# ---------------------------------------------------------------------------
# Queue Persistence Tests
# ---------------------------------------------------------------------------

class TestQueuePersistence:
    def test_concurrent_dispatch_persists(self, tmp_path: Path) -> None:
        q = _make_queue(tmp_path / "q.json", [_make_work_item("t1"), _make_work_item("t2")])
        q.dispatch_ready(max_concurrent=2)

        q2 = _make_queue(tmp_path / "q.json", [])
        assert len(q2.items()) == 2
        assert all(item.state == "RUNNING" for item in q2.items())

    def test_dispatch_ready_increments_revision(self, tmp_path: Path) -> None:
        q = _make_queue(tmp_path / "q.json", [_make_work_item("t1")])
        initial_rev = q.state.revision
        q.dispatch_ready(max_concurrent=1)
        assert q.state.revision > initial_rev


# ---------------------------------------------------------------------------
# Duplicate Execution Prevention Tests
# ---------------------------------------------------------------------------

class TestDuplicatePrevention:
    def test_running_task_cannot_be_dispatched_again(self, tmp_path: Path) -> None:
        q = _make_queue(tmp_path / "q.json", [_make_work_item("t1")])
        q.dispatch_ready(max_concurrent=1)
        assert q.get("t1").state == "RUNNING"
        with pytest.raises(ValueError, match="already running"):
            q.transition("t1", "RUNNING", increment_attempts=True)

    def test_dispatch_ready_skips_running(self, tmp_path: Path) -> None:
        q = _make_queue(tmp_path / "q.json", [_make_work_item("t1"), _make_work_item("t2")])
        q.dispatch_ready(max_concurrent=1)
        dispatched = q.dispatch_ready(max_concurrent=1)
        assert len(dispatched) == 1
        assert dispatched[0].task_id == "t2"


# ---------------------------------------------------------------------------
# Retry Behavior Tests
# ---------------------------------------------------------------------------

class TestRetryBehavior:
    def test_retry_resets_to_ready(self, tmp_path: Path) -> None:
        q = _make_queue(tmp_path / "q.json", [_make_work_item("t1", max_retries=3)])
        q.dispatch_ready(max_concurrent=1)
        q.mark_failed("t1", "error")
        q.refresh()
        assert q.get("t1").state == "READY"
        assert q.get("t1").can_retry()

    def test_retry_exhaustion(self, tmp_path: Path) -> None:
        q = _make_queue(tmp_path / "q.json", [_make_work_item("t1", max_retries=2)])
        q.dispatch_ready(max_concurrent=1)
        q.mark_failed("t1", "error1")
        q.dispatch_ready(max_concurrent=1)
        q.mark_failed("t1", "error2")
        q.dispatch_ready(max_concurrent=1)
        q.mark_failed("t1", "error3")
        q.refresh()
        assert not q.get("t1").can_retry()


# ---------------------------------------------------------------------------
# CLI Concurrency Flag Tests
# ---------------------------------------------------------------------------

class TestCLIConcurrencyFlag:
    def test_cli_accepts_concurrency(self, tmp_path: Path, capsys) -> None:
        from argparse import Namespace
        from evosia.mission_runner_cli import cmd_run

        mission_data = _minimal_plan()
        mission_file = tmp_path / "mission.json"
        mission_file.write_text(json.dumps(mission_data), encoding="utf-8")

        runtime_root = tmp_path / "runtime"
        runtime_root.mkdir()
        (runtime_root / "evidence").mkdir()
        (runtime_root / "reviews").mkdir()
        (runtime_root / "health").mkdir()
        (runtime_root / "runs").mkdir()
        (runtime_root / "state").mkdir()

        repo = tmp_path / "repo"
        repo.mkdir()
        work = tmp_path / "work"
        work.mkdir()
        queue = tmp_path / "queue.json"

        args = Namespace(
            mission_file=str(mission_file),
            runtime_root=str(runtime_root),
            repository=str(repo),
            cwd=str(work),
            queue_file=str(queue),
            report_file=None,
            executor=None,
            plugin_dirs=[],
            mission_type=None,
            concurrency=4,
        )
        result = cmd_run(args)
        report = json.loads(capsys.readouterr().out)
        assert report["max_concurrency"] == 4


# ---------------------------------------------------------------------------
# Integration: Sequential Behavior Preservation
# ---------------------------------------------------------------------------

class TestSequentialPreservation:
    def test_max_concurrency_1_uses_sequential_path(self, tmp_path: Path) -> None:
        runner = MissionRunner(
            runtime_root=tmp_path / "runtime",
            repository=tmp_path / "repo",
            working_directory=tmp_path / "work",
            queue_path=tmp_path / "queue.json",
            max_concurrency=1,
        )
        assert runner.max_concurrency == 1

    def test_report_default_concurrency_fields(self) -> None:
        report = MissionReport(
            schema_version="1",
            mission_id="test",
            mission_title="Test",
            mission_type="generic",
            status="COMPLETED",
            started_at="2024-01-01T00:00:00Z",
            finished_at="2024-01-01T00:00:01Z",
            duration_seconds=1.0,
            tasks_planned=1,
            tasks_completed=1,
            tasks_failed=0,
            tasks_skipped=0,
            evidence_records=(),
            independent_reviews=(),
            queue_summary={},
            runtime_health="UNKNOWN",
            metrics_summary={},
            warnings=(),
            errors=(),
            artifacts_produced=(),
        )
        d = report.as_dict()
        assert d["max_concurrency"] == 1
        assert d["peak_concurrent_tasks"] == 0


# ---------------------------------------------------------------------------
# Concurrency Defect Regression Tests
# ---------------------------------------------------------------------------

class TestConcurrencyDefects:
    """Regression tests for three concurrency defects found during v0.9.4 implementation."""

    def test_reentrant_lock_no_deadlock(self, tmp_path: Path) -> None:
        """WorkQueueManager uses RLock so _replace_item can call _normalize_item
        without deadlocking.  Verify concurrent mutations from multiple threads
        complete without hanging."""
        q = _make_queue(tmp_path / "q.json", [
            _make_work_item("t1"),
            _make_work_item("t2"),
            _make_work_item("t3"),
        ])
        q.dispatch_ready(max_concurrent=3)

        errors: list[str] = []

        def mutate(task_id: str) -> None:
            try:
                q.mark_observed(task_id)
                q.mark_verification_pending(task_id)
                q.record_independent_verification(task_id)
                q.mark_complete(task_id)
            except Exception as exc:
                errors.append(f"{task_id}: {exc}")

        threads = [threading.Thread(target=mutate, args=(tid,)) for tid in ("t1", "t2", "t3")]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert not errors, f"Concurrent mutations failed: {errors}"
        assert all(t.is_alive() is False for t in threads), "Threads deadlocked"
        for tid in ("t1", "t2", "t3"):
            assert q.get(tid).state == "COMPLETE"

    def test_starvation_prevention_futures_complete(self, tmp_path: Path) -> None:
        """When the main dispatch loop has no new tasks to dispatch, it must
        yield (sleep) so pool workers can complete.  Verify futures actually
        finish instead of spinning forever."""
        plan_data = {
            "mission_id": "starvation-test",
            "title": "Starvation Test",
            "tasks": [
                {"title": "A", "command": ["true"]},
                {"title": "B", "command": ["true"]},
            ],
        }
        mission_file = tmp_path / "mission.json"
        mission_file.write_text(json.dumps(plan_data), encoding="utf-8")

        runtime_root = tmp_path / "runtime"
        for d in ["evidence", "reviews", "health", "runs", "state"]:
            (runtime_root / d).mkdir(parents=True)

        repo = tmp_path / "repo"
        repo.mkdir()
        work = tmp_path / "work"
        work.mkdir()

        runner = MissionRunner(
            runtime_root=runtime_root,
            repository=repo,
            working_directory=work,
            queue_path=tmp_path / "state" / "queue.json",
            max_concurrency=2,
        )
        report = runner.run_mission_file(mission_file)
        assert report.tasks_completed == 2
        assert report.tasks_failed == 0

    def test_retry_future_key_no_collision(self, tmp_path: Path) -> None:
        """When a task fails and retries, the new future must use a unique key
        ({task_id}:{attempts}) so it doesn't overwrite the old future entry.
        Verify both attempts are tracked independently."""
        q = _make_queue(tmp_path / "q.json", [
            _make_work_item("t1", max_retries=3),
        ])
        item = q.dispatch_ready(max_concurrent=1)[0]
        key1 = f"{item.task_id}:{item.attempts}"
        assert key1 == "t1:1"

        q.mark_failed("t1", "transient")
        q.refresh()
        item2 = q.dispatch_ready(max_concurrent=1)[0]
        key2 = f"{item2.task_id}:{item2.attempts}"
        assert key2 == "t1:2"
        assert key1 != key2, "Future keys must be unique across retries"

    def test_concurrent_runner_handles_failing_tasks(self, tmp_path: Path) -> None:
        """MissionRunner concurrent path correctly counts completed vs failed
        tasks and reports them in MissionReport."""
        plan_data = {
            "mission_id": "mixed-test",
            "title": "Mixed Results",
            "tasks": [
                {"title": "OK", "command": ["true"]},
                {"title": "FAIL", "command": ["false"]},
            ],
        }
        mission_file = tmp_path / "mission.json"
        mission_file.write_text(json.dumps(plan_data), encoding="utf-8")

        runtime_root = tmp_path / "runtime"
        for d in ["evidence", "reviews", "health", "runs", "state"]:
            (runtime_root / d).mkdir(parents=True)

        repo = tmp_path / "repo"
        repo.mkdir()
        work = tmp_path / "work"
        work.mkdir()

        runner = MissionRunner(
            runtime_root=runtime_root,
            repository=repo,
            working_directory=work,
            queue_path=tmp_path / "state" / "queue.json",
            max_concurrency=2,
        )
        report = runner.run_mission_file(mission_file)
        assert report.tasks_completed == 1
        assert report.tasks_failed == 1
        assert report.status == "PARTIAL"
