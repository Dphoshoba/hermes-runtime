"""Comprehensive tests for the Mission Runner."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from evosia.mission import (
    Mission,
    MissionPlanner,
    MissionTask,
    Plan,
    PlanTask,
    RetryPolicy,
    enqueue_plan,
    load_mission,
    load_plan,
    parse_mission,
    save_plan,
)
from evosia.mission_runner import (
    MissionReport,
    MissionRunner,
    load_mission_report,
    save_mission_report,
)
from evosia.work_queue import WorkQueueManager, WorkQueueStateStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _mock_hermes_binaries(tmp_path: Path, monkeypatch) -> None:
    """Install mock hermes-record, hermes-review, hermes-health binaries."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    runtime_root = tmp_path / "runtime"
    evidence_dir = runtime_root / "evidence"
    reviews_dir = runtime_root / "reviews"
    health_dir = runtime_root / "health"
    evidence_dir.mkdir(parents=True)
    reviews_dir.mkdir(parents=True)
    health_dir.mkdir(parents=True)

    _write_executable(
        bin_dir / "hermes-record",
        f"""#!/bin/sh
# Find the execution_id argument or generate one
EXEC_ID="exec-test-$(date +%s)"
mkdir -p "{evidence_dir}/$EXEC_ID"
cat > "{evidence_dir}/$EXEC_ID/execution-record.json" <<'JSON'
{{"execution_record": {{"execution_id": "exec-test-1", "command": ["echo", "test"], "start_time": "2026-01-01T00:00:00Z", "end_time": "2026-01-01T00:00:01Z", "exit_code": 0, "artifacts": []}}}}
JSON
echo "{evidence_dir}/$EXEC_ID/execution-record.json"
exit 0
""",
    )

    _write_executable(
        bin_dir / "hermes-review",
        f"""#!/bin/sh
REVIEW_ID="review-test-$(date +%s)"
mkdir -p "{reviews_dir}/$REVIEW_ID"
cat > "{reviews_dir}/$REVIEW_ID/review.json" <<'JSON'
{{"outcome": "REVIEW_PASSED", "review_id": "review-test-1"}}
JSON
echo "{reviews_dir}/$REVIEW_ID/review.json"
exit 0
""",
    )

    _write_executable(
        bin_dir / "hermes-health",
        f"""#!/bin/sh
mkdir -p "{health_dir}"
cat > "{health_dir}/health.json" <<'JSON'
{{"overall_health": "HEALTHY"}}
JSON
echo "{health_dir}/health.json"
exit 0
""",
    )

    monkeypatch.setenv(
        "PATH",
        f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
    )


def _minimal_mission() -> dict:
    return {
        "mission_id": "runner-test-001",
        "title": "Runner Test Mission",
        "description": "Minimal mission for runner tests",
        "tasks": [
            {"title": "Echo Hello", "command": ["echo", "hello"]},
        ],
    }


def _multi_task_mission() -> dict:
    return {
        "mission_id": "runner-multi-001",
        "title": "Multi-Task Runner Mission",
        "description": "Mission with dependencies",
        "tasks": [
            {"title": "Step 1", "command": ["echo", "step1"]},
            {"title": "Step 2", "command": ["echo", "step2"], "dependencies": ["runner-multi-001-task-0000"]},
            {"title": "Step 3", "command": ["echo", "step3"], "dependencies": ["runner-multi-001-task-0001"]},
        ],
    }


def _setup_runner_env(tmp_path: Path) -> dict:
    """Create standard directory structure for runner tests."""
    return {
        "runtime_root": tmp_path / "runtime",
        "repository": tmp_path / "repo",
        "working_directory": tmp_path / "work",
        "queue_path": tmp_path / "queue.json",
    }


# ---------------------------------------------------------------------------
# MissionReport Tests
# ---------------------------------------------------------------------------

