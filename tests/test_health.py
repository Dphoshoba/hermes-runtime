from __future__ import annotations

import json
from pathlib import Path

from evosia.health import FAILED, HEALTHY, UNKNOWN, build_health_report, write_health_reports


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_empty_runtime_is_unknown(tmp_path: Path) -> None:
    report = build_health_report(tmp_path)
    assert report.overall_health == UNKNOWN
    assert report.execution_record_count == 0
    assert report.review_count == 0
    assert report.supervisor_cycle_count == 0


def test_healthy_runtime(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "evidence" / "exec-1" / "execution-record.json",
        {
            "execution_record": {
                "execution_id": "exec-1",
                "end_time": "2026-08-04T11:00:00Z",
                "exit_code": 0,
            }
        },
    )
    _write_json(
        tmp_path / "reviews" / "review-1" / "review.json",
        {
            "reviewed_at": "2026-08-04T11:01:00Z",
            "outcome": "REVIEW_PASSED",
        },
    )
    _write_json(
        tmp_path / "supervisor" / "supervisor-state.json",
        {"cycle_count": 1, "status": "STOPPED"},
    )
    _write_json(
        tmp_path / "supervisor" / "cycles" / "000001" / "verification-report.json",
        {"generated_at_utc": "2026-08-04T11:02:00Z"},
    )

    report = build_health_report(tmp_path)
    assert report.overall_health == HEALTHY
    assert report.last_execution_id == "exec-1"
    assert report.last_review_outcome == "REVIEW_PASSED"


def test_failed_execution_marks_failed(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "evidence" / "exec-1" / "execution-record.json",
        {
            "execution_record": {
                "execution_id": "exec-1",
                "end_time": "2026-08-04T11:00:00Z",
                "exit_code": 1,
            }
        },
    )

    report = build_health_report(tmp_path)
    assert report.overall_health == FAILED
    assert "exit code" in (report.last_failure or "")


def test_failed_review_marks_failed(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reviews" / "review-1" / "review.json",
        {
            "reviewed_at": "2026-08-04T11:01:00Z",
            "outcome": "REVIEW_FAILED",
        },
    )

    report = build_health_report(tmp_path)
    assert report.overall_health == FAILED


def test_latest_execution_is_selected_deterministically(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "evidence" / "exec-1" / "execution-record.json",
        {
            "execution_record": {
                "execution_id": "exec-1",
                "end_time": "2026-08-04T10:00:00Z",
                "exit_code": 0,
            }
        },
    )
    _write_json(
        tmp_path / "evidence" / "exec-2" / "execution-record.json",
        {
            "execution_record": {
                "execution_id": "exec-2",
                "end_time": "2026-08-04T12:00:00Z",
                "exit_code": 0,
            }
        },
    )

    report = build_health_report(tmp_path)
    assert report.last_execution_id == "exec-2"


def test_reports_are_written(tmp_path: Path) -> None:
    report = build_health_report(tmp_path)
    json_path, md_path = write_health_reports(report, tmp_path / "health")

    assert json_path.exists()
    assert md_path.exists()
    assert json.loads(json_path.read_text())["overall_health"] == UNKNOWN
