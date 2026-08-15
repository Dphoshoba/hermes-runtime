from __future__ import annotations

import json
import stat
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from evosia.evidence import EvidenceRecorder
from evosia.reviewer import IndependentReviewer, ImmutableReviewStore


class Clock:
    def __init__(self) -> None:
        self.current = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        value = self.current
        self.current += timedelta(seconds=1)
        return value


def create_record(tmp_path: Path) -> Path:
    work = tmp_path / "work"
    work.mkdir()
    recorder = EvidenceRecorder(tmp_path / "evidence", clock=Clock())
    result = recorder.execute([sys.executable, "-c", "print('ok')"], working_directory=work)
    return Path(result.record_path)


def review(record: Path, tmp_path: Path):
    return IndependentReviewer(tmp_path / "reviews", clock=Clock()).review(record)


def test_valid_record_passes_and_publishes_immutable_json_and_markdown(tmp_path: Path) -> None:
    result = review(create_record(tmp_path), tmp_path)

    assert result.envelope.outcome == "REVIEW_PASSED"
    assert Path(result.review_json_path).exists()
    assert Path(result.review_markdown_path).exists()
    assert stat.S_IMODE(Path(result.review_json_path).stat().st_mode) & 0o222 == 0
    assert stat.S_IMODE(Path(result.review_markdown_path).stat().st_mode) & 0o222 == 0


def test_missing_record_is_incomplete(tmp_path: Path) -> None:
    result = review(tmp_path / "missing.json", tmp_path)
    assert result.envelope.outcome == "REVIEW_INCOMPLETE"
    assert any("record is unavailable" in error for error in result.envelope.errors)


def test_malformed_json_is_incomplete(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{", encoding="utf-8")
    result = review(path, tmp_path)
    assert result.envelope.outcome == "REVIEW_INCOMPLETE"


def test_unsupported_schema_fails(tmp_path: Path) -> None:
    path = create_record(tmp_path)
    payload = json.loads(path.read_text())
    path.chmod(0o644)
    payload["schema_version"] = "999"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = review(path, tmp_path)
    assert result.envelope.outcome == "REVIEW_FAILED"
    assert any("unsupported schema" in error for error in result.envelope.errors)


def test_missing_stdout_is_failed(tmp_path: Path) -> None:
    path = create_record(tmp_path)
    payload = json.loads(path.read_text())
    Path(payload["execution_record"]["stdout_path"]).chmod(0o644)
    Path(payload["execution_record"]["stdout_path"]).unlink()
    result = review(path, tmp_path)
    assert result.envelope.outcome == "REVIEW_FAILED"
    assert any("artifact is unavailable" in error for error in result.envelope.errors)


def test_hash_mismatch_is_failed(tmp_path: Path) -> None:
    path = create_record(tmp_path)
    payload = json.loads(path.read_text())
    stdout = Path(payload["execution_record"]["stdout_path"])
    stdout.chmod(0o644)
    stdout.write_text("altered\n", encoding="utf-8")
    result = review(path, tmp_path)
    assert result.envelope.outcome == "REVIEW_FAILED"
    assert any("SHA-256 mismatch" in error for error in result.envelope.errors)


def test_size_mismatch_is_failed(tmp_path: Path) -> None:
    path = create_record(tmp_path)
    payload = json.loads(path.read_text())
    path.chmod(0o644)
    payload["artifact_manifest"][0]["size_bytes"] += 1
    unsigned = dict(payload)
    unsigned.pop("record_sha256")
    from evosia.evidence import canonical_json_bytes
    import hashlib
    payload["record_sha256"] = hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = review(path, tmp_path)
    assert result.envelope.outcome == "REVIEW_FAILED"
    assert any("size mismatch" in error for error in result.envelope.errors)


def test_invalid_timestamps_fail(tmp_path: Path) -> None:
    path = create_record(tmp_path)
    payload = json.loads(path.read_text())
    path.chmod(0o644)
    payload["execution_record"]["end_time"] = "2025-01-01T00:00:00Z"
    unsigned = dict(payload)
    unsigned.pop("record_sha256")
    from evosia.evidence import canonical_json_bytes
    import hashlib
    payload["record_sha256"] = hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = review(path, tmp_path)
    assert result.envelope.outcome == "REVIEW_FAILED"
    assert any("end_time precedes" in error for error in result.envelope.errors)


def test_incomplete_record_is_incomplete(tmp_path: Path) -> None:
    path = create_record(tmp_path)
    payload = json.loads(path.read_text())
    path.chmod(0o644)
    payload["execution_record"]["exit_code"] = None
    unsigned = dict(payload)
    unsigned.pop("record_sha256")
    from evosia.evidence import canonical_json_bytes
    import hashlib
    payload["record_sha256"] = hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = review(path, tmp_path)
    assert result.envelope.outcome == "REVIEW_INCOMPLETE"


def test_altered_record_digest_fails(tmp_path: Path) -> None:
    path = create_record(tmp_path)
    payload = json.loads(path.read_text())
    path.chmod(0o644)
    payload["execution_record"]["trigger"] = "ALTERED"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = review(path, tmp_path)
    assert result.envelope.outcome == "REVIEW_FAILED"
    assert any("record SHA-256 mismatch" in error for error in result.envelope.errors)


def test_store_refuses_overwrite(tmp_path: Path) -> None:
    store = ImmutableReviewStore(tmp_path / "reviews")
    store.publish("review-20260101T000000.000000Z-0123456789ab", "review.json", b"{}\n")
    with pytest.raises(FileExistsError):
        store.publish("review-20260101T000000.000000Z-0123456789ab", "review.json", b"different\n")
