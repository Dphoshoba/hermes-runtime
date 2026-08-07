from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .work_queue import WorkQueueManager, WorkQueueStateStore
from .mission import Plan, load_plan, enqueue_plan
from .runtime import run_pipeline
from .capabilities import CapabilityManager, CapabilityRegistry, ExecutorPlugin
from .health import build_health_report
from .metrics import compute_queue_metrics, compute_runtime_metrics
from .mission_types import MissionTypeRegistry, register_built_in_types
from .mission_state import (
    MissionState,
    MissionStateStore,
    create_initial_state,
    transition_state,
    update_counts,
    TERMINAL_MISSION_STATES,
)
from .mission_control import MissionControlStore, MissionControlCommand, CONTROL_ACTIONS
from .utils import utc_now_str


# ---------------------------------------------------------------------------
# Mission Report
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MissionReport:
    schema_version: str
    mission_id: str
    mission_title: str
    mission_type: str
    status: str  # COMPLETED | PARTIAL | FAILED | CANCELLED | ABORTED
    started_at: str
    finished_at: str
    duration_seconds: float
    tasks_planned: int
    tasks_completed: int
    tasks_failed: int
    tasks_skipped: int
    evidence_records: tuple[str, ...]
    independent_reviews: tuple[str, ...]
    queue_summary: dict[str, tuple[str, ...]]
    runtime_health: str
    metrics_summary: dict[str, object]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    artifacts_produced: tuple[str, ...]
    mission_report_path: str | None = None
    max_concurrency: int = 1
    peak_concurrent_tasks: int = 0
    # v0.9.6 lifecycle fields
    lifecycle_state: str = ""
    tasks_cancelled: int = 0
    tasks_aborted: int = 0
    retry_summary: dict[str, object] | None = None
    scheduler_summary: dict[str, object] | None = None
    concurrency_summary: dict[str, object] | None = None
    capability_usage: dict[str, object] | None = None
    evidence_summary: dict[str, object] | None = None
    independent_review_summary: dict[str, object] | None = None
    health_summary: dict[str, object] | None = None
    repository: str | None = None
    git_revision: str | None = None
    runtime_version: str = ""

    def as_dict(self) -> dict:
        d: dict[str, object] = {
            "schema_version": self.schema_version,
            "mission_id": self.mission_id,
            "mission_title": self.mission_title,
            "mission_type": self.mission_type,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,
            "tasks_planned": self.tasks_planned,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "tasks_skipped": self.tasks_skipped,
            "evidence_records": list(self.evidence_records),
            "independent_reviews": list(self.independent_reviews),
            "queue_summary": {k: list(v) for k, v in self.queue_summary.items()},
            "runtime_health": self.runtime_health,
            "metrics_summary": self.metrics_summary,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "artifacts_produced": list(self.artifacts_produced),
            "mission_report_path": self.mission_report_path,
            "max_concurrency": self.max_concurrency,
            "peak_concurrent_tasks": self.peak_concurrent_tasks,
        }
        # v0.9.6 fields — only include when set (deterministic output)
        if self.lifecycle_state:
            d["lifecycle_state"] = self.lifecycle_state
        if self.tasks_cancelled:
            d["tasks_cancelled"] = self.tasks_cancelled
        if self.tasks_aborted:
            d["tasks_aborted"] = self.tasks_aborted
        if self.retry_summary is not None:
            d["retry_summary"] = self.retry_summary
        if self.scheduler_summary is not None:
            d["scheduler_summary"] = self.scheduler_summary
        if self.concurrency_summary is not None:
            d["concurrency_summary"] = self.concurrency_summary
        if self.capability_usage is not None:
            d["capability_usage"] = self.capability_usage
        if self.evidence_summary is not None:
            d["evidence_summary"] = self.evidence_summary
        if self.independent_review_summary is not None:
            d["independent_review_summary"] = self.independent_review_summary
        if self.health_summary is not None:
            d["health_summary"] = self.health_summary
        if self.repository is not None:
            d["repository"] = self.repository
        if self.git_revision is not None:
            d["git_revision"] = self.git_revision
        if self.runtime_version:
            d["runtime_version"] = self.runtime_version
        return d