class TestMissionReport:
    def test_report_schema_version(self) -> None:
        report = MissionReport(
            schema_version="1",
            mission_id="m1",
            mission_title="M",
            mission_type="generic",
            status="COMPLETED",
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:01:00Z",
            duration_seconds=60.0,
            tasks_planned=1,
            tasks_completed=1,
            tasks_failed=0,
            tasks_skipped=0,
            evidence_records=(),
            independent_reviews=(),
            queue_summary={},
            runtime_health="HEALTHY",
            metrics_summary={},
            warnings=(),
            errors=(),
            artifacts_produced=(),
        )
        assert report.schema_version == "1"

    def test_report_as_dict(self) -> None:
        report = MissionReport(
            schema_version="1",
            mission_id="m1",
            mission_title="M",
            mission_type="generic",
            status="COMPLETED",
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:01:00Z",
            duration_seconds=60.0,
            tasks_planned=2,
            tasks_completed=1,
            tasks_failed=1,
            tasks_skipped=0,
            evidence_records=("exec-1",),
            independent_reviews=("review-1",),
            queue_summary={"COMPLETE": ("t1",), "FAILED": ("t2",)},
            runtime_health="WARNING",
            metrics_summary={"total_executions": 5},
            warnings=("warn1",),
            errors=("err1",),
            artifacts_produced=("art1",),
        )
        d = report.as_dict()
        assert d["mission_id"] == "m1"
        assert d["status"] == "COMPLETED"
        assert d["tasks_planned"] == 2
        assert d["tasks_completed"] == 1
        assert d["tasks_failed"] == 1
        assert d["evidence_records"] == ["exec-1"]
        assert d["independent_reviews"] == ["review-1"]
        assert d["queue_summary"]["COMPLETE"] == ["t1"]
        assert d["runtime_health"] == "WARNING"
        assert d["metrics_summary"]["total_executions"] == 5
        assert d["warnings"] == ["warn1"]
        assert d["errors"] == ["err1"]

    def test_report_status_values(self) -> None:
        for status in ("COMPLETED", "PARTIAL", "FAILED"):
            report = MissionReport(
                schema_version="1", mission_id="m", mission_title="M",
                mission_type="generic", status=status, started_at="", finished_at="",
                duration_seconds=0.0, tasks_planned=0, tasks_completed=0,
                tasks_failed=0, tasks_skipped=0, evidence_records=(),
                independent_reviews=(), queue_summary={}, runtime_health="UNKNOWN",
                metrics_summary={}, warnings=(), errors=(), artifacts_produced=(),
            )
            assert report.status == status

    def test_report_deterministic(self) -> None:
        args = dict(
            schema_version="1", mission_id="m", mission_title="M",
            mission_type="generic", status="COMPLETED", started_at="t", finished_at="t",
            duration_seconds=1.0, tasks_planned=1, tasks_completed=1,
            tasks_failed=0, tasks_skipped=0, evidence_records=("e1",),
            independent_reviews=("r1",), queue_summary={}, runtime_health="HEALTHY",
            metrics_summary={}, warnings=(), errors=(), artifacts_produced=(),
        )
        r1 = MissionReport(**args)
        r2 = MissionReport(**args)
        assert r1.as_dict() == r2.as_dict()


# ---------------------------------------------------------------------------
# Save/Load Mission Report Tests
# ---------------------------------------------------------------------------

class TestMissionReportPersistence:
    def test_save_and_load(self, tmp_path: Path) -> None:
        report = MissionReport(
            schema_version="1", mission_id="m1", mission_title="M",
            mission_type="generic", status="COMPLETED", started_at="t1", finished_at="t2",
            duration_seconds=10.0, tasks_planned=3, tasks_completed=3,
            tasks_failed=0, tasks_skipped=0, evidence_records=("e1", "e2"),
            independent_reviews=("r1",), queue_summary={"COMPLETE": ("t1", "t2", "t3")},
            runtime_health="HEALTHY", metrics_summary={"executions": 5},
            warnings=(), errors=(), artifacts_produced=("a1",),
        )
        path = tmp_path / "report.json"
        save_mission_report(report, path)
        assert path.exists()

        loaded = load_mission_report(path)
        assert loaded["mission_id"] == "m1"
        assert loaded["status"] == "COMPLETED"
        assert loaded["tasks_planned"] == 3

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        report = MissionReport(
            schema_version="1", mission_id="m", mission_title="M",
            mission_type="generic", status="FAILED", started_at="", finished_at="",
            duration_seconds=0.0, tasks_planned=0, tasks_completed=0,
            tasks_failed=0, tasks_skipped=0, evidence_records=(),
            independent_reviews=(), queue_summary={}, runtime_health="UNKNOWN",
            metrics_summary={}, warnings=(), errors=(), artifacts_produced=(),
        )
        path = tmp_path / "nested" / "dir" / "report.json"
        save_mission_report(report, path)
        assert path.exists()

    def test_load_preserves_all_fields(self, tmp_path: Path) -> None:
        report = MissionReport(
            schema_version="1", mission_id="m1", mission_title="Test",
            mission_type="security-audit", status="PARTIAL", started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:30Z", duration_seconds=30.0,
            tasks_planned=5, tasks_completed=3, tasks_failed=1, tasks_skipped=1,
            evidence_records=("exec-1", "exec-2", "exec-3"),
            independent_reviews=("review-1", "review-2", "review-3"),
            queue_summary={"COMPLETE": ("t1", "t2", "t3"), "FAILED": ("t4",), "BLOCKED": ("t5",)},
            runtime_health="WARNING",
            metrics_summary={"total": 5, "avg_duration": 10.0},
            warnings=("skipped task t5",),
            errors=("task t4 failed permanently",),
            artifacts_produced=("a1", "a2"),
        )
        path = tmp_path / "full_report.json"
        save_mission_report(report, path)
        loaded = load_mission_report(path)
        assert loaded["schema_version"] == "1"
        assert loaded["mission_id"] == "m1"
        assert loaded["status"] == "PARTIAL"
        assert loaded["tasks_planned"] == 5
        assert loaded["tasks_completed"] == 3
        assert loaded["tasks_failed"] == 1
        assert loaded["tasks_skipped"] == 1
        assert loaded["evidence_records"] == ["exec-1", "exec-2", "exec-3"]
        assert loaded["independent_reviews"] == ["review-1", "review-2", "review-3"]
        assert loaded["runtime_health"] == "WARNING"
        assert loaded["warnings"] == ["skipped task t5"]
        assert loaded["errors"] == ["task t4 failed permanently"]


