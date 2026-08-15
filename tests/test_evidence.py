from __future__ import annotations

import json
import os
import stat
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from evosia.evidence import (
    EvidenceIntegrityChecker,
    EvidenceRecorder,
    ExecutionRecord,
    ImmutableEvidenceStore,
)


class Clock:
    def __init__(self) -> None:
        self.current = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        value = self.current
        self.current += timedelta(seconds=1)
        return value


def test_execute_writes_one_complete_immutable_record(tmp_path: Path) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    artifact = workdir / "result.json"
    script = workdir / "command.py"
    script.write_text(
        "from pathlib import Path\n"
        "print('observed stdout')\n"
        "Path('result.json').write_text('{\\\"ok\\\":true}\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    recorder = EvidenceRecorder(tmp_path / "evidence", clock=Clock())

    result = recorder.execute(
        [sys.executable, str(script)],
        working_directory=workdir,
        artifacts=[artifact],
    )

    envelope = result.envelope
    assert envelope.assessment.evidence_status == "OBSERVED"
    assert envelope.assessment.integrity_status == "PASSED"
    assert envelope.execution_record.exit_code == 0
    assert Path(result.record_path).exists()
    assert Path(result.stdout_path).read_text(encoding="utf-8") == "observed stdout\n"
    assert Path(result.stderr_path).read_text(encoding="utf-8") == ""
    assert artifact.exists()
    assert envelope.independent_review_status == "NOT_STARTED"
    assert len(envelope.artifact_manifest) == 3

    payload = json.loads(Path(result.record_path).read_text(encoding="utf-8"))
    assert payload["record_sha256"] == envelope.record_sha256
    assert payload["execution_record"]["exit_code"] == 0
    assert stat.S_IMODE(Path(result.record_path).stat().st_mode) & 0o222 == 0
    assert stat.S_IMODE(Path(result.stdout_path).stat().st_mode) & 0o222 == 0


def test_nonzero_exit_code_is_observed_without_being_reinterpreted(tmp_path: Path) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    recorder = EvidenceRecorder(tmp_path / "evidence", clock=Clock())

    result = recorder.execute(
        [sys.executable, "-c", "import sys; print('failure'); sys.exit(7)"],
        working_directory=workdir,
    )

    assert result.envelope.execution_record.exit_code == 7
    assert result.envelope.assessment.evidence_status == "OBSERVED"
    assert result.envelope.assessment.integrity_status == "PASSED"


def test_record_is_immutable_and_cannot_be_overwritten(tmp_path: Path) -> None:
    root = tmp_path / "evidence"
    store = ImmutableEvidenceStore(root)

    first = store.publish("exec-20260101T000000.000000Z-0123456789ab", "record.json", b"{}\n")

    with pytest.raises(FileExistsError, match="immutable evidence already exists"):
        store.publish("exec-20260101T000000.000000Z-0123456789ab", "record.json", b"different\n")
    assert first.read_bytes() == b"{}\n"


def test_incomplete_record_is_classified_without_inference() -> None:
    assessment = EvidenceIntegrityChecker().assess(
        ExecutionRecord(
            execution_id=None,
            command=None,
            trigger=None,
            working_directory=None,
            start_time=None,
            end_time=None,
            exit_code=None,
            stdout_path=None,
            stderr_path=None,
            artifacts=(),
        )
    )

    assert assessment.evidence_status == "INCOMPLETE"
    assert assessment.integrity_status == "NOT_EVALUATED"
    assert "missing required field: execution_id" in assessment.errors


def test_conflicting_record_is_classified_inconsistent(tmp_path: Path) -> None:
    stdout = tmp_path / "stdout.log"
    stderr = tmp_path / "stderr.log"
    stdout.write_text("", encoding="utf-8")
    stderr.write_text("", encoding="utf-8")
    record = ExecutionRecord(
        execution_id="exec-20260101T000000.000000Z-0123456789ab",
        command="python command.py",
        trigger="LOCAL_TERMINAL",
        working_directory=str(tmp_path),
        start_time="2026-01-01T00:00:02Z",
        end_time="2026-01-01T00:00:01Z",
        exit_code=0,
        stdout_path=str(stdout),
        stderr_path=str(stderr),
        artifacts=(str(tmp_path / "missing.json"),),
    )

    assessment = EvidenceIntegrityChecker().assess(record)

    assert assessment.evidence_status == "EVIDENCE_INCONSISTENT"
    assert assessment.integrity_status == "FAILED"
    assert "end_time precedes start_time" in assessment.errors
    assert any("artifact does not exist" in error for error in assessment.errors)


def test_repository_revision_is_captured_when_available(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    if os.system(f"git -C {repo} init -q") != 0:
        pytest.skip("git unavailable")
    (repo / "file.txt").write_text("content\n", encoding="utf-8")
    os.system(f"git -C {repo} add file.txt")
    os.system(
        f"git -C {repo} -c user.email=test@example.com -c user.name=Test commit -q -m initial"
    )
    recorder = EvidenceRecorder(tmp_path / "evidence", clock=Clock())

    result = recorder.execute(
        [sys.executable, "-c", "print('ok')"],
        working_directory=repo,
        repository=repo,
    )

    revision = result.envelope.execution_record.repository_revision
    assert revision is not None
    assert len(revision) == 40
