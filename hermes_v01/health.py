from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


HEALTHY = "HEALTHY"
WARNING = "WARNING"
FAILED = "FAILED"
UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class HealthReport:
    runtime_version: str
    last_execution_id: str | None
    last_execution_time: str | None
    last_execution_exit_code: int | None
    last_supervisor_cycle: int | None
    last_supervisor_status: str | None
    last_review_outcome: str | None
    execution_record_count: int
    review_count: int
    supervisor_cycle_count: int
    last_failure: str | None
    overall_health: str


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _latest_record(paths: list[Path], time_getter) -> dict[str, Any] | None:
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for path in paths:
        data = _load_json(path)
        if not data:
            continue
        timestamp = _parse_time(time_getter(data))
        if timestamp is not None:
            candidates.append((timestamp, data))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def build_health_report(runtime_root: Path) -> HealthReport:
    evidence_dir = runtime_root / "evidence"
    supervisor_dir = runtime_root / "supervisor"
    reviews_dir = runtime_root / "reviews"
    reviewer_reviews_dir = runtime_root / "reviewer-reviews"

    execution_paths = sorted(evidence_dir.glob("exec-*/execution-record.json"))
    review_paths = sorted(reviews_dir.glob("review-*/review.json"))
    reviewer_review_paths = sorted(reviewer_reviews_dir.glob("review-*/review.json"))
    all_review_paths = review_paths + reviewer_review_paths
    supervisor_paths = sorted(supervisor_dir.glob("cycles/*/verification-report.json"))

    latest_execution = _latest_record(
        execution_paths,
        lambda data: data.get("execution_record", {}).get("end_time"),
    )
    latest_review = _latest_record(
        all_review_paths,
        lambda data: data.get("reviewed_at"),
    )
    latest_supervisor = _latest_record(
        supervisor_paths,
        lambda data: data.get("generated_at_utc"),
    )

    supervisor_state = _load_json(supervisor_dir / "supervisor-state.json") or {}

    last_execution_id = None
    last_execution_time = None
    last_execution_exit_code = None
    if latest_execution:
        execution = latest_execution.get("execution_record", {})
        last_execution_id = execution.get("execution_id")
        last_execution_time = execution.get("end_time")
        last_execution_exit_code = execution.get("exit_code")

    last_review_outcome = latest_review.get("outcome") if latest_review else None
    last_supervisor_cycle = supervisor_state.get("cycle_count")
    last_supervisor_status = supervisor_state.get("status")

    failures: list[str] = []
    if last_execution_exit_code not in (None, 0):
        failures.append(f"latest execution exit code: {last_execution_exit_code}")
    if last_review_outcome == "REVIEW_FAILED":
        failures.append("latest independent review failed")
    if last_supervisor_status not in (None, "RUNNING", "STOPPED"):
        failures.append(f"supervisor status: {last_supervisor_status}")

    if not execution_paths and not all_review_paths and not supervisor_paths:
        overall_health = UNKNOWN
    elif failures:
        overall_health = FAILED
    elif last_review_outcome in (None, "REVIEW_INCOMPLETE"):
        overall_health = WARNING
    else:
        overall_health = HEALTHY

    return HealthReport(
        runtime_version="0.2.0",
        last_execution_id=last_execution_id,
        last_execution_time=last_execution_time,
        last_execution_exit_code=last_execution_exit_code,
        last_supervisor_cycle=last_supervisor_cycle,
        last_supervisor_status=last_supervisor_status,
        last_review_outcome=last_review_outcome,
        execution_record_count=len(execution_paths),
        review_count=len(all_review_paths),
        supervisor_cycle_count=len(supervisor_paths),
        last_failure="; ".join(failures) if failures else None,
        overall_health=overall_health,
    )


def write_health_reports(report: HealthReport, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "health.json"
    md_path = output_dir / "health.md"

    json_path.write_text(
        json.dumps(asdict(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    md_path.write_text(
        "\n".join(
            [
                "# Hermes Runtime Health",
                "",
                f"- Overall health: **{report.overall_health}**",
                f"- Runtime version: `{report.runtime_version}`",
                f"- Last execution ID: `{report.last_execution_id}`",
                f"- Last execution time: `{report.last_execution_time}`",
                f"- Last execution exit code: `{report.last_execution_exit_code}`",
                f"- Last supervisor cycle: `{report.last_supervisor_cycle}`",
                f"- Last supervisor status: `{report.last_supervisor_status}`",
                f"- Last review outcome: `{report.last_review_outcome}`",
                f"- Execution records: `{report.execution_record_count}`",
                f"- Reviews: `{report.review_count}`",
                f"- Supervisor cycles: `{report.supervisor_cycle_count}`",
                f"- Last failure: `{report.last_failure}`",
                "",
            ]
        ),
        encoding="utf-8",
    )

    return json_path, md_path
