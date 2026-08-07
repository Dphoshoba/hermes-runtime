from __future__ import annotations

import json
import statistics
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ExecutionMetrics:
    """Metrics for a single execution."""
    execution_id: str
    task_id: str | None
    command: str
    start_time: str
    end_time: str
    duration_seconds: float
    exit_code: int
    status: str  # COMPLETED, FAILED, RETRYING
    error: str | None = None


@dataclass(frozen=True)
class QueueMetrics:
    """Aggregate queue metrics."""
    total_tasks: int
    tasks_by_state: dict[str, int]
    ready_tasks: int
    blocked_tasks: int
    running_tasks: int
    completed_tasks: int
    failed_tasks: int
    pending_verification_tasks: int
    average_attempts: float
    max_attempts: int
    retryable_tasks: int
    non_retryable_tasks: int


@dataclass(frozen=True)
class RuntimeMetrics:
    """Aggregate runtime metrics."""
    total_executions: int
    successful_executions: int
    failed_executions: int
    retry_executions: int
    average_duration_seconds: float
    median_duration_seconds: float
    p95_duration_seconds: float
    throughput_per_minute: float
    first_execution_time: str | None
    last_execution_time: str | None
    execution_metrics: list[ExecutionMetrics] = field(default_factory=list)


@dataclass(frozen=True)
class FailureClassification:
    """Classification of a failure."""
    category: str  # TRANSIENT, PERMANENT, INFRASTRUCTURE, DEPENDENCY, VALIDATION
    recoverable: bool
    suggested_action: str
    error_signature: str


def classify_failure(error: str, exit_code: int | None, task_state: str) -> FailureClassification:
    """Classify a failure based on error message, exit code, and task state."""
    error_lower = error.lower() if error else ""
    
    # Dependency failures (check first - more specific)
    if any(kw in error_lower for kw in ["modulenotfounderror", "importerror", "import error", "module not found", "no module named"]):
        return FailureClassification(
            category="DEPENDENCY",
            recoverable=False,
            suggested_action="Resolve missing dependencies before retry",
            error_signature=error[:100]
        )
    
    if any(kw in error_lower for kw in ["dependency", "missing", "not found", "file not found", "no such file"]):
        return FailureClassification(
            category="DEPENDENCY",
            recoverable=False,
            suggested_action="Resolve missing dependencies before retry",
            error_signature=error[:100]
        )
    
    # Infrastructure failures
    if any(kw in error_lower for kw in ["connection refused", "timeout", "network", "dns", "unreachable", "connection reset", "connection timed out"]):
        return FailureClassification(
            category="INFRASTRUCTURE",
            recoverable=True,
            suggested_action="Retry after delay; check network connectivity",
            error_signature=error[:100]
        )
    
    # Transient failures
    if any(kw in error_lower for kw in ["temporary", "retry", "rate limit", "busy", "locked", "try again"]):
        return FailureClassification(
            category="TRANSIENT",
            recoverable=True,
            suggested_action="Retry with exponential backoff",
            error_signature=error[:100]
        )
    
    # Validation failures
    if any(kw in error_lower for kw in ["validation", "schema", "assert", "test failed", "verification failed", "assertionerror"]):
        return FailureClassification(
            category="VALIDATION",
            recoverable=False,
            suggested_action="Fix validation errors; do not retry",
            error_signature=error[:100]
        )
    
    # Exit code based classification
    if exit_code is not None:
        if exit_code == 124:  # timeout
            return FailureClassification(
                category="TRANSIENT",
                recoverable=True,
                suggested_action="Increase timeout or optimize execution",
                error_signature=f"exit_code={exit_code}"
            )
        if exit_code in (137, 143):  # SIGKILL, SIGTERM
            return FailureClassification(
                category="INFRASTRUCTURE",
                recoverable=True,
                suggested_action="Investigate process termination cause",
                error_signature=f"exit_code={exit_code}"
            )
        if exit_code == 2:  # usage/config error
            return FailureClassification(
                category="VALIDATION",
                recoverable=False,
                suggested_action="Fix command usage or configuration",
                error_signature=f"exit_code={exit_code}"
            )
    
    # Task state based
    if task_state == "VERIFICATION_PENDING":
        return FailureClassification(
            category="VALIDATION",
            recoverable=False,
            suggested_action="Review failed; fix underlying issue",
            error_signature=error[:100] if error else "review_failed"
        )
    
    # Default: treat as transient
    return FailureClassification(
        category="TRANSIENT",
        recoverable=True,
        suggested_action="Retry with exponential backoff",
        error_signature=error[:100] if error else "unknown"
    )


def compute_queue_metrics(work_queue) -> QueueMetrics:
    """Compute aggregate metrics from a WorkQueueManager."""
    items = work_queue.state.items
    if not items:
        return QueueMetrics(
            total_tasks=0,
            tasks_by_state={},
            ready_tasks=0,
            blocked_tasks=0,
            running_tasks=0,
            completed_tasks=0,
            failed_tasks=0,
            pending_verification_tasks=0,
            average_attempts=0.0,
            max_attempts=0,
            retryable_tasks=0,
            non_retryable_tasks=0,
        )
    
    tasks_by_state: dict[str, int] = {}
    attempts = []
    retryable = 0
    non_retryable = 0
    
    for item in items:
        tasks_by_state[item.state] = tasks_by_state.get(item.state, 0) + 1
        attempts.append(item.attempts)
        if item.retryable:
            retryable += 1
        else:
            non_retryable += 1
    
    return QueueMetrics(
        total_tasks=len(items),
        tasks_by_state=tasks_by_state,
        ready_tasks=tasks_by_state.get("READY", 0),
        blocked_tasks=tasks_by_state.get("BLOCKED", 0),
        running_tasks=tasks_by_state.get("RUNNING", 0),
        completed_tasks=tasks_by_state.get("COMPLETE", 0),
        failed_tasks=tasks_by_state.get("VERIFICATION_PENDING", 0) + tasks_by_state.get("OBSERVED", 0),  # in-progress failed
        pending_verification_tasks=tasks_by_state.get("VERIFICATION_PENDING", 0),
        average_attempts=statistics.mean(attempts) if attempts else 0.0,
        max_attempts=max(attempts) if attempts else 0,
        retryable_tasks=retryable,
        non_retryable_tasks=non_retryable,
    )


