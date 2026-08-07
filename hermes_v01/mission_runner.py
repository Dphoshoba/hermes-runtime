from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .work_queue import WorkQueueManager, WorkQueueStateStore
from .mission import Plan, load_plan, enqueue_plan
from .runtime import run_pipeline
from .capabilities import CapabilityManager, CapabilityRegistry, ExecutorPlugin
from .health import build_health_report
from .metrics import compute_queue_metrics, compute_runtime_metrics
from .mission_types import MissionTypeRegistry, register_built_in_types


# ---------------------------------------------------------------------------
# Mission Report
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MissionReport:
    schema_version: str
    mission_id: str
    mission_title: str
    mission_type: str
    status: str  # COMPLETED | PARTIAL | FAILED
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

    def as_dict(self) -> dict:
        d = {
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
        executor_name: Optional[str] = None,
        plugin_dirs: Optional[list[Path]] = None,
        max_task_retries: int = 3,
        inter_task_delay: float = 0.0,
        mission_type_name: Optional[str] = None,
        max_concurrency: int = 1,
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
        self._queue_lock = threading.Lock()

    def _resolve_executor(self) -> tuple[ExecutorPlugin | None, CapabilityManager | None]:
        if not self.executor_name:
            return None, None
        registry_path = self.runtime_root / "state" / "capabilities.json"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry = CapabilityRegistry(registry_path)
        cap_manager = CapabilityManager(registry, self.plugin_dirs)
        cap_manager.discover_and_register()
        return cap_manager.get_executor(self.executor_name), cap_manager

    def run(self, plan: Plan) -> MissionReport:
        started_at = _utc_now()
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

        if not plan.valid:
            return _build_report(
                plan=plan,
                started_at=started_at,
                finished_at=_utc_now(),
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

        finished_at = _utc_now()
        duration = time.monotonic() - started_time

        if tasks_failed == 0 and tasks_completed == len(plan.tasks):
            status = "COMPLETED"
        elif tasks_completed > 0:
            status = "PARTIAL"
        else:
            status = "FAILED"

        return _build_report(
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
                        started_at=_utc_now(),
                        finished_at=_utc_now(),
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

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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
