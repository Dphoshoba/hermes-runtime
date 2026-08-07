from __future__ import annotations

import json
import os
import signal
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional

from .__main__ import DEFAULT_ARTIFACTS, Finding, Report, inspect_repository
from .work_queue import WorkItem, WorkQueueManager


@dataclass(frozen=True)
class SupervisorState:
    schema_version: str
    status: str
    repository: str
    output_dir: str
    cycle_count: int
    last_cycle_started_at_utc: str | None
    last_cycle_finished_at_utc: str | None
    last_exit_code: int | None
    last_mission_status: str | None
    stop_reason: str | None


@dataclass(frozen=True)
class CycleResult:
    cycle_number: int
    started_at_utc: str
    finished_at_utc: str
    exit_code: int
    report: Report
    report_json: str
    report_markdown: str


class AtomicJsonStateStore:
    """Persists supervisor state atomically outside the inspected repository."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> SupervisorState | None:
        if not self.path.exists():
            return None
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return SupervisorState(**data)

    def save(self, state: SupervisorState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(asdict(state), indent=2, sort_keys=True) + "\n"
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=str(self.path.parent),
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)


class ExecutionSupervisor:
    """Runs the existing read-only validator repeatedly and persists its state.

    The supervisor never mutates the inspected repository. It only writes reports
    and its own state beneath ``output_dir``.
    """

    def __init__(
        self,
        *,
        repository: Path,
        output_dir: Path,
        artifacts: Iterable[str] | None = None,
        interval_seconds: float = 60.0,
        state_file: Path | None = None,
        stop_file: Path | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] | None = None,
        work_queue: Optional[WorkQueueManager] = None,
    ) -> None:
        if interval_seconds < 0:
            raise ValueError("interval_seconds must be >= 0")
        self.repository = repository.expanduser().resolve()
        self.output_dir = output_dir.expanduser().resolve()
        self.artifacts = tuple(artifacts or DEFAULT_ARTIFACTS)
        self.interval_seconds = interval_seconds
        self.state_file = (state_file or self.output_dir / "supervisor-state.json").expanduser().resolve()
        self.stop_file = (stop_file or self.output_dir / "STOP").expanduser().resolve()
        self._sleeper = sleeper
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._state_store = AtomicJsonStateStore(self.state_file)
        self._stop_requested = False
        self._work_queue = work_queue

    def request_stop(self) -> None:
        self._stop_requested = True

    def _timestamp(self) -> str:
        return self._clock().isoformat()

    def _initial_state(self) -> SupervisorState:
        previous = self._state_store.load()
        cycle_count = previous.cycle_count if previous else 0
        return SupervisorState(
            schema_version="1",
            status="STARTING",
            repository=str(self.repository),
            output_dir=str(self.output_dir),
            cycle_count=cycle_count,
            last_cycle_started_at_utc=previous.last_cycle_started_at_utc if previous else None,
            last_cycle_finished_at_utc=previous.last_cycle_finished_at_utc if previous else None,
            last_exit_code=previous.last_exit_code if previous else None,
            last_mission_status=previous.last_mission_status if previous else None,
            stop_reason=None,
        )

    def run_cycle(self) -> CycleResult:
        state = self._state_store.load() or self._initial_state()
        cycle_number = state.cycle_count + 1
        started = self._timestamp()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        running = SupervisorState(
            **{
                **asdict(state),
                "status": "RUNNING",
                "cycle_count": cycle_number,
                "last_cycle_started_at_utc": started,
                "stop_reason": None,
            }
        )
        self._state_store.save(running)

        report = inspect_repository(self.repository, list(self.artifacts))
        exit_code = 0 if report.mission_status == "Observation Complete" else 2
        finished = self._timestamp()
        cycle_dir = self.output_dir / "cycles" / f"{cycle_number:06d}"
        cycle_dir.mkdir(parents=True, exist_ok=True)
        json_path = cycle_dir / "verification-report.json"
        markdown_path = cycle_dir / "verification-report.md"

        from .__main__ import render_markdown

        json_path.write_text(json.dumps(asdict(report), indent=2) + "\n", encoding="utf-8")
        markdown_path.write_text(render_markdown(report), encoding="utf-8")

        # Enqueue remediation tasks for missing artifacts if work queue is configured
        if self._work_queue is not None:
            self._enqueue_remediation_tasks(report.findings, cycle_number)

        completed = SupervisorState(
            schema_version="1",
            status="QUIESCENT",
            repository=str(self.repository),
            output_dir=str(self.output_dir),
            cycle_count=cycle_number,
            last_cycle_started_at_utc=started,
            last_cycle_finished_at_utc=finished,
            last_exit_code=exit_code,
            last_mission_status=report.mission_status,
            stop_reason=None,
        )
        self._state_store.save(completed)
        return CycleResult(
            cycle_number=cycle_number,
            started_at_utc=started,
            finished_at_utc=finished,
            exit_code=exit_code,
            report=report,
            report_json=str(json_path),
            report_markdown=str(markdown_path),
        )

    def _enqueue_remediation_tasks(self, findings: list[Finding], cycle_number: int) -> None:
        """Enqueue remediation tasks for missing or unverified artifacts."""
        existing_items = {item.task_id for item in self._work_queue.state.items}
        for finding in findings:
            if finding.classification in ("Verified Missing", "Unverified"):
                task_id = f"remediate-{finding.artifact.replace('/', '-').replace('.', '-')}-c{cycle_number}"
                if task_id not in existing_items:
                    remediation_item = WorkItem(
                        task_id=task_id,
                        title=f"Remediate {finding.artifact}",
                        priority=100 + cycle_number,
                        dependencies=(),
                        state="READY",
                    )
                    # Use transition to add the new item - we need to recreate the state with the new item
                    current_items = list(self._work_queue.state.items)
                    current_items.append(remediation_item)
                    from .work_queue import WorkQueueState
                    new_state = WorkQueueState(
                        schema_version=self._work_queue.state.schema_version,
                        revision=self._work_queue.state.revision + 1,
                        items=tuple(current_items),
                    )
                    self._work_queue._persist(self._work_queue._normalize(new_state))

    def run(self, *, max_cycles: int | None = None) -> int:
        if max_cycles is not None and max_cycles < 1:
            raise ValueError("max_cycles must be >= 1 when provided")

        state = self._initial_state()
        self._state_store.save(state)

        previous_handlers: dict[int, object] = {}

        def handle_signal(signum: int, _frame: object) -> None:
            self._stop_requested = True

        for signum in (signal.SIGINT, signal.SIGTERM):
            try:
                previous_handlers[signum] = signal.getsignal(signum)
                signal.signal(signum, handle_signal)
            except (ValueError, OSError):
                pass

        stop_reason = "STOP_REQUESTED"
        final_exit_code = 0
        cycles_this_run = 0
        try:
            while True:
                if self._stop_requested:
                    stop_reason = "SIGNAL"
                    break
                if self.stop_file.exists():
                    stop_reason = "STOP_FILE"
                    break
                result = self.run_cycle()
                final_exit_code = max(final_exit_code, result.exit_code)
                cycles_this_run += 1
                if max_cycles is not None and cycles_this_run >= max_cycles:
                    stop_reason = "MAX_CYCLES"
                    break
                self._sleeper(self.interval_seconds)
        finally:
            current = self._state_store.load() or state
            stopped = SupervisorState(
                **{
                    **asdict(current),
                    "status": "STOPPED",
                    "stop_reason": stop_reason,
                }
            )
            self._state_store.save(stopped)
            for signum, handler in previous_handlers.items():
                try:
                    signal.signal(signum, handler)  # type: ignore[arg-type]
                except (ValueError, OSError):
                    pass
        return final_exit_code