def compute_runtime_metrics(runtime_root: Path) -> RuntimeMetrics:
    """Compute aggregate runtime metrics from evidence records."""
    evidence_dir = runtime_root / "evidence"
    execution_paths = sorted(evidence_dir.glob("exec-*/execution-record.json"))
    
    metrics: list[ExecutionMetrics] = []
    durations: list[float] = []
    
    for path in execution_paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            execution = data.get("execution_record", {})
            
            start_time = execution.get("start_time")
            end_time = execution.get("end_time")
            exit_code = execution.get("exit_code", 0)
            execution_id = execution.get("execution_id", "")
            command = execution.get("command", "")
            
            duration = 0.0
            if start_time and end_time:
                start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                duration = (end - start).total_seconds()
                durations.append(duration)
            
            status = "COMPLETED" if exit_code == 0 else "FAILED"
            
            metrics.append(ExecutionMetrics(
                execution_id=execution_id,
                task_id=None,  # Not stored in evidence
                command=command,
                start_time=start_time or "",
                end_time=end_time or "",
                duration_seconds=duration,
                exit_code=exit_code,
                status=status,
            ))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
    
    if not durations:
        return RuntimeMetrics(
            total_executions=0,
            successful_executions=0,
            failed_executions=0,
            retry_executions=0,
            average_duration_seconds=0.0,
            median_duration_seconds=0.0,
            p95_duration_seconds=0.0,
            throughput_per_minute=0.0,
            first_execution_time=None,
            last_execution_time=None,
            execution_metrics=[],
        )
    
    durations.sort()
    successful = sum(1 for m in metrics if m.status == "COMPLETED")
    failed = sum(1 for m in metrics if m.status == "FAILED")
    
    # Calculate throughput (executions per minute over total time window)
    first_time = datetime.fromisoformat(metrics[0].start_time.replace("Z", "+00:00")) if metrics[0].start_time else None
    last_time = datetime.fromisoformat(metrics[-1].end_time.replace("Z", "+00:00")) if metrics[-1].end_time else None
    
    throughput = 0.0
    if first_time and last_time and last_time > first_time:
        window_minutes = (last_time - first_time).total_seconds() / 60.0
        throughput = len(metrics) / window_minutes if window_minutes > 0 else 0.0
    
    return RuntimeMetrics(
        total_executions=len(metrics),
        successful_executions=successful,
        failed_executions=failed,
        retry_executions=0,  # Would need queue state to compute
        average_duration_seconds=statistics.mean(durations),
        median_duration_seconds=statistics.median(durations),
        p95_duration_seconds=durations[int(len(durations) * 0.95)] if len(durations) > 1 else durations[0],
        throughput_per_minute=throughput,
        first_execution_time=metrics[0].start_time,
        last_execution_time=metrics[-1].end_time,
        execution_metrics=metrics,
    )


def write_metrics_report(metrics: RuntimeMetrics, queue_metrics: QueueMetrics | None, output_dir: Path) -> tuple[Path, Path]:
    """Write metrics report as JSON and Markdown."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    json_path = output_dir / "metrics.json"
    md_path = output_dir / "metrics.md"
    
    report = {
        "runtime_metrics": asdict(metrics),
    }
    if queue_metrics:
        report["queue_metrics"] = asdict(queue_metrics)
    
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    
    md_lines = [
        "# Hermes Runtime Metrics",
        "",
        "## Runtime Metrics",
        "",
        f"- Total executions: `{metrics.total_executions}`",
        f"- Successful: `{metrics.successful_executions}`",
        f"- Failed: `{metrics.failed_executions}`",
        f"- Average duration: `{metrics.average_duration_seconds:.3f}s`",
        f"- Median duration: `{metrics.median_duration_seconds:.3f}s`",
        f"- P95 duration: `{metrics.p95_duration_seconds:.3f}s`",
        f"- Throughput: `{metrics.throughput_per_minute:.2f} executions/minute`",
        f"- First execution: `{metrics.first_execution_time}`",
        f"- Last execution: `{metrics.last_execution_time}`",
        "",
    ]
    
    if queue_metrics:
        md_lines.extend([
            "## Queue Metrics",
            "",
            f"- Total tasks: `{queue_metrics.total_tasks}`",
            f"- Ready: `{queue_metrics.ready_tasks}`",
            f"- Blocked: `{queue_metrics.blocked_tasks}`",
            f"- Running: `{queue_metrics.running_tasks}`",
            f"- Completed: `{queue_metrics.completed_tasks}`",
            f"- Pending verification: `{queue_metrics.pending_verification_tasks}`",
            f"- Average attempts: `{queue_metrics.average_attempts:.2f}`",
            f"- Max attempts: `{queue_metrics.max_attempts}`",
            f"- Retryable: `{queue_metrics.retryable_tasks}`",
            f"- Non-retryable: `{queue_metrics.non_retryable_tasks}`",
            "",
            "### Tasks by State",
            "",
        ])
        for state, count in sorted(queue_metrics.tasks_by_state.items()):
            md_lines.append(f"- {state}: `{count}`")
        md_lines.append("")
    
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    
    return json_path, md_path