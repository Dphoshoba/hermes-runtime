from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence, Optional

from .work_queue import WorkQueueManager
from .capabilities import CapabilityManager, ExecutorPlugin


@dataclass(frozen=True)
class RuntimeResult:
    run_id: str
    command: list[str]
    working_directory: str
    started_at: str
    finished_at: str
    execution_record_path: str | None
    review_path: str | None
    health_path: str | None
    exit_code: int
    status: str
    errors: list[str]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _latest_matching_file(root: Path, pattern: str) -> Path | None:
    matches = sorted(root.glob(pattern))
    return matches[-1] if matches else None


def run_pipeline(
    command: Sequence[str],
    *,
    runtime_root: Path,
    repository: Path,
    working_directory: Path,
    work_queue: Optional[WorkQueueManager] = None,
    task_id: Optional[str] = None,
    executor: Optional[ExecutorPlugin] = None,
    capability_manager: Optional[CapabilityManager] = None,
    executor_name: Optional[str] = None,
) -> RuntimeResult:
    started_at = _utc_now()
    run_id = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%S.%fZ")

    evidence_dir = runtime_root / "evidence"
    reviews_dir = runtime_root / "reviews"
    health_dir = runtime_root / "health"
    run_dir = runtime_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    errors: list[str] = []
    execution_record_path: Path | None = None
    review_path: Path | None = None
    health_path: Path | None = None

    # Transition task to RUNNING if work queue is provided
    if work_queue and task_id:
        current = work_queue.get(task_id)
        if current.state != "RUNNING":
            work_queue.transition(task_id, "RUNNING", increment_attempts=True)

    # Resolve executor
    if executor is None:
        if capability_manager and executor_name:
            executor = capability_manager.get_executor(executor_name)
        else:
            executor = capability_manager._executors.get("local") if capability_manager else None
            if executor is None:
                from .capabilities import LocalExecutorPlugin
                executor = LocalExecutorPlugin()

    # Execute using the executor plugin
    record_command = [
        "hermes-record",
        "--evidence-dir",
        str(evidence_dir),
        "--cwd",
        str(working_directory),
        "--trigger",
        "PROGRAM_III_RUNTIME",
        "--repository",
        str(repository),
        *command,
    ]

    # Add work queue args if provided
    if work_queue and task_id:
        pass

    record_result = executor.execute(record_command, working_directory)

    (run_dir / "record.stdout.log").write_text(
        record_result.stdout,
        encoding="utf-8",
    )
    (run_dir / "record.stderr.log").write_text(
        record_result.stderr,
        encoding="utf-8",
    )

    if record_result.exit_code != 0:
        errors.append(
            f"hermes-record exited with code {record_result.exit_code}"
        )

    for line in reversed(record_result.stdout.splitlines()):
        candidate = Path(line.strip())
        if candidate.name == "execution-record.json" and candidate.exists():
            execution_record_path = candidate
            break

    if execution_record_path is None:
        errors.append("execution record path not found in executor output")
    else:
        # Mark OBSERVED after successful evidence recording
        if work_queue and task_id:
            work_queue.mark_observed(task_id)
            work_queue.mark_verification_pending(task_id)

        review_process = subprocess.run(
            [
                "hermes-review",
                "--record",
                str(execution_record_path),
                "--output-dir",
                str(reviews_dir),
            ],
            cwd=working_directory,
            text=True,
            capture_output=True,
            check=False,
        )

        (run_dir / "review.stdout.log").write_text(
            review_process.stdout,
            encoding="utf-8",
        )
        (run_dir / "review.stderr.log").write_text(
            review_process.stderr,
            encoding="utf-8",
        )

        if review_process.returncode != 0:
            errors.append(
                f"hermes-review exited with code {review_process.returncode}"
            )

        for line in reversed(review_process.stdout.splitlines()):
            candidate = Path(line.strip())
            if candidate.name == "review.json" and candidate.exists():
                review_path = candidate
                break

        if review_path is None:
            errors.append("review path not found in hermes-review output")
        else:
            # Mark VERIFIED after successful review
            if work_queue and task_id:
                work_queue.record_independent_verification(task_id)

    health_process = subprocess.run(
        [
            "hermes-health",
            "--runtime-root",
            str(runtime_root),
            "--output-dir",
            str(health_dir),
        ],
        cwd=working_directory,
        text=True,
        capture_output=True,
        check=False,
    )

    (run_dir / "health.stdout.log").write_text(
        health_process.stdout,
        encoding="utf-8",
    )
    (run_dir / "health.stderr.log").write_text(
        health_process.stderr,
        encoding="utf-8",
    )

    if health_process.returncode != 0:
        errors.append(
            f"hermes-health exited with code {health_process.returncode}"
        )

    candidate_health = health_dir / "health.json"
    if candidate_health.exists():
        health_path = candidate_health
    else:
        errors.append("health.json was not generated")

    status = "COMPLETED" if not errors else "FAILED"
    exit_code = 0 if not errors else 1
    finished_at = _utc_now()

    # Mark COMPLETE on full success
    if work_queue and task_id and not errors:
        work_queue.mark_complete(task_id)

    result = RuntimeResult(
        run_id=run_id,
        command=list(command),
        working_directory=str(working_directory),
        started_at=started_at,
        finished_at=finished_at,
        execution_record_path=(
            str(execution_record_path) if execution_record_path else None
        ),
        review_path=str(review_path) if review_path else None,
        health_path=str(health_path) if health_path else None,
        exit_code=exit_code,
        status=status,
        errors=errors,
    )

    (run_dir / "runtime-result.json").write_text(
        json.dumps(asdict(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return result