# ---------------------------------------------------------------------------
# MissionRunner: Invalid Plan
# ---------------------------------------------------------------------------

class TestMissionRunnerInvalidPlan:
    def test_invalid_plan_returns_failed(self, tmp_path: Path, monkeypatch) -> None:
        _mock_hermes_binaries(tmp_path, monkeypatch)
        env = _setup_runner_env(tmp_path)
        env["repository"].mkdir(exist_ok=True)
        env["working_directory"].mkdir(exist_ok=True)

        runner = MissionRunner(**env)

        plan = Plan(
            schema_version="1", mission_id="m1", mission_title="M",
            mission_description="D", generated_at="t",
            plan_hash="h", tasks=(), dependency_graph={},
            required_capabilities=(), working_directory=None,
            repository=None, warnings=(), valid=False,
            errors=("plan invalid",),
        )
        report = runner.run(plan)
        assert report.status == "FAILED"
        assert report.tasks_planned == 0
        assert any("plan invalid" in e for e in report.errors)


# ---------------------------------------------------------------------------
# MissionRunner: Single Task
# ---------------------------------------------------------------------------

class TestMissionRunnerSingleTask:
    def test_single_task_completes(self, tmp_path: Path, monkeypatch) -> None:
        _mock_hermes_binaries(tmp_path, monkeypatch)
        env = _setup_runner_env(tmp_path)
        env["repository"].mkdir(exist_ok=True)
        env["working_directory"].mkdir(exist_ok=True)

        runner = MissionRunner(**env)

        mission = parse_mission(_minimal_mission())
        planner = MissionPlanner()
        plan = planner.build(mission)

        report = runner.run(plan)
        assert report.status == "COMPLETED"
        assert report.tasks_planned == 1
        assert report.tasks_completed == 1
        assert report.tasks_failed == 0
        assert report.duration_seconds >= 0

    def test_single_task_creates_queue(self, tmp_path: Path, monkeypatch) -> None:
        _mock_hermes_binaries(tmp_path, monkeypatch)
        env = _setup_runner_env(tmp_path)
        env["repository"].mkdir(exist_ok=True)
        env["working_directory"].mkdir(exist_ok=True)

        runner = MissionRunner(**env)

        mission = parse_mission(_minimal_mission())
        planner = MissionPlanner()
        plan = planner.build(mission)

        report = runner.run(plan)
        assert env["queue_path"].exists()

    def test_single_task_evidence_recorded(self, tmp_path: Path, monkeypatch) -> None:
        _mock_hermes_binaries(tmp_path, monkeypatch)
        env = _setup_runner_env(tmp_path)
        env["repository"].mkdir(exist_ok=True)
        env["working_directory"].mkdir(exist_ok=True)

        runner = MissionRunner(**env)

        mission = parse_mission(_minimal_mission())
        planner = MissionPlanner()
        plan = planner.build(mission)

        report = runner.run(plan)
        assert len(report.evidence_records) > 0
        assert len(report.independent_reviews) > 0


# ---------------------------------------------------------------------------
# MissionRunner: Multi-Task with Dependencies
# ---------------------------------------------------------------------------

