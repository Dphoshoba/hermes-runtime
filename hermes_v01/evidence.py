from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
import tempfile
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

EXECUTION_ID_PATTERN = re.compile(r"^exec-[0-9]{8}T[0-9]{6}(?:\.[0-9]{1,6})?Z-[0-9a-f]{12}$")
EVIDENCE_STATUSES = {"OBSERVED", "INCOMPLETE", "EVIDENCE_INCONSISTENT"}
INTEGRITY_STATUSES = {"PASSED", "FAILED", "NOT_EVALUATED"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(data: Mapping[str, Any]) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8")


@dataclass(frozen=True)
class ArtifactEvidence:
    path: str
    size_bytes: int
    sha256: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionRecord:
    execution_id: str | None
    command: str | None
    trigger: str | None
    working_directory: str | None
    start_time: str | None
    end_time: str | None
    exit_code: int | None
    stdout_path: str | None
    stderr_path: str | None
    artifacts: tuple[str, ...] = ()
    repository_revision: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["artifacts"] = list(self.artifacts)
        return data


@dataclass(frozen=True)
class EvidenceAssessment:
    evidence_status: str
    integrity_status: str
    errors: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.evidence_status not in EVIDENCE_STATUSES:
            raise ValueError(f"unknown evidence status: {self.evidence_status}")
        if self.integrity_status not in INTEGRITY_STATUSES:
            raise ValueError(f"unknown integrity status: {self.integrity_status}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "evidence_status": self.evidence_status,
            "integrity_status": self.integrity_status,
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class EvidenceEnvelope:
    schema_version: str
    execution_record: ExecutionRecord
    assessment: EvidenceAssessment
    artifact_manifest: tuple[ArtifactEvidence, ...]
    independent_review_status: str
    record_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "execution_record": self.execution_record.as_dict(),
            **self.assessment.as_dict(),
            "artifact_manifest": [item.as_dict() for item in self.artifact_manifest],
            "independent_review_status": self.independent_review_status,
            "record_sha256": self.record_sha256,
        }


@dataclass(frozen=True)
class RecordedExecution:
    envelope: EvidenceEnvelope
    record_path: str
    stdout_path: str
    stderr_path: str


class EvidenceIntegrityChecker:
    """Validates completeness and internal consistency without judging success."""

    REQUIRED_TEXT_FIELDS = (
        "execution_id",
        "command",
        "trigger",
        "working_directory",
        "start_time",
        "end_time",
        "stdout_path",
        "stderr_path",
    )

    def assess(self, record: ExecutionRecord) -> EvidenceAssessment:
        missing: list[str] = []
        errors: list[str] = []

        for field_name in self.REQUIRED_TEXT_FIELDS:
            value = getattr(record, field_name)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(field_name)
        if record.exit_code is None:
            missing.append("exit_code")

        if missing:
            return EvidenceAssessment(
                evidence_status="INCOMPLETE",
                integrity_status="NOT_EVALUATED",
                errors=tuple(f"missing required field: {field}" for field in missing),
            )

        assert record.execution_id is not None
        assert record.command is not None
        assert record.working_directory is not None
        assert record.start_time is not None
        assert record.end_time is not None
        assert record.stdout_path is not None
        assert record.stderr_path is not None

        if not EXECUTION_ID_PATTERN.fullmatch(record.execution_id):
            errors.append("execution_id does not match the canonical format")
        if not record.command.strip():
            errors.append("command must not be empty")
        if not isinstance(record.exit_code, int) or isinstance(record.exit_code, bool):
            errors.append("exit_code must be an integer")

        try:
            start = parse_utc(record.start_time)
            end = parse_utc(record.end_time)
            if end < start:
                errors.append("end_time precedes start_time")
        except ValueError as exc:
            errors.append(f"invalid timestamp: {exc}")

        workdir = Path(record.working_directory)
        if not workdir.is_absolute():
            errors.append("working_directory must be absolute")
        elif not workdir.exists() or not workdir.is_dir():
            errors.append("working_directory does not exist or is not a directory")

        paths: list[tuple[str, str]] = [
            ("stdout_path", record.stdout_path),
            ("stderr_path", record.stderr_path),
            *(("artifact", path) for path in record.artifacts),
        ]
        seen: set[str] = set()
        for label, raw_path in paths:
            path = Path(raw_path)
            if not path.is_absolute():
                errors.append(f"{label} must be absolute: {raw_path}")
                continue
            normalized = str(path.resolve(strict=False))
            if normalized in seen:
                errors.append(f"duplicate evidence path: {normalized}")
            seen.add(normalized)
            if not path.exists() or not path.is_file():
                errors.append(f"{label} does not exist or is not a file: {raw_path}")

        if errors:
            return EvidenceAssessment(
                evidence_status="EVIDENCE_INCONSISTENT",
                integrity_status="FAILED",
                errors=tuple(errors),
            )
        return EvidenceAssessment(
            evidence_status="OBSERVED",
            integrity_status="PASSED",
            errors=(),
        )


class ImmutableEvidenceStore:
    """Publishes evidence records atomically and refuses overwrites."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

    def execution_dir(self, execution_id: str) -> Path:
        return self.root / execution_id

    def publish(self, execution_id: str, filename: str, payload: bytes) -> Path:
        directory = self.execution_dir(execution_id)
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / filename
        if destination.exists():
            raise FileExistsError(f"immutable evidence already exists: {destination}")

        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{filename}.", suffix=".tmp", dir=str(directory)
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary_name, destination)
            except FileExistsError:
                raise FileExistsError(f"immutable evidence already exists: {destination}")
            self._fsync_directory(directory)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
        self._make_read_only(destination)
        return destination

    @staticmethod
    def _make_read_only(path: Path) -> None:
        mode = stat.S_IMODE(path.stat().st_mode)
        path.chmod(mode & ~0o222)

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            flags |= os.O_DIRECTORY
        descriptor = os.open(directory, flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


class EvidenceRecorder:
    """Executes one command and writes one immutable evidence envelope."""

    def __init__(
        self,
        root: Path,
        *,
        checker: EvidenceIntegrityChecker | None = None,
        clock: callable | None = None,
    ) -> None:
        self.store = ImmutableEvidenceStore(root)
        self.checker = checker or EvidenceIntegrityChecker()
        self._clock = clock or utc_now

    def new_execution_id(self) -> str:
        timestamp = self._clock().astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        suffix = uuid.uuid4().hex[:12]
        return f"exec-{timestamp}-{suffix}"

    def execute(
        self,
        command: Sequence[str],
        *,
        working_directory: Path,
        trigger: str = "LOCAL_TERMINAL",
        artifacts: Iterable[Path] = (),
        repository: Path | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> RecordedExecution:
        if not command:
            raise ValueError("command must not be empty")
        workdir = working_directory.expanduser().resolve()
        if not workdir.exists() or not workdir.is_dir():
            raise FileNotFoundError(f"working directory is unavailable: {workdir}")

        execution_id = self.new_execution_id()
        execution_dir = self.store.execution_dir(execution_id)
        execution_dir.mkdir(parents=True, exist_ok=False)
        stdout_path = execution_dir / "stdout.log"
        stderr_path = execution_dir / "stderr.log"

        start_time = format_utc(self._clock())
        with stdout_path.open("wb") as stdout_handle, stderr_path.open("wb") as stderr_handle:
            completed = subprocess.run(
                list(command),
                cwd=workdir,
                env=dict(environment) if environment is not None else None,
                stdout=stdout_handle,
                stderr=stderr_handle,
                check=False,
            )
            stdout_handle.flush()
            stderr_handle.flush()
            os.fsync(stdout_handle.fileno())
            os.fsync(stderr_handle.fileno())
        end_time = format_utc(self._clock())

        artifact_paths = tuple(Path(path).expanduser().resolve() for path in artifacts)
        record = ExecutionRecord(
            execution_id=execution_id,
            command=shlex.join(str(part) for part in command),
            trigger=trigger,
            working_directory=str(workdir),
            start_time=start_time,
            end_time=end_time,
            exit_code=completed.returncode,
            stdout_path=str(stdout_path.resolve()),
            stderr_path=str(stderr_path.resolve()),
            artifacts=tuple(str(path) for path in artifact_paths),
            repository_revision=self._repository_revision(repository),
        )
        assessment = self.checker.assess(record)
        manifest = self._artifact_manifest(record)
        record_payload = {
            "schema_version": "1",
            "execution_record": record.as_dict(),
            **assessment.as_dict(),
            "artifact_manifest": [item.as_dict() for item in manifest],
            "independent_review_status": "NOT_STARTED",
        }
        record_sha256 = hashlib.sha256(canonical_json_bytes(record_payload)).hexdigest()
        envelope = EvidenceEnvelope(
            schema_version="1",
            execution_record=record,
            assessment=assessment,
            artifact_manifest=manifest,
            independent_review_status="NOT_STARTED",
            record_sha256=record_sha256,
        )

        record_path = self.store.publish(
            execution_id,
            "execution-record.json",
            canonical_json_bytes(envelope.as_dict()),
        )
        self._freeze_existing_file(stdout_path)
        self._freeze_existing_file(stderr_path)
        return RecordedExecution(
            envelope=envelope,
            record_path=str(record_path),
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
        )

    def record(self, record: ExecutionRecord) -> EvidenceEnvelope:
        if record.execution_id is None:
            raise ValueError("execution_id is required to publish evidence")
        assessment = self.checker.assess(record)
        manifest = self._artifact_manifest(record)
        payload = {
            "schema_version": "1",
            "execution_record": record.as_dict(),
            **assessment.as_dict(),
            "artifact_manifest": [item.as_dict() for item in manifest],
            "independent_review_status": "NOT_STARTED",
        }
        digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
        envelope = EvidenceEnvelope(
            schema_version="1",
            execution_record=record,
            assessment=assessment,
            artifact_manifest=manifest,
            independent_review_status="NOT_STARTED",
            record_sha256=digest,
        )
        self.store.publish(
            record.execution_id,
            "execution-record.json",
            canonical_json_bytes(envelope.as_dict()),
        )
        return envelope

    @staticmethod
    def _repository_revision(repository: Path | None) -> str | None:
        if repository is None:
            return None
        repo = repository.expanduser().resolve()
        try:
            result = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except OSError:
            return None
        revision = result.stdout.strip()
        return revision if result.returncode == 0 and revision else None

    @staticmethod
    def _artifact_manifest(record: ExecutionRecord) -> tuple[ArtifactEvidence, ...]:
        paths = [record.stdout_path, record.stderr_path, *record.artifacts]
        manifest: list[ArtifactEvidence] = []
        for raw_path in paths:
            if raw_path is None:
                continue
            path = Path(raw_path)
            if path.exists() and path.is_file():
                manifest.append(
                    ArtifactEvidence(
                        path=str(path.resolve()),
                        size_bytes=path.stat().st_size,
                        sha256=sha256_file(path),
                    )
                )
        return tuple(manifest)

    @staticmethod
    def _freeze_existing_file(path: Path) -> None:
        if path.exists():
            ImmutableEvidenceStore._make_read_only(path)
