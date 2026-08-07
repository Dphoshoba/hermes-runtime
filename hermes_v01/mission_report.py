"""Mission Report Generator and Markdown Renderer.

Builds comprehensive mission reports from runner state, MissionState, and
existing health/metrics/evidence systems.  Produces deterministic JSON and
Markdown from a single canonical model.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .mission_runner import MissionReport, save_mission_report
from .mission_state import MissionState, MissionStateStore, TERMINAL_MISSION_STATES
from .utils import utc_now_str


# ---------------------------------------------------------------------------
# Git revision helper
# ---------------------------------------------------------------------------

def _git_revision(repository: Path | None) -> str | None:
    if repository is None:
        return None
    repo = repository.expanduser().resolve()
    if not repo.exists():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except OSError:
        return None
    revision = result.stdout.strip()
    return revision if result.returncode == 0 and revision else None


# ---------------------------------------------------------------------------
# Summary builders — consume existing models
# ---------------------------------------------------------------------------

def _build_evidence_summary(evidence_paths: list[str], runtime_root: Path) -> dict[str, object]:
    """Parse evidence records and build a summary."""
    total = len(evidence_paths)
    successful = 0
    failed = 0
    execution_ids: list[str] = []
    exit_codes: list[int] = []

    for path in evidence_paths:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            record = data.get("execution_record", data)
            exit_code = record.get("exit_code")
            exec_id = record.get("execution_id")
            if exec_id:
                execution_ids.append(exec_id)
            if exit_code is not None:
                exit_codes.append(exit_code)
                if exit_code == 0:
                    successful += 1
                else:
                    failed += 1
        except (json.JSONDecodeError, KeyError, OSError):
            pass

    return {
        "total_records": total,
        "successful_executions": successful,
        "failed_executions": failed,
        "execution_ids": execution_ids,
        "exit_codes": exit_codes,
    }


def _build_review_summary(review_paths: list[str]) -> dict[str, object]:
    """Parse review records and build a summary."""
    total = len(review_paths)
    passed = 0
    failed = 0
    incomplete = 0
    review_ids: list[str] = []
    outcomes: list[str] = []

    for path in review_paths:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            outcome = data.get("outcome", "UNKNOWN")
            review_id = data.get("review_id")
            if review_id:
                review_ids.append(review_id)
            outcomes.append(outcome)
            if outcome == "REVIEW_PASSED":
                passed += 1
            elif outcome == "REVIEW_FAILED":
                failed += 1
            else:
                incomplete += 1
        except (json.JSONDecodeError, KeyError, OSError):
            pass

    return {
        "total_reviews": total,
        "passed": passed,
        "failed": failed,
        "incomplete": incomplete,
        "review_ids": review_ids,
        "outcomes": outcomes,
    }


def _build_retry_summary(work_queue_summary: dict[str, tuple[str, ...]]) -> dict[str, object]:
    """Build retry summary from queue state."""
    return {
        "tasks_in_retry": len(work_queue_summary.get("BLOCKED", ())),
        "tasks_ready": len(work_queue_summary.get("READY", ())),
        "tasks_running": len(work_queue_summary.get("RUNNING", ())),
        "tasks_complete": len(work_queue_summary.get("COMPLETE", ())),
        "tasks_verified": len(work_queue_summary.get("VERIFIED", ())),
    }


def _build_scheduler_summary(report: MissionReport) -> dict[str, object]:
    """Build scheduler summary from report fields."""
    return {
        "inter_task_delay": 0.0,
        "total_tasks": report.tasks_planned,
        "tasks_dispatched": report.tasks_completed + report.tasks_failed,
        "tasks_remaining": report.tasks_planned - report.tasks_completed - report.tasks_failed,
    }


def _build_concurrency_summary(report: MissionReport) -> dict[str, object]:
    """Build concurrency summary from report fields."""
    return {
        "max_concurrency": report.max_concurrency,
        "peak_concurrent_tasks": report.peak_concurrent_tasks,
        "parallelism_ratio": (
            round(report.peak_concurrent_tasks / report.max_concurrency, 3)
            if report.max_concurrency > 0 else 0.0
        ),
        "sequential_equivalent": report.max_concurrency <= 1,
    }


def _build_health_summary(runtime_root: Path) -> dict[str, object] | None:
    """Build health summary from existing health system."""
    try:
        from .health import build_health_report
        hr = build_health_report(runtime_root)
        return {
            "overall_health": hr.overall_health,
            "runtime_version": hr.runtime_version,
            "execution_record_count": hr.execution_record_count,
            "review_count": hr.review_count,
            "last_review_outcome": hr.last_review_outcome,
            "last_failure": hr.last_failure,
        }
    except Exception:
        return None


def _build_capability_summary(runtime_root: Path, executor_name: str | None) -> dict[str, object] | None:
    """Build capability usage summary."""
    if not executor_name:
        return None
    return {
        "executor_name": executor_name,
        "resolved": True,
    }


# ---------------------------------------------------------------------------
# MissionReportGenerator
# ---------------------------------------------------------------------------

class MissionReportGenerator:
    """Builds comprehensive MissionReport from runner state and existing systems.

    The generator is deterministic: the same inputs produce the same report.
    """

    def __init__(
        self,
        runtime_root: Path,
        repository: Path | None = None,
        executor_name: str | None = None,
    ) -> None:
        self.runtime_root = runtime_root
        self.repository = repository
        self.executor_name = executor_name

    def generate(
        self,
        base_report: MissionReport,
        mission_state: MissionState | None = None,
    ) -> MissionReport:
        """Enrich a base MissionReport with lifecycle, evidence, review, and
        health summaries.  Returns a new MissionReport with all fields populated."""
        runtime_root = self.runtime_root
        repo_str = str(self.repository) if self.repository else None
        git_rev = _git_revision(self.repository)

        # Lifecycle state from MissionState
        lifecycle_state = mission_state.state if mission_state else base_report.status
        tasks_cancelled = 0
        tasks_aborted = 0
        if mission_state:
            if mission_state.state == "CANCELLED":
                tasks_cancelled = mission_state.tasks_remaining
            elif mission_state.state == "ABORTED":
                tasks_aborted = mission_state.tasks_remaining

        # Evidence summary
        evidence_summary = _build_evidence_summary(
            list(base_report.evidence_records), runtime_root,
        )

        # Review summary
        independent_review_summary = _build_review_summary(
            list(base_report.independent_reviews),
        )

        # Retry summary
        retry_summary = _build_retry_summary(
            {k: tuple(v) if isinstance(v, list) else v
             for k, v in base_report.queue_summary.items()}
        )

        # Scheduler summary
        scheduler_summary = _build_scheduler_summary(base_report)

        # Concurrency summary
        concurrency_summary = _build_concurrency_summary(base_report)

        # Health summary
        health_summary = _build_health_summary(runtime_root)

        # Capability usage
        capability_usage = _build_capability_summary(runtime_root, self.executor_name)

        # Runtime version
        try:
            from . import __version__
            runtime_version = __version__
        except ImportError:
            runtime_version = ""

        # Determine status mapping for lifecycle
        status = base_report.status
        if mission_state and mission_state.state in TERMINAL_MISSION_STATES:
            if mission_state.state == "COMPLETED":
                status = "COMPLETED"
            elif mission_state.state == "CANCELLED":
                status = "CANCELLED" if base_report.tasks_completed == 0 else "PARTIAL"
            elif mission_state.state == "ABORTED":
                status = "ABORTED" if base_report.tasks_completed == 0 else "PARTIAL"
            elif mission_state.state == "FAILED":
                status = "FAILED"

        return MissionReport(
            schema_version=base_report.schema_version,
            mission_id=base_report.mission_id,
            mission_title=base_report.mission_title,
            mission_type=base_report.mission_type,
            status=status,
            started_at=base_report.started_at,
            finished_at=base_report.finished_at,
            duration_seconds=base_report.duration_seconds,
            tasks_planned=base_report.tasks_planned,
            tasks_completed=base_report.tasks_completed,
            tasks_failed=base_report.tasks_failed,
            tasks_skipped=base_report.tasks_skipped,
            evidence_records=base_report.evidence_records,
            independent_reviews=base_report.independent_reviews,
            queue_summary=base_report.queue_summary,
            runtime_health=base_report.runtime_health,
            metrics_summary=base_report.metrics_summary,
            warnings=base_report.warnings,
            errors=base_report.errors,
            artifacts_produced=base_report.artifacts_produced,
            mission_report_path=base_report.mission_report_path,
            max_concurrency=base_report.max_concurrency,
            peak_concurrent_tasks=base_report.peak_concurrent_tasks,
            lifecycle_state=lifecycle_state,
            tasks_cancelled=tasks_cancelled,
            tasks_aborted=tasks_aborted,
            retry_summary=retry_summary,
            scheduler_summary=scheduler_summary,
            concurrency_summary=concurrency_summary,
            capability_usage=capability_usage,
            evidence_summary=evidence_summary,
            independent_review_summary=independent_review_summary,
            health_summary=health_summary,
            repository=repo_str,
            git_revision=git_rev,
            runtime_version=runtime_version,
        )


# ---------------------------------------------------------------------------
# Deterministic serialization
# ---------------------------------------------------------------------------

def report_to_json(report: MissionReport, indent: int = 2) -> str:
    """Serialize a MissionReport to deterministic JSON with stable key ordering."""
    return json.dumps(report.as_dict(), indent=indent, sort_keys=True, ensure_ascii=False) + "\n"


def save_report_json(report: MissionReport, path: Path) -> None:
    """Write MissionReport as deterministic JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report_to_json(report), encoding="utf-8")


