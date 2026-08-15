from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .evidence import EXECUTION_ID_PATTERN, canonical_json_bytes, parse_utc, utc_now
from .utils import format_utc, make_read_only, fsync_directory, sha256_file

REVIEW_ID_PATTERN = re.compile(r"^review-[0-9]{8}T[0-9]{6}(?:\.[0-9]{1,6})?Z-[0-9a-f]{12}$")
REVIEW_OUTCOMES = {"REVIEW_PASSED", "REVIEW_FAILED", "REVIEW_INCOMPLETE"}
SUPPORTED_SCHEMA_VERSIONS = {"1"}


@dataclass(frozen=True)
class ReviewCheck:
    name: str
    status: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ReviewEnvelope:
    schema_version: str
    review_id: str
    reviewed_execution_id: str | None
    reviewed_record_path: str
    reviewed_at: str
    outcome: str
    checks: tuple[ReviewCheck, ...]
    errors: tuple[str, ...]
    reviewed_evidence_paths: tuple[str, ...]
    review_sha256: str

    def __post_init__(self) -> None:
        if self.outcome not in REVIEW_OUTCOMES:
            raise ValueError(f"unknown reviewer outcome: {self.outcome}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "review_id": self.review_id,
            "reviewed_execution_id": self.reviewed_execution_id,
            "reviewed_record_path": self.reviewed_record_path,
            "reviewed_at": self.reviewed_at,
            "outcome": self.outcome,
            "checks": [check.as_dict() for check in self.checks],
            "errors": list(self.errors),
            "reviewed_evidence_paths": list(self.reviewed_evidence_paths),
            "review_sha256": self.review_sha256,
        }


@dataclass(frozen=True)
class PublishedReview:
    envelope: ReviewEnvelope
    review_json_path: str
    review_markdown_path: str


class ImmutableReviewStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

    def review_dir(self, review_id: str) -> Path:
        return self.root / review_id

    def publish(self, review_id: str, filename: str, payload: bytes) -> Path:
        directory = self.review_dir(review_id)
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / filename
        if destination.exists():
            raise FileExistsError(f"immutable review already exists: {destination}")

        fd, temporary_name = tempfile.mkstemp(prefix=f".{filename}.", suffix=".tmp", dir=str(directory))
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary_name, destination)
            except FileExistsError:
                raise FileExistsError(f"immutable review already exists: {destination}")
            self._fsync_directory(directory)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
        self._make_read_only(destination)
        return destination

    @staticmethod
    def _make_read_only(path: Path) -> None:
        make_read_only(path)

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        fsync_directory(directory)