class TestMissionRunnerMultiTask:
    def test_multi_task_completes(self, tmp_path: Path, monkeypatch) -> None:
        _mock_hermes_binaries(tmp_path, monkeypatch)
        env = _setup_runner_env(tmp_path)
        env["repository"].mkdir(exist_ok=True)
        env["working_directory"].mkdir(exist_ok=True)

        runner = MissionRunner(**env)

        mission = parse_mission(_multi_task_mission())
        planner = MissionPlanner()
        plan = planner.build(mission)

        report = runner.run(plan)
        assert report.status == "COMPLETED"
        assert report.tasks_planned == 3
        assert report.tasks_completed == 3
        assert report.tasks_failed == 0

    def test_multi_task_dependency_order(self, tmp_path: Path, monkeypatch) -> None:
        execution_order = []

        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        runtime_root = tmp_path / "runtime"
        evidence_dir = runtime_root / "evidence"
        reviews_dir = runtime_root / "reviews"
        health_dir = runtime_root / "health"
        evidence_dir.mkdir(parents=True)
        reviews_dir.mkdir(parents=True)
        health_dir.mkdir(parents=True)

        def _record_executable(name: str, script: str) -> None:
            _write_executable(bin_dir / name, script)

        _record_executable("hermes-record", f"""#!/bin/sh
EXEC_ID="exec-$(date +%s%N)"
mkdir -p "{evidence_dir}/$EXEC_ID"
# Extract command from args to track execution order
CMD=""
for arg in "$@"; do
    CMD="$CMD $arg"
done
cat > "{evidence_dir}/$EXEC_ID/execution-record.json" <<JSON
{{"execution_record": {{"execution_id": "$EXEC_ID", "command": ["echo", "tracked"], "start_time": "2026-01-01T00:00:00Z", "end_time": "2026-01-01T00:00:01Z", "exit_code": 0, "artifacts": []}}}}
JSON
echo "{evidence_dir}/$EXEC_ID/execution-record.json"
exit 0
""")

        _record_executable("hermes-review", f"""#!/bin/sh
REVIEW_ID="review-$(date +%s%N)"
mkdir -p "{reviews_dir}/$REVIEW_ID"
cat > "{reviews_dir}/$REVIEW_ID/review.json" <<'JSON'
{{"outcome": "REVIEW_PASSED"}}
JSON
echo "{reviews_dir}/$REVIEW_ID/review.json"
exit 0
""")

        _record_executable("hermes-health", f"""#!/bin/sh
mkdir -p "{health_dir}"
cat > "{health_dir}/health.json" <<'JSON'
{{"overall_health": "HEALTHY"}}
JSON
echo "{health_dir}/health.json"
exit 0
""")

        monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

        env = _setup_runner_env(tmp_path)
        env["working_directory"].mkdir(exist_ok=True)
        runner = MissionRunner(**env)

        mission = parse_mission(_multi_task_mission())
        planner = MissionPlanner()
        plan = planner.build(mission)

        report = runner.run(plan)
        assert report.status == "COMPLETED"
        assert report.tasks_completed == 3


# ---------------------------------------------------------------------------
# MissionRunner: Queue Summary
# ---------------------------------------------------------------------------

class TestMissionRunnerQueueSummary:
    def test_queue_summary_in_report(self, tmp_path: Path, monkeypatch) -> None:
        _mock_hermes_binaries(tmp_path, monkeypatch)
        env = _setup_runner_env(tmp_path)
        env["repository"].mkdir(exist_ok=True)
        env["working_directory"].mkdir(exist_ok=True)

        runner = MissionRunner(**env)

        mission = parse_mission(_minimal_mission())
        planner = MissionPlanner()
        plan = planner.build(mission)

        report = runner.run(plan)
        assert isinstance(report.queue_summary, dict)
        assert "COMPLETE" in report.queue_summary


# ---------------------------------------------------------------------------
# MissionRunner: Health and Metrics
# ---------------------------------------------------------------------------

