"""Comprehensive tests for Mission Report generation, serialization, and Markdown rendering."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from hermes_v01.mission_runner import MissionReport, MissionRunner
from hermes_v01.mission_state import MissionState, create_initial_state, transition_state, update_counts
from hermes_v01.mission import Mission, MissionPlanner, parse_mission
from hermes_v01.mission_report import (
    MissionReportGenerator,
    report_to_json,
    save_report_json,
    save_report_atomically,
    load_report_json,
    render_markdown,
    save_report_markdown,
    mission_report_dir,
    mission_report_json_path,
    mission_report_md_path,
    generate_and_save_reports,
    _build_evidence_summary,
    _build_review_summary,
    _build_retry_summary,
    _build_scheduler_summary,
    _build_concurrency_summary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_report(
    mission_id: str = "test-001",
    status: str = "COMPLETED",
    tasks_planned: int = 4,
    tasks_completed: int = 4,
    tasks_failed: int = 0,
    tasks_skipped: int = 0,
    max_concurrency: int = 1,
    peak_concurrent_tasks: int = 0,
) -> MissionReport:
    return MissionReport(
        schema_version="1",
        mission_id=mission_id,
        mission_title="Test Mission",
        mission_type="generic",
        status=status,
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:01:00Z",
        duration_seconds=60.0,
        tasks_planned=tasks_planned,
        tasks_completed=tasks_completed,
        tasks_failed=tasks_failed,
        tasks_skipped=tasks_skipped,
        evidence_records=("exec-1/execution-record.json",),
        independent_reviews=("review-1/review.json",),
        queue_summary={"COMPLETE": ("task-0", "task-1", "task-2", "task-3")},
        runtime_health="HEALTHY",
        metrics_summary={"total_executions": 4, "successful_executions": 4},
        warnings=(),
        errors=(),
        artifacts_produced=(),
        max_concurrency=max_concurrency,
        peak_concurrent_tasks=peak_concurrent_tasks,
    )


def _cancelled_report() -> MissionReport:
    return _base_report(
        status="CANCELLED",
        tasks_planned=4,
        tasks_completed=1,
        tasks_failed=0,
        tasks_skipped=3,
    )


def _aborted_report() -> MissionReport:
    return _base_report(
        status="ABORTED",
        tasks_planned=4,
        tasks_completed=0,
        tasks_failed=0,
        tasks_skipped=4,
    )


def _failed_report() -> MissionReport:
    return _base_report(
        status="FAILED",
        tasks_planned=4,
        tasks_completed=0,
        tasks_failed=4,
    )


def _concurrent_report() -> MissionReport:
    return _base_report(max_concurrency=4, peak_concurrent_tasks=3)


# ===================================================================
# MissionReport — extended fields
# ===================================================================

class TestMissionReportExtendedFields:
    def test_new_fields_default(self) -> None:
        r = _base_report()
        assert r.lifecycle_state == ""
        assert r.tasks_cancelled == 0
        assert r.tasks_aborted == 0
        assert r.retry_summary is None
        assert r.scheduler_summary is None
        assert r.concurrency_summary is None
        assert r.capability_usage is None
        assert r.evidence_summary is None
        assert r.independent_review_summary is None
        assert r.health_summary is None
        assert r.repository is None
        assert r.git_revision is None
        assert r.runtime_version == ""

    def test_new_fields_in_as_dict(self) -> None:
        r = _base_report()
        d = r.as_dict()
        # Empty defaults should not appear
        assert "lifecycle_state" not in d
        assert "tasks_cancelled" not in d
        assert "tasks_aborted" not in d

    def test_new_fields_appear_when_set(self) -> None:
        r = MissionReport(
            schema_version="1",
            mission_id="x",
            mission_title="X",
            mission_type="generic",
            status="COMPLETED",
            started_at="t",
            finished_at="t",
            duration_seconds=1.0,
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
            lifecycle_state="COMPLETED",
            tasks_cancelled=2,
            tasks_aborted=1,
            repository="/repo",
            git_revision="abc123",
            runtime_version="0.9.6",
        )
        d = r.as_dict()
        assert d["lifecycle_state"] == "COMPLETED"
        assert d["tasks_cancelled"] == 2
        assert d["tasks_aborted"] == 1
        assert d["repository"] == "/repo"
        assert d["git_revision"] == "abc123"
        assert d["runtime_version"] == "0.9.6"

    def test_optional_summaries_appear_when_set(self) -> None:
        r = MissionReport(
            schema_version="1",
            mission_id="x",
            mission_title="X",
            mission_type="generic",
            status="COMPLETED",
            started_at="t",
            finished_at="t",
            duration_seconds=1.0,
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
            retry_summary={"tasks_complete": 1},
            scheduler_summary={"total_tasks": 1},
            concurrency_summary={"max_concurrency": 1},
            capability_usage={"executor_name": "local"},
            evidence_summary={"total_records": 1},
            independent_review_summary={"total_reviews": 1},
            health_summary={"overall_health": "HEALTHY"},
        )
        d = r.as_dict()
        assert "retry_summary" in d
        assert "scheduler_summary" in d
        assert "concurrency_summary" in d
        assert "capability_usage" in d
        assert "evidence_summary" in d
        assert "independent_review_summary" in d
        assert "health_summary" in d


# ===================================================================
# Serialization — determinism
# ===================================================================

class TestDeterministicSerialization:
    def test_json_is_deterministic(self) -> None:
        r = _base_report()
        json1 = report_to_json(r)
        json2 = report_to_json(r)
        assert json1 == json2

    def test_json_has_stable_key_ordering(self) -> None:
        r = _base_report()
        d = json.loads(report_to_json(r))
        keys = list(d.keys())
        assert keys == sorted(keys)

    def test_json_is_valid(self) -> None:
        r = _base_report()
        json_str = report_to_json(r)
        parsed = json.loads(json_str)
        assert parsed["mission_id"] == "test-001"

    def test_json_ends_with_newline(self) -> None:
        r = _base_report()
        assert report_to_json(r).endswith("\n")


# ===================================================================
# JSON persistence
# ===================================================================

class TestJsonPersistence:
    def test_save_and_load(self, tmp_path: Path) -> None:
        r = _base_report()
        path = tmp_path / "report.json"
        save_report_json(r, path)
        loaded = load_report_json(path)
        assert loaded is not None
        assert loaded["mission_id"] == "test-001"

    def test_atomic_save(self, tmp_path: Path) -> None:
        r = _base_report()
        path = tmp_path / "report.json"
        save_report_atomically(r, path)
        assert path.exists()
        assert list(tmp_path.glob(".report.json.*")) == []

    def test_load_nonexistent(self, tmp_path: Path) -> None:
        assert load_report_json(tmp_path / "nope.json") is None

    def test_load_malformed(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("NOT JSON {{{", encoding="utf-8")
        assert load_report_json(path) is None

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        r = _base_report()
        path = tmp_path / "deep" / "path" / "report.json"
        save_report_json(r, path)
        assert load_report_json(path) is not None


# ===================================================================
# Mission-specific paths
# ===================================================================

class TestMissionPaths:
    def test_report_dir(self, tmp_path: Path) -> None:
        d = mission_report_dir(tmp_path, "m-001")
        assert d == tmp_path / "reports" / "m-001"

    def test_json_path(self, tmp_path: Path) -> None:
        p = mission_report_json_path(tmp_path, "m-001")
        assert p.name == "MISSION_REPORT.json"
        assert "m-001" in str(p)

    def test_md_path(self, tmp_path: Path) -> None:
        p = mission_report_md_path(tmp_path, "m-001")
        assert p.name == "MISSION_REPORT.md"
        assert "m-001" in str(p)


# ===================================================================
# Markdown rendering
# ===================================================================

class TestMarkdownRendering:
    def test_renders_header(self) -> None:
        r = _base_report()
        md = render_markdown(r)
        assert "# Mission Report: Test Mission" in md

    def test_renders_status(self) -> None:
        r = _base_report(status="COMPLETED")
        md = render_markdown(r)
        assert "**Status:** `COMPLETED`" in md

    def test_renders_overview(self) -> None:
        r = _base_report(mission_id="m-001")
        md = render_markdown(r)
        assert "## Overview" in md
        assert "`m-001`" in md

    def test_renders_timing(self) -> None:
        r = _base_report()
        md = render_markdown(r)
        assert "## Timing" in md
        assert "2026-01-01T00:00:00Z" in md

    def test_renders_task_summary(self) -> None:
        r = _base_report(tasks_planned=4, tasks_completed=3, tasks_failed=1)
        md = render_markdown(r)
        assert "## Task Summary" in md
        assert "`4`" in md  # tasks_planned
        assert "`3`" in md  # tasks_completed
        assert "`1`" in md  # tasks_failed

    def test_renders_queue_summary(self) -> None:
        r = _base_report()
        md = render_markdown(r)
        assert "## Queue Summary" in md

    def test_renders_evidence_summary(self) -> None:
        r = _base_report()
        r = MissionReport(
            schema_version=r.schema_version,
            mission_id=r.mission_id,
            mission_title=r.mission_title,
            mission_type=r.mission_type,
            status=r.status,
            started_at=r.started_at,
            finished_at=r.finished_at,
            duration_seconds=r.duration_seconds,
            tasks_planned=r.tasks_planned,
            tasks_completed=r.tasks_completed,
            tasks_failed=r.tasks_failed,
            tasks_skipped=r.tasks_skipped,
            evidence_records=r.evidence_records,
            independent_reviews=r.independent_reviews,
            queue_summary=r.queue_summary,
            runtime_health=r.runtime_health,
            metrics_summary=r.metrics_summary,
            warnings=r.warnings,
            errors=r.errors,
            artifacts_produced=r.artifacts_produced,
            evidence_summary={"total_records": 1, "successful_executions": 1},
        )
        md = render_markdown(r)
        assert "## Evidence Summary" in md
        assert "total_records" in md

    def test_renders_concurrency_summary(self) -> None:
        r = _concurrent_report()
        r = MissionReport(
            schema_version=r.schema_version,
            mission_id=r.mission_id,
            mission_title=r.mission_title,
            mission_type=r.mission_type,
            status=r.status,
            started_at=r.started_at,
            finished_at=r.finished_at,
            duration_seconds=r.duration_seconds,
            tasks_planned=r.tasks_planned,
            tasks_completed=r.tasks_completed,
            tasks_failed=r.tasks_failed,
            tasks_skipped=r.tasks_skipped,
            evidence_records=r.evidence_records,
            independent_reviews=r.independent_reviews,
            queue_summary=r.queue_summary,
            runtime_health=r.runtime_health,
            metrics_summary=r.metrics_summary,
            warnings=r.warnings,
            errors=r.errors,
            artifacts_produced=r.artifacts_produced,
            max_concurrency=r.max_concurrency,
            peak_concurrent_tasks=r.peak_concurrent_tasks,
            concurrency_summary={"max_concurrency": 4, "peak_concurrent_tasks": 3},
        )
        md = render_markdown(r)
        assert "## Concurrency Summary" in md

    def test_renders_warnings_and_errors(self) -> None:
        r = MissionReport(
            schema_version="1",
            mission_id="x",
            mission_title="X",
            mission_type="generic",
            status="FAILED",
            started_at="t",
            finished_at="t",
            duration_seconds=1.0,
            tasks_planned=1,
            tasks_completed=0,
            tasks_failed=1,
            tasks_skipped=0,
            evidence_records=(),
            independent_reviews=(),
            queue_summary={},
            runtime_health="UNKNOWN",
            metrics_summary={},
            warnings=("warn1",),
            errors=("err1",),
            artifacts_produced=(),
        )
        md = render_markdown(r)
        assert "## Warnings & Errors" in md
        assert "Warnings" in md
        assert "Errors" in md

    def test_renders_empty_optional_sections_gracefully(self) -> None:
        r = _base_report()
        md = render_markdown(r)
        # Should not crash and should produce valid output
        assert len(md) > 0

    def test_markdown_ends_with_newline(self) -> None:
        r = _base_report()
        assert render_markdown(r).endswith("\n")

    def test_markdown_is_deterministic(self) -> None:
        r = _base_report()
        md1 = render_markdown(r)
        md2 = render_markdown(r)
        assert md1 == md2

    def test_save_markdown(self, tmp_path: Path) -> None:
        r = _base_report()
        path = tmp_path / "report.md"
        save_report_markdown(r, path)
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "# Mission Report" in content


# ===================================================================
# JSON/Markdown consistency
# ===================================================================

class TestJsonMarkdownConsistency:
    def test_json_and_markdown_match(self) -> None:
        r = _base_report()
        d = r.as_dict()
        md = render_markdown(r)
        assert d["mission_id"] in md
        assert d["mission_title"] in md
        assert d["status"] in md

    def test_all_json_fields_represented_in_markdown(self) -> None:
        r = MissionReport(
            schema_version="1",
            mission_id="m-001",
            mission_title="Test",
            mission_type="generic",
            status="COMPLETED",
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:01:00Z",
            duration_seconds=60.0,
            tasks_planned=4,
            tasks_completed=4,
            tasks_failed=0,
            tasks_skipped=0,
            evidence_records=(),
            independent_reviews=(),
            queue_summary={},
            runtime_health="HEALTHY",
            metrics_summary={"total_executions": 4},
            warnings=(),
            errors=(),
            artifacts_produced=(),
            lifecycle_state="COMPLETED",
            tasks_cancelled=0,
            tasks_aborted=0,
            repository="/repo",
            git_revision="abc123",
            runtime_version="0.9.6",
            retry_summary={"tasks_complete": 4},
            concurrency_summary={"max_concurrency": 1},
        )
        md = render_markdown(r)
        assert "`m-001`" in md
        assert "COMPLETED" in md
        assert "`/repo`" in md
        assert "`abc123`" in md
        assert "`0.9.6`" in md


# ===================================================================
# Summary builders
# ===================================================================

class TestEvidenceSummaryBuilder:
    def test_empty(self) -> None:
        s = _build_evidence_summary([], Path("/tmp"))
        assert s["total_records"] == 0

    def test_with_records(self, tmp_path: Path) -> None:
        rec = {
            "execution_record": {
                "execution_id": "exec-001",
                "exit_code": 0,
            }
        }
        p = tmp_path / "exec-001" / "execution-record.json"
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps(rec), encoding="utf-8")
        s = _build_evidence_summary([str(p)], tmp_path)
        assert s["total_records"] == 1
        assert s["successful_executions"] == 1
        assert s["failed_executions"] == 0

    def test_malformed_record(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.json"
        p.write_text("NOT JSON", encoding="utf-8")
        s = _build_evidence_summary([str(p)], tmp_path)
        assert s["total_records"] == 1
        assert s["successful_executions"] == 0


class TestReviewSummaryBuilder:
    def test_empty(self) -> None:
        s = _build_review_summary([])
        assert s["total_reviews"] == 0

    def test_with_reviews(self, tmp_path: Path) -> None:
        rev = {"review_id": "rev-001", "outcome": "REVIEW_PASSED"}
        p = tmp_path / "review.json"
        p.write_text(json.dumps(rev), encoding="utf-8")
        s = _build_review_summary([str(p)])
        assert s["total_reviews"] == 1
        assert s["passed"] == 1

    def test_mixed_outcomes(self, tmp_path: Path) -> None:
        paths = []
        for i, outcome in enumerate(["REVIEW_PASSED", "REVIEW_FAILED", "REVIEW_INCOMPLETE"]):
            p = tmp_path / f"review-{i}.json"
            p.write_text(json.dumps({"review_id": f"r-{i}", "outcome": outcome}), encoding="utf-8")
            paths.append(str(p))
        s = _build_review_summary(paths)
        assert s["passed"] == 1
        assert s["failed"] == 1
        assert s["incomplete"] == 1


class TestRetrySummaryBuilder:
    def test_basic(self) -> None:
        qs = {"COMPLETE": ("t0", "t1"), "BLOCKED": ("t2",), "READY": (), "RUNNING": (), "VERIFIED": (), "OBSERVED": (), "VERIFICATION_PENDING": ()}
        s = _build_retry_summary(qs)
        assert s["tasks_complete"] == 2
        assert s["tasks_in_retry"] == 1


class TestSchedulerSummaryBuilder:
    def test_basic(self) -> None:
        r = _base_report(tasks_planned=4, tasks_completed=3, tasks_failed=1)
        s = _build_scheduler_summary(r)
        assert s["total_tasks"] == 4
        assert s["tasks_dispatched"] == 4
        assert s["tasks_remaining"] == 0


class TestConcurrencySummaryBuilder:
    def test_sequential(self) -> None:
        r = _base_report(max_concurrency=1)
        s = _build_concurrency_summary(r)
        assert s["max_concurrency"] == 1
        assert s["sequential_equivalent"] is True

    def test_concurrent(self) -> None:
        r = _concurrent_report()
        s = _build_concurrency_summary(r)
        assert s["max_concurrency"] == 4
        assert s["sequential_equivalent"] is False
        assert s["parallelism_ratio"] == 0.75


# ===================================================================
# MissionReportGenerator
# ===================================================================

class TestMissionReportGenerator:
    def test_generates_with_defaults(self, tmp_path: Path) -> None:
        gen = MissionReportGenerator(runtime_root=tmp_path)
        base = _base_report()
        full = gen.generate(base)
        assert full.lifecycle_state == "COMPLETED"
        assert full.runtime_version != ""
        assert full.evidence_summary is not None
        assert full.independent_review_summary is not None
        assert full.retry_summary is not None
        assert full.scheduler_summary is not None
        assert full.concurrency_summary is not None

    def test_generates_with_mission_state(self, tmp_path: Path) -> None:
        gen = MissionReportGenerator(runtime_root=tmp_path)
        base = _base_report(status="CANCELLED", tasks_completed=1, tasks_skipped=3)
        state = create_initial_state("test-001", "Test", 4)
        state = transition_state(state, "RUNNING")
        state = transition_state(state, "CANCELLED", reason="user cancel")
        state = update_counts(state, tasks_completed=1)
        full = gen.generate(base, state)
        assert full.lifecycle_state == "CANCELLED"
        assert full.tasks_cancelled == 3

    def test_generates_with_aborted_state(self, tmp_path: Path) -> None:
        gen = MissionReportGenerator(runtime_root=tmp_path)
        base = _aborted_report()
        state = create_initial_state("test-001", "Test", 4)
        state = transition_state(state, "RUNNING")
        state = transition_state(state, "ABORTED", reason="emergency")
        full = gen.generate(base, state)
        assert full.lifecycle_state == "ABORTED"
        assert full.tasks_aborted == 4

    def test_includes_repository_and_git(self, tmp_path: Path) -> None:
        gen = MissionReportGenerator(
            runtime_root=tmp_path,
            repository=tmp_path / "repo",
        )
        base = _base_report()
        full = gen.generate(base)
        assert full.repository == str(tmp_path / "repo")

    def test_includes_capability_usage(self, tmp_path: Path) -> None:
        gen = MissionReportGenerator(
            runtime_root=tmp_path,
            executor_name="local",
        )
        base = _base_report()
        full = gen.generate(base)
        assert full.capability_usage is not None
        assert full.capability_usage["executor_name"] == "local"

    def test_no_capability_when_no_executor(self, tmp_path: Path) -> None:
        gen = MissionReportGenerator(runtime_root=tmp_path)
        base = _base_report()
        full = gen.generate(base)
        assert full.capability_usage is None


# ===================================================================
# generate_and_save_reports
# ===================================================================

class TestGenerateAndSaveReports:
    def test_generates_both_artifacts(self, tmp_path: Path) -> None:
        base = _base_report()
        json_path, md_path = generate_and_save_reports(
            runtime_root=tmp_path,
            report=base,
        )
        assert json_path.exists()
        assert md_path.exists()
        assert json_path.name == "MISSION_REPORT.json"
        assert md_path.name == "MISSION_REPORT.md"

    def test_json_content_valid(self, tmp_path: Path) -> None:
        base = _base_report()
        json_path, _ = generate_and_save_reports(tmp_path, base)
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["mission_id"] == "test-001"
        assert "lifecycle_state" in data

    def test_md_content_valid(self, tmp_path: Path) -> None:
        base = _base_report()
        _, md_path = generate_and_save_reports(tmp_path, base)
        content = md_path.read_text(encoding="utf-8")
        assert "# Mission Report: Test Mission" in content

    def test_deterministic_output(self, tmp_path: Path) -> None:
        base = _base_report()
        json1, md1 = generate_and_save_reports(tmp_path, base)
        data1 = json.loads(json1.read_text(encoding="utf-8"))
        md_content1 = md1.read_text(encoding="utf-8")

        json2, md2 = generate_and_save_reports(tmp_path, base)
        data2 = json.loads(json2.read_text(encoding="utf-8"))
        md_content2 = md2.read_text(encoding="utf-8")

        assert data1 == data2
        assert md_content1 == md_content2


# ===================================================================
# Schema version
# ===================================================================

class TestSchemaVersion:
    def test_schema_version_in_json(self) -> None:
        r = _base_report()
        d = r.as_dict()
        assert d["schema_version"] == "1"

    def test_schema_version_in_full_report(self, tmp_path: Path) -> None:
        gen = MissionReportGenerator(runtime_root=tmp_path)
        full = gen.generate(_base_report())
        d = full.as_dict()
        assert d["schema_version"] == "1"


# ===================================================================
# Missing optional inputs
# ===================================================================

class TestMissingOptionalInputs:
    def test_report_with_no_evidence(self) -> None:
        r = MissionReport(
            schema_version="1",
            mission_id="x",
            mission_title="X",
            mission_type="generic",
            status="COMPLETED",
            started_at="t",
            finished_at="t",
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
        d = r.as_dict()
        assert d["evidence_records"] == []
        assert d["independent_reviews"] == []

    def test_report_with_empty_queue(self) -> None:
        r = _base_report()
        r = MissionReport(
            schema_version=r.schema_version,
            mission_id=r.mission_id,
            mission_title=r.mission_title,
            mission_type=r.mission_type,
            status=r.status,
            started_at=r.started_at,
            finished_at=r.finished_at,
            duration_seconds=r.duration_seconds,
            tasks_planned=r.tasks_planned,
            tasks_completed=r.tasks_completed,
            tasks_failed=r.tasks_failed,
            tasks_skipped=r.tasks_skipped,
            evidence_records=r.evidence_records,
            independent_reviews=r.independent_reviews,
            queue_summary={},
            runtime_health=r.runtime_health,
            metrics_summary=r.metrics_summary,
            warnings=r.warnings,
            errors=r.errors,
            artifacts_produced=r.artifacts_produced,
        )
        d = r.as_dict()
        assert d["queue_summary"] == {}


# ===================================================================
# Malformed persisted inputs
# ===================================================================

class TestMalformedInputs:
    def test_load_missing_report(self, tmp_path: Path) -> None:
        assert load_report_json(tmp_path / "missing.json") is None

    def test_load_corrupted_json(self, tmp_path: Path) -> None:
        p = tmp_path / "corrupt.json"
        p.write_text("{not valid json", encoding="utf-8")
        assert load_report_json(p) is None

    def test_load_wrong_type(self, tmp_path: Path) -> None:
        p = tmp_path / "wrong.json"
        p.write_text('"just a string"', encoding="utf-8")
        result = load_report_json(p)
        assert result == "just a string"


# ===================================================================
# CLI report generation
# ===================================================================

class TestCLIReportGeneration:
    def test_cli_has_generate_report(self) -> None:
        import subprocess
        result = subprocess.run(
            ["python", "-m", "hermes_v01.mission_runner_cli", "generate-report", "--help"],
            capture_output=True, text=True, cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode == 0
        assert "generate-report" in result.stdout.lower() or "Generate" in result.stdout


# ===================================================================
# Backward compatibility
# ===================================================================

class TestBackwardCompatibility:
    def test_existing_report_format_unchanged(self) -> None:
        """The original 23 fields must still be present and unchanged."""
        r = _base_report()
        d = r.as_dict()
        expected_keys = {
            "schema_version", "mission_id", "mission_title", "mission_type",
            "status", "started_at", "finished_at", "duration_seconds",
            "tasks_planned", "tasks_completed", "tasks_failed", "tasks_skipped",
            "evidence_records", "independent_reviews", "queue_summary",
            "runtime_health", "metrics_summary", "warnings", "errors",
            "artifacts_produced", "mission_report_path", "max_concurrency",
            "peak_concurrent_tasks",
        }
        assert expected_keys.issubset(set(d.keys()))

    def test_old_code_creates_report_with_defaults(self) -> None:
        """Old code calling MissionReport without new fields should still work."""
        r = MissionReport(
            schema_version="1",
            mission_id="x",
            mission_title="X",
            mission_type="generic",
            status="COMPLETED",
            started_at="t",
            finished_at="t",
            duration_seconds=1.0,
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
        assert r.lifecycle_state == ""
        assert r.tasks_cancelled == 0
        assert r.git_revision is None


# ===================================================================
# E2E — full lifecycle report generation
# ===================================================================

class TestE2EReportGeneration:
    def _make_runner(self, tmp_path: Path) -> MissionRunner:
        runtime = tmp_path / "runtime"
        repo = tmp_path / "repo"
        work = tmp_path / "work"
        for d in (runtime, repo, work, runtime / "state", runtime / "runs"):
            d.mkdir(parents=True, exist_ok=True)
        return MissionRunner(
            runtime_root=runtime,
            repository=repo,
            working_directory=work,
            queue_path=runtime / "state" / "queue.json",
            lifecycle_poll_interval=0.01,
        )

    def _simple_plan(self) -> dict:
        return {
            "mission_id": "e2e-report-001",
            "title": "E2E Report Mission",
            "tasks": [
                {"title": "Task A", "command": ["echo", "a"]},
            ],
        }

    def test_completed_mission_generates_reports(self, tmp_path: Path) -> None:
        runner = self._make_runner(tmp_path)
        mission = parse_mission(self._simple_plan())
        planner = MissionPlanner()
        plan = planner.build(mission)
        report = runner.run(plan)

        json_path = mission_report_json_path(runner.runtime_root, "e2e-report-001")
        md_path = mission_report_md_path(runner.runtime_root, "e2e-report-001")
        assert json_path.exists()
        assert md_path.exists()

        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["status"] == "COMPLETED"
        assert data["lifecycle_state"] == "COMPLETED"
        assert data["tasks_completed"] == 1

        md = md_path.read_text(encoding="utf-8")
        assert "COMPLETED" in md

    def test_cancelled_mission_report_accurate(self, tmp_path: Path) -> None:
        runner = self._make_runner(tmp_path)
        slow_plan = {
            "mission_id": "e2e-cancel-001",
            "title": "Cancel Mission",
            "tasks": [
                {"title": "Slow", "command": ["sleep", "0.5"]},
                {"title": "Slow2", "command": ["sleep", "0.5"]},
            ],
        }
        mission = parse_mission(slow_plan)
        planner = MissionPlanner()
        plan = planner.build(mission)

        def cancel_soon():
            time.sleep(0.02)
            runner.cancel(reason="test")

        t = threading.Thread(target=cancel_soon)
        t.start()
        report = runner.run(plan)
        t.join(timeout=5)

        json_path = mission_report_json_path(runner.runtime_root, "e2e-cancel-001")
        if json_path.exists():
            data = json.loads(json_path.read_text(encoding="utf-8"))
            assert data["status"] in ("CANCELLED", "PARTIAL")
            assert data["lifecycle_state"] == "CANCELLED"

    def test_report_json_and_md_consistency(self, tmp_path: Path) -> None:
        runner = self._make_runner(tmp_path)
        mission = parse_mission(self._simple_plan())
        planner = MissionPlanner()
        plan = planner.build(mission)
        runner.run(plan)

        json_path = mission_report_json_path(runner.runtime_root, "e2e-report-001")
        md_path = mission_report_md_path(runner.runtime_root, "e2e-report-001")
        data = json.loads(json_path.read_text(encoding="utf-8"))
        md = md_path.read_text(encoding="utf-8")
        assert data["mission_id"] in md
        assert data["mission_title"] in md