class IndependentReviewer:
    """Read-only reviewer for one immutable EVOSIA execution record."""

    def __init__(self, output_dir: Path, *, clock: Callable[[], datetime] | None = None) -> None:
        self.store = ImmutableReviewStore(output_dir)
        self._clock = clock or utc_now

    def new_review_id(self) -> str:
        timestamp = self._clock().astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        return f"review-{timestamp}-{uuid.uuid4().hex[:12]}"

    def review(self, record_path: Path) -> PublishedReview:
        path = record_path.expanduser().resolve(strict=False)
        review_id = self.new_review_id()
        reviewed_at = format_utc(self._clock())
        checks: list[ReviewCheck] = []
        errors: list[str] = []
        reviewed_paths: list[str] = [str(path)]
        execution_id: str | None = None
        payload: Mapping[str, Any] | None = None
        incomplete = False

        if not path.exists() or not path.is_file():
            checks.append(ReviewCheck("record_exists", "FAIL", f"record is unavailable: {path}"))
            errors.append(f"record is unavailable: {path}")
            incomplete = True
        else:
            checks.append(ReviewCheck("record_exists", "PASS", str(path)))
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                checks.append(ReviewCheck("valid_json", "FAIL", str(exc)))
                errors.append(f"invalid execution record JSON: {exc}")
                incomplete = True
            else:
                if not isinstance(loaded, dict):
                    checks.append(ReviewCheck("valid_json", "FAIL", "top-level JSON must be an object"))
                    errors.append("top-level JSON must be an object")
                    incomplete = True
                else:
                    payload = loaded
                    checks.append(ReviewCheck("valid_json", "PASS", "JSON object parsed"))

        if payload is not None:
            self._check_schema(payload, checks, errors)
            execution = payload.get("execution_record")
            if not isinstance(execution, dict):
                checks.append(ReviewCheck("execution_record", "FAIL", "execution_record must be an object"))
                errors.append("execution_record must be an object")
                incomplete = True
            else:
                execution_id = execution.get("execution_id") if isinstance(execution.get("execution_id"), str) else None
                missing = self._missing_execution_fields(execution)
                if missing:
                    checks.append(ReviewCheck("required_fields", "FAIL", ", ".join(missing)))
                    errors.extend(f"missing required field: {field}" for field in missing)
                    incomplete = True
                else:
                    checks.append(ReviewCheck("required_fields", "PASS", "all required fields present"))
                self._check_execution_id(execution, checks, errors)
                self._check_timestamps(execution, checks, errors)
                self._check_exit_code(execution, checks, errors)
                self._check_repository_revision(execution, checks, errors)

            manifest = payload.get("artifact_manifest")
            if not isinstance(manifest, list):
                checks.append(ReviewCheck("artifact_manifest", "FAIL", "artifact_manifest must be an array"))
                errors.append("artifact_manifest must be an array")
                incomplete = True
            else:
                self._check_manifest(manifest, checks, errors, reviewed_paths)

            self._check_record_digest(payload, checks, errors)

        if incomplete:
            outcome = "REVIEW_INCOMPLETE"
        elif errors:
            outcome = "REVIEW_FAILED"
        else:
            outcome = "REVIEW_PASSED"

        base_payload = {
            "schema_version": "1",
            "review_id": review_id,
            "reviewed_execution_id": execution_id,
            "reviewed_record_path": str(path),
            "reviewed_at": reviewed_at,
            "outcome": outcome,
            "checks": [check.as_dict() for check in checks],
            "errors": errors,
            "reviewed_evidence_paths": reviewed_paths,
        }
        digest = hashlib.sha256(canonical_json_bytes(base_payload)).hexdigest()
        envelope = ReviewEnvelope(
            schema_version="1",
            review_id=review_id,
            reviewed_execution_id=execution_id,
            reviewed_record_path=str(path),
            reviewed_at=reviewed_at,
            outcome=outcome,
            checks=tuple(checks),
            errors=tuple(errors),
            reviewed_evidence_paths=tuple(reviewed_paths),
            review_sha256=digest,
        )
        json_path = self.store.publish(review_id, "review.json", canonical_json_bytes(envelope.as_dict()))
        markdown_path = self.store.publish(review_id, "review.md", self._markdown(envelope).encode("utf-8"))
        return PublishedReview(envelope, str(json_path), str(markdown_path))

    @staticmethod
    def _check_schema(payload: Mapping[str, Any], checks: list[ReviewCheck], errors: list[str]) -> None:
        value = payload.get("schema_version")
        if value in SUPPORTED_SCHEMA_VERSIONS:
            checks.append(ReviewCheck("schema_version", "PASS", str(value)))
        else:
            checks.append(ReviewCheck("schema_version", "FAIL", repr(value)))
            errors.append(f"unsupported schema version: {value!r}")

    @staticmethod
    def _missing_execution_fields(execution: Mapping[str, Any]) -> list[str]:
        required = (
            "execution_id", "command", "trigger", "working_directory", "start_time", "end_time",
            "exit_code", "stdout_path", "stderr_path", "artifacts",
        )
        missing: list[str] = []
        for field in required:
            if field not in execution or execution[field] is None:
                missing.append(field)
        return missing

    @staticmethod
    def _check_execution_id(execution: Mapping[str, Any], checks: list[ReviewCheck], errors: list[str]) -> None:
        value = execution.get("execution_id")
        if isinstance(value, str) and EXECUTION_ID_PATTERN.fullmatch(value):
            checks.append(ReviewCheck("execution_id", "PASS", value))
        else:
            checks.append(ReviewCheck("execution_id", "FAIL", repr(value)))
            errors.append("execution_id does not match canonical format")

    @staticmethod
    def _check_timestamps(execution: Mapping[str, Any], checks: list[ReviewCheck], errors: list[str]) -> None:
        start_raw = execution.get("start_time")
        end_raw = execution.get("end_time")
        try:
            if not isinstance(start_raw, str) or not isinstance(end_raw, str):
                raise ValueError("timestamps must be strings")
            start = parse_utc(start_raw)
            end = parse_utc(end_raw)
            if end < start:
                raise ValueError("end_time precedes start_time")
        except ValueError as exc:
            checks.append(ReviewCheck("timestamps", "FAIL", str(exc)))
            errors.append(f"invalid timestamps: {exc}")
        else:
            checks.append(ReviewCheck("timestamps", "PASS", f"{start_raw} <= {end_raw}"))

    @staticmethod
    def _check_exit_code(execution: Mapping[str, Any], checks: list[ReviewCheck], errors: list[str]) -> None:
        value = execution.get("exit_code")
        if isinstance(value, int) and not isinstance(value, bool):
            checks.append(ReviewCheck("exit_code", "PASS", str(value)))
        else:
            checks.append(ReviewCheck("exit_code", "FAIL", repr(value)))
            errors.append("exit_code must be an integer")

    @staticmethod
    def _check_repository_revision(execution: Mapping[str, Any], checks: list[ReviewCheck], errors: list[str]) -> None:
        value = execution.get("repository_revision")
        if value is None:
            checks.append(ReviewCheck("repository_revision", "PASS", "not recorded"))
        elif isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value):
            checks.append(ReviewCheck("repository_revision", "PASS", value))
        else:
            checks.append(ReviewCheck("repository_revision", "FAIL", repr(value)))
            errors.append("repository_revision must be null or a 40-character lowercase hex SHA")

    @staticmethod
    def _check_manifest(
        manifest: list[Any], checks: list[ReviewCheck], errors: list[str], reviewed_paths: list[str]
    ) -> None:
        if not manifest:
            checks.append(ReviewCheck("artifact_manifest", "FAIL", "manifest is empty"))
            errors.append("artifact_manifest is empty")
            return
        all_passed = True
        for index, item in enumerate(manifest):
            if not isinstance(item, dict):
                errors.append(f"artifact_manifest[{index}] must be an object")
                all_passed = False
                continue
            raw_path = item.get("path")
            expected_size = item.get("size_bytes")
            expected_sha = item.get("sha256")
            if not isinstance(raw_path, str) or not raw_path:
                errors.append(f"artifact_manifest[{index}].path is invalid")
                all_passed = False
                continue
            path = Path(raw_path)
            reviewed_paths.append(str(path.resolve(strict=False)))
            if not path.is_absolute() or not path.exists() or not path.is_file():
                errors.append(f"artifact is unavailable: {raw_path}")
                all_passed = False
                continue
            actual_size = path.stat().st_size
            actual_sha = sha256_file(path)
            if not isinstance(expected_size, int) or isinstance(expected_size, bool) or expected_size != actual_size:
                errors.append(f"artifact size mismatch: {raw_path}")
                all_passed = False
            if not isinstance(expected_sha, str) or expected_sha != actual_sha:
                errors.append(f"artifact SHA-256 mismatch: {raw_path}")
                all_passed = False
        checks.append(
            ReviewCheck(
                "artifact_manifest",
                "PASS" if all_passed else "FAIL",
                f"{len(manifest)} artifact entries checked",
            )
        )

    @staticmethod
    def _check_record_digest(payload: Mapping[str, Any], checks: list[ReviewCheck], errors: list[str]) -> None:
        recorded = payload.get("record_sha256")
        unsigned = dict(payload)
        unsigned.pop("record_sha256", None)
        calculated = hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
        if isinstance(recorded, str) and recorded == calculated:
            checks.append(ReviewCheck("record_sha256", "PASS", recorded))
        else:
            checks.append(ReviewCheck("record_sha256", "FAIL", f"recorded={recorded!r} calculated={calculated}"))
            errors.append("execution record SHA-256 mismatch")

    @staticmethod
    def _markdown(envelope: ReviewEnvelope) -> str:
        lines = [
            "# EVOSIA Independent Review",
            "",
            f"- Review ID: `{envelope.review_id}`",
            f"- Execution ID: `{envelope.reviewed_execution_id}`",
            f"- Outcome: **{envelope.outcome}**",
            f"- Reviewed at: `{envelope.reviewed_at}`",
            f"- Record: `{envelope.reviewed_record_path}`",
            "",
            "## Checks",
            "",
        ]
        for check in envelope.checks:
            lines.append(f"- **{check.status}** `{check.name}` — {check.detail}")
        lines.extend(["", "## Errors", ""])
        if envelope.errors:
            lines.extend(f"- {error}" for error in envelope.errors)
        else:
            lines.append("- None")
        lines.extend(["", f"Review SHA-256: `{envelope.review_sha256}`", ""])
        return "\n".join(lines)