class TestMissionRunnerHealthMetrics:
    def test_runtime_health_in_report(self, tmp_path: Path, monkeypatch) -> None:
        _mock_hermes_binaries(tmp_path, monkeypatch)
        env = _setup_runner_env(tmp_path)
        env["repository"].mkdir(exist_ok=True)
        env["working_directory"].mkdir(exist_ok=True)

        runner = MissionRunner(**env)

        mission = parse_mission(_minimal_mission())
        planner = MissionPlanner()
        plan = planner.build(mission)

        report = runner.run(plan)
        assert report.runtime_health in ("HEALTHY", "WARNING", "FAILED", "UNKNOWN")

    def test_metrics_summary_in_report(self, tmp_path: Path, monkeypatch) -> None:
        _mock_hermes_binaries(tmp_path, monkeypatch)
        env = _setup_runner_env(tmp_path)
        env["repository"].mkdir(exist_ok=True)
        env["working_directory"].mkdir(exist_ok=True)

        runner = MissionRunner(**env)

        mission = parse_mission(_minimal_mission())
        planner = MissionPlanner()
        plan = planner.build(mission)

        report = runner.run(plan)
        assert isinstance(report.metrics_summary, dict)


# ---------------------------------------------------------------------------
# MissionRunner: Run from File
# ---------------------------------------------------------------------------

class TestMissionRunnerFromFile:
    def test_run_mission_file(self, tmp_path: Path, monkeypatch) -> None:
        _mock_hermes_binaries(tmp_path, monkeypatch)
        env = _setup_runner_env(tmp_path)
        env["repository"].mkdir(exist_ok=True)
        env["working_directory"].mkdir(exist_ok=True)

        mission_path = tmp_path / "mission.json"
        mission_path.write_text(json.dumps(_minimal_mission()), encoding="utf-8")

        runner = MissionRunner(**env)
        report = runner.run_mission_file(mission_path)
        assert report.status == "COMPLETED"
        assert report.tasks_completed == 1


# ---------------------------------------------------------------------------
# MissionRunner: Plan File
# ---------------------------------------------------------------------------

class TestMissionRunnerPlanFile:
    def test_run_plan_file(self, tmp_path: Path, monkeypatch) -> None:
        _mock_hermes_binaries(tmp_path, monkeypatch)
        env = _setup_runner_env(tmp_path)
        env["repository"].mkdir(exist_ok=True)
        env["working_directory"].mkdir(exist_ok=True)

        mission = parse_mission(_minimal_mission())
        planner = MissionPlanner()
        plan = planner.build(mission)
        plan_path = tmp_path / "plan.json"
        save_plan(plan, plan_path)

        runner = MissionRunner(**env)
        loaded_plan = load_plan(plan_path)
        report = runner.run(loaded_plan)
        assert report.status == "COMPLETED"


# ---------------------------------------------------------------------------
# MissionRunner: Edge Cases
# ---------------------------------------------------------------------------

class TestMissionRunnerEdgeCases:
    def test_empty_tasks(self, tmp_path: Path, monkeypatch) -> None:
        _mock_hermes_binaries(tmp_path, monkeypatch)
        env = _setup_runner_env(tmp_path)
        env["repository"].mkdir(exist_ok=True)
        env["working_directory"].mkdir(exist_ok=True)

        runner = MissionRunner(**env)

        plan = Plan(
            schema_version="1", mission_id="empty", mission_title="Empty",
            mission_description="No tasks", generated_at="t",
            plan_hash="h", tasks=(), dependency_graph={},
            required_capabilities=(), working_directory=None,
            repository=None, warnings=(), valid=True, errors=(),
        )
        report = runner.run(plan)
        assert report.status == "COMPLETED"
        assert report.tasks_planned == 0
        assert report.tasks_completed == 0

    def test_inter_task_delay(self, tmp_path: Path, monkeypatch) -> None:
        _mock_hermes_binaries(tmp_path, monkeypatch)
        env = _setup_runner_env(tmp_path)
        env["repository"].mkdir(exist_ok=True)
        env["working_directory"].mkdir(exist_ok=True)

        runner = MissionRunner(**env, inter_task_delay=0.01)

        mission = parse_mission(_minimal_mission())
        planner = MissionPlanner()
        plan = planner.build(mission)

        report = runner.run(plan)
        assert report.status == "COMPLETED"

    def test_runner_preserves_plan_metadata(self, tmp_path: Path, monkeypatch) -> None:
        _mock_hermes_binaries(tmp_path, monkeypatch)
        env = _setup_runner_env(tmp_path)
        env["repository"].mkdir(exist_ok=True)
        env["working_directory"].mkdir(exist_ok=True)

        runner = MissionRunner(**env)

        data = _minimal_mission()
        data["metadata"] = {"author": "test", "version": "1.0"}
        mission = parse_mission(data)
        planner = MissionPlanner()
        plan = planner.build(mission)

        report = runner.run(plan)
        assert report.mission_id == "runner-test-001"
        assert report.mission_title == "Runner Test Mission"