# ---------------------------------------------------------------------------
# Mission Runner
# ---------------------------------------------------------------------------

class MissionRunner:
    """Orchestrates complete mission execution.

    Pipeline:
        Plan → enqueue → dispatch tasks in dependency order →
        execute each via run_pipeline → collect results → MissionReport

    Supports concurrent execution of independent tasks when max_concurrency > 1.
    """

    def __init__(
        self,
        runtime_root: Path,
        repository: Path,
        working_directory: Path,
        queue_path: Path,
        executor_name: str | None = None,
        plugin_dirs: list[Path] | None = None,
        max_task_retries: int = 3,
        inter_task_delay: float = 0.0,
        mission_type_name: str | None = None,
        max_concurrency: int = 1,
        lifecycle_poll_interval: float = 0.1,
    ) -> None:
        self.runtime_root = runtime_root
        self.repository = repository
        self.working_directory = working_directory
        self.queue_path = queue_path
        self.executor_name = executor_name
        self.plugin_dirs = plugin_dirs or []
        self.max_task_retries = max_task_retries
        self.inter_task_delay = inter_task_delay
        self.mission_type_name = mission_type_name
        self.max_concurrency = max(1, max_concurrency)
        self.lifecycle_poll_interval = lifecycle_poll_interval
        self._queue_lock = threading.Lock()

        # Lifecycle coordination
        self._pause_event = threading.Event()
        self._cancel_event = threading.Event()
        self._abort_event = threading.Event()
        self._pause_event.set()
        self._cancel_event.set()
        self._abort_event.set()
        self._mission_state_store: MissionStateStore | None = None
        self._mission_control_store: MissionControlStore | None = None
        self._current_mission_state: MissionState | None = None
        self._active_mission_id: str | None = None

    def _resolve_executor(self) -> tuple[ExecutorPlugin | None, CapabilityManager | None]:
        if not self.executor_name:
            return None, None
        registry_path = self.runtime_root / "state" / "capabilities.json"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry = CapabilityRegistry(registry_path)
        cap_manager = CapabilityManager(registry, self.plugin_dirs)
        cap_manager.discover_and_register()
        return cap_manager.get_executor(self.executor_name), cap_manager

    # ------------------------------------------------------------------
    # Lifecycle control methods
    # ------------------------------------------------------------------

    def _ensure_lifecycle_stores(self) -> tuple[MissionStateStore, MissionControlStore]:
        if self._mission_state_store is None:
            self._mission_state_store = MissionStateStore(
                self.runtime_root / "state" / "mission_state.json"
            )
        if self._mission_control_store is None:
            self._mission_control_store = MissionControlStore(
                self.runtime_root / "state" / "mission_control.json"
            )
        return self._mission_state_store, self._mission_control_store

    def _persist_mission_state(self) -> None:
        if self._current_mission_state is not None and self._mission_state_store is not None:
            self._mission_state_store.save(self._current_mission_state)

    def pause(self, reason: str | None = None) -> MissionState:
        """Request pause: stop dispatching, let running tasks finish."""
        state_store, control_store = self._ensure_lifecycle_stores()
        state = self._current_mission_state
        if state is None:
            state = state_store.load()
        if state is None:
            raise RuntimeError("no active mission to pause")
        if state.is_terminal():
            raise ValueError(f"cannot pause mission in terminal state: {state.state}")
        if state.state == "PAUSED":
            return state
        cmd = MissionControlCommand(
            schema_version="1",
            mission_id=state.mission_id,
            command_id=control_store.next_command_id(state.last_control_command_id),
            action="pause",
            reason=reason,
            requested_at=utc_now_str(),
        )
        control_store.save(cmd)
        self._cancel_event.set()
        self._abort_event.set()
        self._pause_event.clear()
        new_state = transition_state(state, "PAUSED", reason=reason, command_id=cmd.command_id)
        self._current_mission_state = new_state
        self._persist_mission_state()
        return new_state

    def resume(self) -> MissionState:
        """Resume a paused mission."""
        state_store, control_store = self._ensure_lifecycle_stores()
        state = self._current_mission_state
        if state is None:
            state = state_store.load()
        if state is None:
            raise RuntimeError("no active mission to resume")
        if state.state != "PAUSED":
            raise ValueError(f"can only resume a PAUSED mission, current: {state.state}")
        cmd = MissionControlCommand(
            schema_version="1",
            mission_id=state.mission_id,
            command_id=control_store.next_command_id(state.last_control_command_id),
            action="resume",
            reason=None,
            requested_at=utc_now_str(),
        )
        control_store.save(cmd)
        self._pause_event.set()
        new_state = transition_state(state, "RUNNING", command_id=cmd.command_id)
        self._current_mission_state = new_state
        self._persist_mission_state()
        return new_state

    def cancel(self, reason: str | None = None) -> MissionState:
        """Cancel mission: stop future dispatch, let running tasks finish."""
        state_store, control_store = self._ensure_lifecycle_stores()
        state = self._current_mission_state
        if state is None:
            state = state_store.load()
        if state is None:
            raise RuntimeError("no active mission to cancel")
        if state.is_terminal():
            raise ValueError(f"cannot cancel mission in terminal state: {state.state}")
        if state.state == "CANCELLED":
            return state
        cmd = MissionControlCommand(
            schema_version="1",
            mission_id=state.mission_id,
            command_id=control_store.next_command_id(state.last_control_command_id),
            action="cancel",
            reason=reason,
            requested_at=utc_now_str(),
        )
        control_store.save(cmd)
        self._cancel_event.clear()
        self._abort_event.set()
        self._pause_event.set()
        new_state = transition_state(state, "CANCELLED", reason=reason, command_id=cmd.command_id)
        self._current_mission_state = new_state
        self._persist_mission_state()
        return new_state

    def abort(self, reason: str | None = None) -> MissionState:
        """Abort mission: immediate termination, cancel pending futures."""
        state_store, control_store = self._ensure_lifecycle_stores()
        state = self._current_mission_state
        if state is None:
            state = state_store.load()
        if state is None:
            raise RuntimeError("no active mission to abort")
        if state.is_terminal():
            raise ValueError(f"cannot abort mission in terminal state: {state.state}")
        if state.state == "ABORTED":
            return state
        cmd = MissionControlCommand(
            schema_version="1",
            mission_id=state.mission_id,
            command_id=control_store.next_command_id(state.last_control_command_id),
            action="abort",
            reason=reason,
            requested_at=utc_now_str(),
        )
        control_store.save(cmd)
        self._abort_event.clear()
        self._cancel_event.clear()
        self._pause_event.set()
        new_state = transition_state(state, "ABORTED", reason=reason, command_id=cmd.command_id)
        self._current_mission_state = new_state
        self._persist_mission_state()
        return new_state

    def status(self) -> MissionState | None:
        """Return the current persisted mission state."""
        state_store, _ = self._ensure_lifecycle_stores()
        if self._current_mission_state is not None:
            return self._current_mission_state
        return state_store.load()

    def _poll_control_command(self) -> MissionControlCommand | None:
        """Read and apply a fresh control command from the control file."""
        if self._mission_control_store is None or self._current_mission_state is None:
            return None
        cmd = self._mission_control_store.load()
        if cmd is None:
            return None
        if cmd.mission_id != self._active_mission_id:
            return None
        if cmd.command_id <= self._current_mission_state.last_control_command_id:
            return None
        return cmd

    def _apply_control_command(self, cmd: MissionControlCommand) -> None:
        """Apply a validated control command to the runner and persist state."""
        action = cmd.action
        if action == "pause":
            self._cancel_event.set()
            self._abort_event.set()
            self._pause_event.clear()
            self._current_mission_state = transition_state(
                self._current_mission_state, "PAUSED",
                reason=cmd.reason, command_id=cmd.command_id,
            )
        elif action == "resume":
            self._pause_event.set()
            self._current_mission_state = transition_state(
                self._current_mission_state, "RUNNING",
                command_id=cmd.command_id,
            )
        elif action == "cancel":
            self._cancel_event.clear()
            self._abort_event.set()
            self._pause_event.set()
            self._current_mission_state = transition_state(
                self._current_mission_state, "CANCELLED",
                reason=cmd.reason, command_id=cmd.command_id,
            )
        elif action == "abort":
            self._abort_event.clear()
            self._cancel_event.clear()
            self._pause_event.set()
            self._current_mission_state = transition_state(
                self._current_mission_state, "ABORTED",
                reason=cmd.reason, command_id=cmd.command_id,
            )
        self._persist_mission_state()

    def _check_lifecycle(self) -> str:
        """Check for control commands and event signals.

        Returns:
            "continue" — normal operation
            "pause"    — paused, poll until resumed or cancelled
            "stop"     — cancelled or aborted, exit the loop
        """
        cmd = self._poll_control_command()
        if cmd is not None:
            self._apply_control_command(cmd)

        if not self._abort_event.is_set():
            return "stop"
        if not self._cancel_event.is_set():
            return "stop"
        if not self._pause_event.is_set():
            return "pause"
        return "continue"

    def run(self, plan: Plan) -> MissionReport:
        started_at = utc_now_str()
        started_time = time.monotonic()
        warnings: list[str] = []
        errors: list[str] = []
        evidence_records: list[str] = []
        independent_reviews: list[str] = []
        artifacts_produced: list[str] = []

        mission_type_str = self.mission_type_name or "generic"

        task_command_map: dict[str, list[str]] = {}
        for t in plan.tasks:
            task_command_map[t.task_id] = list(t.command)

        # Initialize lifecycle state
        state_store, _ = self._ensure_lifecycle_stores()
        self._active_mission_id = plan.mission_id
        initial = create_initial_state(plan.mission_id, plan.mission_title, len(plan.tasks))
        self._current_mission_state = initial
        self._mission_state_store.save(transition_state(initial, "RUNNING"))
        self._current_mission_state = transition_state(initial, "RUNNING")

        # Reset lifecycle events for a fresh run
        self._pause_event.set()
        self._cancel_event.set()
        self._abort_event.set()

        if not plan.valid:
            final = transition_state(self._current_mission_state, "FAILED")
            self._current_mission_state = final
            self._persist_mission_state()
            return _build_report(
                plan=plan,
                started_at=started_at,
                finished_at=utc_now_str(),
                duration=0.0,
                status="FAILED",
                tasks_completed=0,
                tasks_failed=0,
                tasks_skipped=plan.tasks,
                evidence_records=[],
                independent_reviews=[],
                warnings=list(plan.warnings),
                errors=list(plan.errors) or ["plan is not valid"],
                artifacts_produced=[],
                runtime_root=self.runtime_root,
                queue_path=self.queue_path,
                mission_type=mission_type_str,
                max_concurrency=self.max_concurrency,
            )

        enqueue_plan(plan, self.queue_path)

        work_queue = WorkQueueManager(
            state_store=WorkQueueStateStore(self.queue_path)
        )

        executor, cap_manager = self._resolve_executor()

        tasks_completed = 0
        tasks_failed = 0
        task_results: dict[str, str] = {}
        peak_concurrent = 0

        if self.max_concurrency <= 1:
            tasks_completed, tasks_failed, evidence_records, independent_reviews, task_results, warnings, errors = (
                self._run_sequential(
                    plan, work_queue, task_command_map, executor, cap_manager,
                )
            )
        else:
            tasks_completed, tasks_failed, evidence_records, independent_reviews, task_results, warnings, errors, peak_concurrent = (
                self._run_concurrent(
                    plan, work_queue, task_command_map, executor, cap_manager,
                )
            )

        work_queue.refresh()
        queue_summary = {k: tuple(v) for k, v in work_queue.summary().items()}

        seen_artifacts: set[str] = set()
        for item in work_queue.items():
            run_dir = self.runtime_root / "runs"
            if run_dir.exists():
                for run_entry in run_dir.iterdir():
                    result_file = run_entry / "runtime-result.json"
                    if result_file.exists():
                        try:
                            data = json.loads(result_file.read_text(encoding="utf-8"))
                            ep = data.get("execution_record_path")
                            if ep and ep not in seen_artifacts:
                                seen_artifacts.add(ep)
                                artifacts_produced.append(ep)
                        except (json.JSONDecodeError, KeyError):
                            pass

        health_str = "UNKNOWN"
        try:
            health_report = build_health_report(self.runtime_root)
            health_str = health_report.overall_health
        except Exception:
            warnings.append("health check failed after mission execution")

        metrics_summary: dict[str, object] = {}
        try:
            rt_metrics = compute_runtime_metrics(self.runtime_root)
            metrics_summary["total_executions"] = rt_metrics.total_executions
            metrics_summary["successful_executions"] = rt_metrics.successful_executions
            metrics_summary["failed_executions"] = rt_metrics.failed_executions
            metrics_summary["average_duration_seconds"] = rt_metrics.average_duration_seconds
        except Exception:
            pass

        skipped = [
            t for t in plan.tasks
            if t.task_id not in task_results
        ]

        finished_at = utc_now_str()
        duration = time.monotonic() - started_time

        if self._current_mission_state.is_terminal():
            status = self._current_mission_state.state
            if status == "COMPLETED":
                status = "COMPLETED"
            elif status in ("CANCELLED", "ABORTED"):
                status = "PARTIAL" if tasks_completed > 0 else "FAILED"
            else:
                status = status
        elif tasks_failed == 0 and tasks_completed == len(plan.tasks):
            status = "COMPLETED"
            self._current_mission_state = transition_state(self._current_mission_state, "COMPLETED")
        elif tasks_completed > 0:
            status = "PARTIAL"
            self._current_mission_state = transition_state(self._current_mission_state, "FAILED")
        else:
            status = "FAILED"
            self._current_mission_state = transition_state(self._current_mission_state, "FAILED")

        self._current_mission_state = update_counts(
            self._current_mission_state,
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
        )
        self._persist_mission_state()

        report = _build_report(
            plan=plan,
            started_at=started_at,
            finished_at=finished_at,
            duration=duration,
            status=status,
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
            tasks_skipped=skipped,
            evidence_records=evidence_records,
            independent_reviews=independent_reviews,
            warnings=warnings,
            errors=errors,
            artifacts_produced=artifacts_produced,
            runtime_root=self.runtime_root,
            queue_path=self.queue_path,
            queue_summary=queue_summary,
            runtime_health=health_str,
            metrics_summary=metrics_summary,
            mission_type=mission_type_str,
            max_concurrency=self.max_concurrency,
            peak_concurrent_tasks=peak_concurrent,
        )

        # Generate comprehensive report artifacts (JSON + Markdown)
        try:
            from .mission_report import generate_and_save_reports
            json_path, md_path = generate_and_save_reports(
                runtime_root=self.runtime_root,
                report=report,
                mission_state=self._current_mission_state,
                repository=self.repository,
                executor_name=self.executor_name,
            )
            report = MissionReport(
                schema_version=report.schema_version,
                mission_id=report.mission_id,
                mission_title=report.mission_title,
                mission_type=report.mission_type,
                status=report.status,
                started_at=report.started_at,
                finished_at=report.finished_at,
                duration_seconds=report.duration_seconds,
                tasks_planned=report.tasks_planned,
                tasks_completed=report.tasks_completed,
                tasks_failed=report.tasks_failed,
                tasks_skipped=report.tasks_skipped,
                evidence_records=report.evidence_records,
                independent_reviews=report.independent_reviews,
                queue_summary=report.queue_summary,
                runtime_health=report.runtime_health,
                metrics_summary=report.metrics_summary,
                warnings=report.warnings,
                errors=report.errors,
                artifacts_produced=report.artifacts_produced,
                mission_report_path=str(json_path),
                max_concurrency=report.max_concurrency,
                peak_concurrent_tasks=report.peak_concurrent_tasks,
                lifecycle_state=report.lifecycle_state,
                tasks_cancelled=report.tasks_cancelled,
                tasks_aborted=report.tasks_aborted,
                retry_summary=report.retry_summary,
                scheduler_summary=report.scheduler_summary,
                concurrency_summary=report.concurrency_summary,
                capability_usage=report.capability_usage,
                evidence_summary=report.evidence_summary,
                independent_review_summary=report.independent_review_summary,
                health_summary=report.health_summary,
                repository=report.repository,
                git_revision=report.git_revision,
                runtime_version=report.runtime_version,
            )
        except Exception:
            pass

        return report

    def _run_sequential(
        self,
        plan: Plan,
        work_queue: WorkQueueManager,
        task_command_map: dict[str, list[str]],
        executor: ExecutorPlugin | None,
        cap_manager: CapabilityManager | None,
    ) -> tuple[int, int, list[str], list[str], dict[str, str], list[str], list[str]]:
        tasks_completed = 0
        tasks_failed = 0
        evidence_records: list[str] = []
        independent_reviews: list[str] = []
        task_results: dict[str, str] = {}
        warnings: list[str] = []
        errors: list[str] = []

        max_iterations = len(plan.tasks) * 20
        for _ in range(max_iterations):
            # Lifecycle check
            lc = self._check_lifecycle()
            if lc == "stop":
                break
            if lc == "pause":
                while not self._pause_event.is_set():
                    if not self._abort_event.is_set() or not self._cancel_event.is_set():
                        break
                    cmd = self._poll_control_command()
                    if cmd is not None:
                        self._apply_control_command(cmd)
                    time.sleep(self.lifecycle_poll_interval)
                if self._check_lifecycle() == "stop":
                    break

            work_queue.refresh()
            summary = work_queue.summary()
            terminal = set(summary.get("COMPLETE", [])) | set(summary.get("VERIFIED", []))

            if len(terminal) >= len(plan.tasks):
                break

            ready = work_queue.next_ready()
            if ready is None:
                blocked = summary.get("BLOCKED", [])
                failed_ids = [tid for tid, state in task_results.items() if state == "FAILED"]
                blocked_without_failed_deps = []
                for tid in blocked:
                    item = work_queue.get(tid)
                    deps_failed = any(d in failed_ids for d in item.dependencies)
                    if not deps_failed:
                        blocked_without_failed_deps.append(tid)

                if not blocked_without_failed_deps and not failed_ids:
                    break
                if blocked_without_failed_deps:
                    warnings.append(f"deadlock: tasks {blocked_without_failed_deps} blocked with no ready path")
                break

            task_cmd = task_command_map.get(ready.task_id)
            if task_cmd is None:
                errors.append(f"task {ready.task_id} not found in plan")
                work_queue.mark_failed(ready.task_id, "missing from plan")
                continue

            result = run_pipeline(
                task_cmd,
                runtime_root=self.runtime_root,
                repository=self.repository,
                working_directory=self.working_directory,
                work_queue=work_queue,
                task_id=ready.task_id,
                executor=executor,
                capability_manager=cap_manager,
                executor_name=self.executor_name,
            )

            if result.execution_record_path:
                evidence_records.append(result.execution_record_path)
            if result.review_path:
                independent_reviews.append(result.review_path)

            if result.status == "COMPLETED":
                tasks_completed += 1
                task_results[ready.task_id] = "COMPLETED"
            else:
                tasks_failed += 1
                task_results[ready.task_id] = "FAILED"
                work_queue.refresh()
                item = work_queue.get(ready.task_id)
                if not item.can_retry():
                    errors.append(f"task {ready.task_id} failed permanently: {'; '.join(result.errors)}")

            if self.inter_task_delay > 0:
                time.sleep(self.inter_task_delay)

        return tasks_completed, tasks_failed, evidence_records, independent_reviews, task_results, warnings, errors

    def _run_concurrent(
        self,
        plan: Plan,
        work_queue: WorkQueueManager,
        task_command_map: dict[str, list[str]],
        executor: ExecutorPlugin | None,
        cap_manager: CapabilityManager | None,
    ) -> tuple[int, int, list[str], list[str], dict[str, str], list[str], list[str], int]:
        tasks_completed = 0
        tasks_failed = 0
        evidence_records: list[str] = []
        independent_reviews: list[str] = []
        task_results: dict[str, str] = {}
        warnings: list[str] = []
        errors: list[str] = []
        peak_concurrent = 0

        def _execute_task(task_id: str, command: list[str]) -> tuple[str, object]:
            result = run_pipeline(
                command,
                runtime_root=self.runtime_root,
                repository=self.repository,
                working_directory=self.working_directory,
                work_queue=work_queue,
                task_id=task_id,
                executor=executor,
                capability_manager=cap_manager,
                executor_name=self.executor_name,
            )
            return task_id, result

        def _handle_result(task_id: str, result: object) -> None:
            nonlocal tasks_completed, tasks_failed
            if result.execution_record_path:
                evidence_records.append(result.execution_record_path)
            if result.review_path:
                independent_reviews.append(result.review_path)

            with self._queue_lock:
                if result.status == "COMPLETED":
                    tasks_completed += 1
                    task_results[task_id] = "COMPLETED"
                else:
                    tasks_failed += 1
                    task_results[task_id] = "FAILED"
                    work_queue.refresh()
                    try:
                        item = work_queue.get(task_id)
                        if not item.can_retry():
                            errors.append(f"task {task_id} failed permanently: {'; '.join(result.errors)}")
                    except KeyError:
                        errors.append(f"task {task_id} failed permanently: {'; '.join(result.errors)}")

        def _dispatch_batch() -> list[WorkItem]:
            nonlocal peak_concurrent
            with self._queue_lock:
                work_queue.refresh()
                summary = work_queue.summary()
                terminal = set(summary.get("COMPLETE", [])) | set(summary.get("VERIFIED", []))

                if len(terminal) >= len(plan.tasks):
                    return []

                running_count = sum(
                    1 for item in work_queue.items() if item.state == "RUNNING"
                )
                available = self.max_concurrency - running_count
                if available <= 0:
                    return []

                dispatched = work_queue.dispatch_ready(max_concurrent=available)
                if running_count + len(dispatched) > peak_concurrent:
                    peak_concurrent = running_count + len(dispatched)
                return dispatched

        with ThreadPoolExecutor(max_workers=self.max_concurrency) as pool:
            futures: dict[str, object] = {}

            max_iterations = len(plan.tasks) * 20
            for _ in range(max_iterations):
                # Lifecycle check
                lc = self._check_lifecycle()
                if lc == "stop":
                    break
                if lc == "pause":
                    while not self._pause_event.is_set():
                        if not self._abort_event.is_set() or not self._cancel_event.is_set():
                            break
                        cmd = self._poll_control_command()
                        if cmd is not None:
                            self._apply_control_command(cmd)
                        time.sleep(self.lifecycle_poll_interval)
                    if self._check_lifecycle() == "stop":
                        break

                dispatched = _dispatch_batch()
                for item in dispatched:
                    task_cmd = task_command_map.get(item.task_id)
                    if task_cmd is None:
                        errors.append(f"task {item.task_id} not found in plan")
                        with self._queue_lock:
                            work_queue.mark_failed(item.task_id, "missing from plan")
                        tasks_failed += 1
                        task_results[item.task_id] = "FAILED"
                        continue
                    future = pool.submit(_execute_task, item.task_id, task_cmd)
                    futures[f"{item.task_id}:{item.attempts}"] = future

                if not futures:
                    with self._queue_lock:
                        work_queue.refresh()
                        summary = work_queue.summary()
                        terminal = set(summary.get("COMPLETE", [])) | set(summary.get("VERIFIED", []))
                        if len(terminal) >= len(plan.tasks):
                            break
                        blocked = summary.get("BLOCKED", [])
                        failed_ids = [tid for tid, state in task_results.items() if state == "FAILED"]
                        blocked_without_failed_deps = [
                            tid for tid in blocked
                            if not any(d in failed_ids for d in work_queue.get(tid).dependencies)
                        ]
                        if not blocked_without_failed_deps and not failed_ids:
                            break
                        if blocked_without_failed_deps:
                            warnings.append(f"deadlock: tasks {blocked_without_failed_deps} blocked with no ready path")
                    break

                done_futures = []
                for key, fut in list(futures.items()):
                    if fut.done():
                        done_futures.append(key)

                for key in done_futures:
                    fut = futures.pop(key)
                    try:
                        _, result = fut.result()
                        _handle_result(key.split(":")[0], result)
                    except Exception as exc:
                        task_id = key.split(":")[0]
                        with self._queue_lock:
                            tasks_failed += 1
                            task_results[task_id] = "FAILED"
                            errors.append(f"task {task_id} raised exception: {exc}")
                            try:
                                work_queue.mark_failed(task_id, f"exception: {exc}")
                            except (KeyError, ValueError):
                                pass

                if not done_futures:
                    time.sleep(0.01)

            # Abort: cancel all pending futures
            if not self._abort_event.is_set():
                for key, fut in futures.items():
                    if not fut.done():
                        fut.cancel()

            for key, fut in futures.items():
                if not fut.done():
                    fut.cancel()
                else:
                    try:
                        _, result = fut.result()
                        _handle_result(key.split(":")[0], result)
                    except Exception as exc:
                        task_id = key.split(":")[0]
                        with self._queue_lock:
                            tasks_failed += 1
                            task_results[task_id] = "FAILED"

        return tasks_completed, tasks_failed, evidence_records, independent_reviews, task_results, warnings, errors, peak_concurrent

    def run_mission_file(self, mission_path: Path) -> MissionReport:
        from .mission import load_mission, MissionPlanner
        mission = load_mission(mission_path)
        planner = MissionPlanner()
        plan = planner.build(mission)

        mission_type_str = self.mission_type_name or mission.metadata.get("type", "generic")

        if mission_type_str and mission_type_str != "generic":
            registry = MissionTypeRegistry.instance()
            if not registry.is_registered(mission_type_str):
                try:
                    register_built_in_types(registry)
                except Exception:
                    pass
            if registry.is_registered(mission_type_str):
                mt = registry.get(mission_type_str)
                type_errors, type_warnings = mt.validate_mission(mission)
                if type_errors:
                    return _build_report(
                        plan=plan,
                        started_at=utc_now_str(),
                        finished_at=utc_now_str(),
                        duration=0.0,
                        status="FAILED",
                        tasks_completed=0,
                        tasks_failed=0,
                        tasks_skipped=list(plan.tasks),
                        evidence_records=[],
                        independent_reviews=[],
                        warnings=list(type_warnings),
                        errors=type_errors,
                        artifacts_produced=[],
                        runtime_root=self.runtime_root,
                        queue_path=self.queue_path,
                        mission_type=mission_type_str,
                        max_concurrency=self.max_concurrency,
                    )

        self.mission_type_name = mission_type_str
        return self.run(plan)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_report(
    plan: Plan,
    started_at: str,
    finished_at: str,
    duration: float,
    status: str,
    tasks_completed: int,
    tasks_failed: int,
    tasks_skipped: list,
    evidence_records: list[str],
    independent_reviews: list[str],
    warnings: list[str],
    errors: list[str],
    artifacts_produced: list[str],
    runtime_root: Path,
    queue_path: Path,
    queue_summary: dict | None = None,
    runtime_health: str = "UNKNOWN",
    metrics_summary: dict | None = None,
    mission_type: str = "generic",
    max_concurrency: int = 1,
    peak_concurrent_tasks: int = 0,
) -> MissionReport:
    if queue_summary is None:
        queue_summary = {}
    if metrics_summary is None:
        metrics_summary = {}

    report = MissionReport(
        schema_version="1",
        mission_id=plan.mission_id,
        mission_title=plan.mission_title,
        mission_type=mission_type,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=round(duration, 3),
        tasks_planned=len(plan.tasks),
        tasks_completed=tasks_completed,
        tasks_failed=tasks_failed,
        tasks_skipped=len(tasks_skipped),
        evidence_records=tuple(evidence_records),
        independent_reviews=tuple(independent_reviews),
        queue_summary=queue_summary,
        runtime_health=runtime_health,
        metrics_summary=metrics_summary,
        warnings=tuple(warnings),
        errors=tuple(errors),
        artifacts_produced=tuple(artifacts_produced),
        max_concurrency=max_concurrency,
        peak_concurrent_tasks=peak_concurrent_tasks,
    )
    return report


def save_mission_report(report: MissionReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_mission_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
