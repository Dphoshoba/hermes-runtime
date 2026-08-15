from __future__ import annotations

import json
import os
from pathlib import Path

from evosia.runtime import run_pipeline


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def test_pipeline_completes(tmp_path: Path, monkeypatch) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    runtime_root = tmp_path / "runtime"
    repository = tmp_path / "repo"
    repository.mkdir()

    _write_executable(
        bin_dir / "hermes-record",
        f"""#!/bin/sh
mkdir -p "{runtime_root}/evidence/exec-1"
cat > "{runtime_root}/evidence/exec-1/execution-record.json" <<'JSON'
{{"execution_record": {{"execution_id": "exec-1"}}}}
JSON
echo "{runtime_root}/evidence/exec-1/execution-record.json"
exit 0
""",
    )

    _write_executable(
        bin_dir / "hermes-review",
        f"""#!/bin/sh
mkdir -p "{runtime_root}/reviews/review-1"
cat > "{runtime_root}/reviews/review-1/review.json" <<'JSON'
{{"outcome": "REVIEW_PASSED"}}
JSON
echo "{runtime_root}/reviews/review-1/review.json"
exit 0
""",
    )

    _write_executable(
        bin_dir / "hermes-health",
        f"""#!/bin/sh
mkdir -p "{runtime_root}/health"
cat > "{runtime_root}/health/health.json" <<'JSON'
{{"overall_health": "HEALTHY"}}
JSON
echo "{runtime_root}/health/health.json"
exit 0
""",
    )

    monkeypatch.setenv(
        "PATH",
        f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
    )

    result = run_pipeline(
        ["echo", "hello"],
        runtime_root=runtime_root,
        repository=repository,
        working_directory=repository,
    )

    assert result.status == "COMPLETED"
    assert result.exit_code == 0
    assert result.execution_record_path is not None
    assert result.review_path is not None
    assert result.health_path is not None

    result_path = (
        runtime_root / "runs" / result.run_id / "runtime-result.json"
    )
    assert result_path.exists()
    assert json.loads(result_path.read_text())["status"] == "COMPLETED"


def test_pipeline_fails_when_recording_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    repository = tmp_path / "repo"
    repository.mkdir()

    _write_executable(
        bin_dir / "hermes-record",
        "#!/bin/sh\nexit 2\n",
    )

    _write_executable(
        bin_dir / "hermes-health",
        "#!/bin/sh\nexit 0\n",
    )

    monkeypatch.setenv(
        "PATH",
        f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
    )

    result = run_pipeline(
        ["false"],
        runtime_root=tmp_path / "runtime",
        repository=repository,
        working_directory=repository,
    )

    assert result.status == "FAILED"
    assert result.exit_code == 1
    assert result.execution_record_path is None
    assert result.errors