def save_report_atomically(report: MissionReport, path: Path) -> None:
    """Atomic write: temp → fsync → os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(report_to_json(report))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def load_report_json(path: Path) -> dict | None:
    """Load a report JSON file. Returns None on any parse error."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# Mission-specific report path
# ---------------------------------------------------------------------------

def mission_report_dir(runtime_root: Path, mission_id: str) -> Path:
    """Deterministic path for a mission's reports."""
    return runtime_root / "reports" / mission_id


def mission_report_json_path(runtime_root: Path, mission_id: str) -> Path:
    return mission_report_dir(runtime_root, mission_id) / "MISSION_REPORT.json"


def mission_report_md_path(runtime_root: Path, mission_id: str) -> Path:
    return mission_report_dir(runtime_root, mission_id) / "MISSION_REPORT.md"


# ---------------------------------------------------------------------------
# Markdown renderer — single source of truth from MissionReport.as_dict()
# ---------------------------------------------------------------------------

def render_markdown(report: MissionReport) -> str:
    """Render a MissionReport as GitHub-flavored Markdown.

    Generated from report.as_dict() — the same model as the JSON artifact.
    """
    d = report.as_dict()
    lines: list[str] = []

    def _h(level: int, text: str) -> None:
        lines.append(f"{'#' * level} {text}")

    def _field(label: str, value: object) -> None:
        if value is None or value == "" or value == [] or value == {}:
            lines.append(f"- **{label}:** _n/a_")
        elif isinstance(value, bool):
            lines.append(f"- **{label}:** {'yes' if value else 'no'}")
        elif isinstance(value, list):
            if len(value) == 0:
                lines.append(f"- **{label}:** _none_")
            else:
                lines.append(f"- **{label}:** {len(value)} items")
        elif isinstance(value, dict):
            if not value:
                lines.append(f"- **{label}:** _empty_")
            else:
                lines.append(f"- **{label}:**")
                for k in sorted(value.keys()):
                    v = value[k]
                    if isinstance(v, list):
                        lines.append(f"  - `{k}`: {len(v)} items")
                    else:
                        lines.append(f"  - `{k}`: `{v}`")
        else:
            lines.append(f"- **{label}:** `{value}`")

    # Header
    _h(1, f"Mission Report: {d.get('mission_title', d.get('mission_id', ''))}")
    lines.append("")

    # Status banner
    status = d.get("status", "UNKNOWN")
    lines.append(f"> **Status:** `{status}`")
    lines.append("")

    # Overview
    _h(2, "Overview")
    _field("Mission ID", d.get("mission_id"))
    _field("Mission Type", d.get("mission_type"))
    _field("Schema Version", d.get("schema_version"))
    _field("Lifecycle State", d.get("lifecycle_state"))
    _field("Runtime Version", d.get("runtime_version"))
    _field("Repository", d.get("repository"))
    _field("Git Revision", d.get("git_revision"))
    lines.append("")

    # Timing
    _h(2, "Timing")
    _field("Started At", d.get("started_at"))
    _field("Finished At", d.get("finished_at"))
    _field("Duration (seconds)", d.get("duration_seconds"))
    lines.append("")

    # Task Summary
    _h(2, "Task Summary")
    _field("Tasks Planned", d.get("tasks_planned"))
    _field("Tasks Completed", d.get("tasks_completed"))
    _field("Tasks Failed", d.get("tasks_failed"))
    _field("Tasks Skipped", d.get("tasks_skipped"))
    _field("Tasks Cancelled", d.get("tasks_cancelled"))
    _field("Tasks Aborted", d.get("tasks_aborted"))
    lines.append("")

    # Queue Summary
    qs = d.get("queue_summary", {})
    if qs:
        _h(2, "Queue Summary")
        for state_name in sorted(qs.keys()):
            task_ids = qs[state_name]
            if task_ids:
                _field(state_name, task_ids)
        lines.append("")

    # Retry Summary
    rs = d.get("retry_summary")
    if rs:
        _h(2, "Retry Summary")
        for k in sorted(rs.keys()):
            _field(k, rs[k])
        lines.append("")

    # Scheduler Summary
    ss = d.get("scheduler_summary")
    if ss:
        _h(2, "Scheduler Summary")
        for k in sorted(ss.keys()):
            _field(k, ss[k])
        lines.append("")

    # Concurrency Summary
    cs = d.get("concurrency_summary")
    if cs:
        _h(2, "Concurrency Summary")
        for k in sorted(cs.keys()):
            _field(k, cs[k])
        lines.append("")

    # Capability Usage
    cu = d.get("capability_usage")
    if cu:
        _h(2, "Capability Usage")
        for k in sorted(cu.keys()):
            _field(k, cu[k])
        lines.append("")

    # Evidence Summary
    es = d.get("evidence_summary")
    if es:
        _h(2, "Evidence Summary")
        for k in sorted(es.keys()):
            v = es[k]
            if isinstance(v, list):
                _field(k, v)
            else:
                _field(k, v)
        lines.append("")

    # Independent Review Summary
    irs = d.get("independent_review_summary")
    if irs:
        _h(2, "Independent Review Summary")
        for k in sorted(irs.keys()):
            v = irs[k]
            if isinstance(v, list):
                _field(k, v)
            else:
                _field(k, v)
        lines.append("")

    # Health Summary
    hs = d.get("health_summary")
    if hs:
        _h(2, "Health Summary")
        for k in sorted(hs.keys()):
            _field(k, hs[k])
        lines.append("")

    # Artifacts
    _h(2, "Artifacts")
    artifacts = d.get("artifacts_produced", [])
    evidence = d.get("evidence_records", [])
    reviews = d.get("independent_reviews", [])
    _field("Artifacts Produced", artifacts)
    _field("Evidence Records", evidence)
    _field("Independent Reviews", reviews)
    lines.append("")

    # Warnings & Errors
    warnings = d.get("warnings", [])
    errors = d.get("errors", [])
    if warnings or errors:
        _h(2, "Warnings & Errors")
        if warnings:
            _field("Warnings", warnings)
        if errors:
            _field("Errors", errors)
        lines.append("")

    # Metrics Summary
    ms = d.get("metrics_summary", {})
    if ms:
        _h(2, "Metrics Summary")
        for k in sorted(ms.keys()):
            _field(k, ms[k])
        lines.append("")

    return "\n".join(lines) + "\n"


def save_report_markdown(report: MissionReport, path: Path) -> None:
    """Write MissionReport as Markdown."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(report), encoding="utf-8")


# ---------------------------------------------------------------------------
# High-level: generate and persist both artifacts
# ---------------------------------------------------------------------------

def generate_and_save_reports(
    runtime_root: Path,
    report: MissionReport,
    mission_state: MissionState | None = None,
    repository: Path | None = None,
    executor_name: str | None = None,
) -> tuple[Path, Path]:
    """Generate comprehensive report, save JSON + Markdown, return paths."""
    generator = MissionReportGenerator(
        runtime_root=runtime_root,
        repository=repository,
        executor_name=executor_name,
    )
    full_report = generator.generate(report, mission_state)

    json_path = mission_report_json_path(runtime_root, full_report.mission_id)
    md_path = mission_report_md_path(runtime_root, full_report.mission_id)

    save_report_atomically(full_report, json_path)
    save_report_markdown(full_report, md_path)

    return json_path, md_path
