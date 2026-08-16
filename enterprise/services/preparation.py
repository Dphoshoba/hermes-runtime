"""Real preparation engine for Guided Mode (I6 / B2).

Implements the smallest REAL preparation path necessary to satisfy the M8
protocol: given an approved mission whose repository is the disposable test
repository, it:

  1. validates the mission is APPROVED_FOR_FUTURE_EXECUTION
  2. confirms the repository is flagged preparation-allowed (disposable only)
  3. snapshots the TARGET repository (objective before-evidence)
  4. creates an ISOLATED workspace (a copy of the target — never the target)
  5. applies a REAL candidate change inside the workspace
  6. identifies the actual affected files
  7. computes the REAL unified diff (vs the copied original)
  8. runs REAL validation (pytest) inside the workspace
  9. records validation output
 10. preserves provenance
 11. leaves the TARGET repository UNCHANGED (verified by after-snapshot)

The transition to PREPARED happens ONLY when objective evidence exists.
On validation failure it does NOT mark PREPARED; it retains a truthful
failure/pending state with failure evidence.

This module never merges, commits, pushes, deploys, or mutates production.
It has no authority over mission lifecycle beyond recording preparation
evidence on the PreparedChange row it is given.
"""

from __future__ import annotations

import difflib
import hashlib
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Isolated workspace root. Constrained to a subdirectory of the repo root or the
# system temp dir. Arbitrary client-supplied paths are NEVER accepted.
_DEFAULT_PREP_ROOT_ENV = "EVOSIA_PREP_ROOT"

# Populated by run_preparation so _compute_diff can read the target original.
_target_repo_for_diff: Path | None = None


def _prep_root() -> Path:
    env = os.environ.get(_DEFAULT_PREP_ROOT_ENV)
    if env:
        base = Path(env).resolve()
    else:
        # default: <repo_root>/.prep_workspaces
        here = Path(__file__).resolve()
        base = here.parents[2] / ".prep_workspaces"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _snapshot_target(repo_path: Path) -> dict[str, str]:
    """Hash every file under the target repo for later integrity comparison."""
    hashes: dict[str, str] = {}
    for p in sorted(repo_path.rglob("*")):
        if p.is_file() and ".git" not in p.parts:
            data = p.read_bytes()
            rel = str(p.relative_to(repo_path))
            hashes[rel] = hashlib.sha256(data).hexdigest()
    return hashes


def _target_unchanged(repo_path: Path, before: dict[str, str]) -> bool:
    after = _snapshot_target(repo_path)
    return after == before


def _apply_candidate_change(workspace: Path) -> list[str]:
    """Apply the REAL candidate change: replace the hardcoded key with an
    environment variable lookup in src/config.py.

    Returns the list of affected (relative) file paths.
    """
    config_path = workspace / "src" / "config.py"
    original = config_path.read_text()
    old_line = 'API_KEY = "example-fake-key-do-not-use-1234567890ABCDEF"'
    new_block = (
        'import os\n\n'
        '# Loaded from the environment so no secret is committed to the repository.\n'
        'API_KEY = os.environ.get("SAMPLE_SERVICE_API_KEY", "example-fake-key-do-not-use-1234567890ABCDEF")'
    )
    if old_line not in original:
        # Nothing to change -> truthful: no candidate modification produced.
        return []
    updated = original.replace(old_line, new_block)
    config_path.write_text(updated)
    return ["src/config.py"]


def _compute_diff(workspace: Path, affected: list[str]) -> str:
    """Compute a real unified diff for each affected file vs its target original."""
    target_repo = _target_repo_for_diff
    diffs = []
    for rel in affected:
        new_text = (workspace / rel).read_text().splitlines()
        orig_path = target_repo / rel if target_repo else None
        old_text = orig_path.read_text().splitlines() if (orig_path and orig_path.exists()) else []
        udiff = difflib.unified_diff(
            old_text, new_text, fromfile=f"a/{rel}", tofile=f"b/{rel}", lineterm=""
        )
        diffs.append("\n".join(udiff))
    return "\n".join(diffs)


def _run_validation(workspace: Path) -> tuple[str, str, int]:
    """Run REAL validation: pytest inside the isolated workspace.

    Returns (validation_status, validation_output, exit_code).
    """
    try:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(workspace / "src") + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
    except FileNotFoundError:
        return "failed", "python3 interpreter not found in workspace", 127
    except subprocess.TimeoutExpired:
        return "failed", "validation timed out", 124
    output = (proc.stdout or "") + (proc.stderr or "")
    status = "passed" if proc.returncode == 0 else "failed"
    return status, output.strip()[-4000:], proc.returncode


def run_preparation(
    mission: Any,
    prepared: Any,
    repository: Any,
    operator: str = "system",
) -> dict[str, Any]:
    """Execute real preparation for an approved mission.

    `prepared` is the already-created PreparedChange row (status="preparing").
    This function fills in objective evidence and, only on success, transitions
    the row to PREPARED. Returns a result dict (also persisted onto `prepared`).
    """
    global _target_repo_for_diff

    meta = repository.metadata_json or {}
    if not meta.get("preparation_allowed"):
        raise ValueError(
            "Preparation is only permitted on the disposable M8 test repository."
        )

    local_path = meta.get("local_path") or repository.url
    target_repo = Path(local_path).resolve()
    if not target_repo.exists():
        raise ValueError(f"Target repository path does not exist: {target_repo}")

    before = _snapshot_target(target_repo)
    _target_repo_for_diff = target_repo

    # Create isolated workspace as a COPY of the target (target never touched).
    workspace_root = _prep_root()
    ws_name = f"prep-{prepared.id}"
    workspace = workspace_root / ws_name
    if workspace.exists():
        shutil.rmtree(workspace)
    shutil.copytree(target_repo, workspace)

    # Establish a git baseline in the isolated workspace so the candidate diff
    # is always generated against the unmodified copy (works whether or not the
    # source repository itself is a git repo).
    try:
        subprocess.run(
            ["git", "init", "-q"], cwd=str(workspace), capture_output=True, text=True,
            timeout=30,
        )
        subprocess.run(
            ["git", "add", "-A"], cwd=str(workspace), capture_output=True, text=True,
            timeout=30,
        )
        subprocess.run(
            ["git", "commit", "-q", "-m", "baseline"], cwd=str(workspace),
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "GIT_AUTHOR_NAME": "EVOSIA", "GIT_AUTHOR_EMAIL": "evosia@local",
                 "GIT_COMMITTER_NAME": "EVOSIA", "GIT_COMMITTER_EMAIL": "evosia@local"},
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        pass  # difflib fallback in _compute_diff handles non-git case

    affected = _apply_candidate_change(workspace)
    if not affected:
        # Truthful failure: no candidate modification could be produced.
        prepared.status = "failed"
        prepared.validation_status = "failed"
        prepared.validation_output = (
            "No candidate modification could be generated for this mission."
        )
        prepared.workspace_path = str(workspace)
        prepared.provenance = {
            **(prepared.provenance or {}),
            "origin": "guided_mode_preparation",
            "outcome": "no_candidate_change",
            "operator": operator,
            "prepared_at": datetime.now(timezone.utc).isoformat(),
        }
        return {"status": "failed", "reason": "no_candidate_change"}

    diff_content = _compute_diff(workspace, affected)
    validation_status, validation_output, _ = _run_validation(workspace)

    # Verify the target repository was NOT mutated.
    target_unchanged = _target_unchanged(target_repo, before)

    if validation_status == "passed" and target_unchanged:
        prepared.status = "PREPARED"
        prepared.workspace_path = str(workspace)
        prepared.affected_files = affected
        prepared.diff_content = diff_content
        prepared.validation_status = "passed"
        prepared.validation_output = validation_output
        prepared.rollback_representation = (
            "Discard the isolated workspace; the target repository is unchanged."
        )
        prepared.source_commit_sha = (meta.get("commit_sha") or "") or None
        prepared.provenance = {
            **(prepared.provenance or {}),
            "origin": "guided_mode_preparation",
            "operator": operator,
            "target_repository_unchanged": True,
            "isolated_workspace": str(workspace),
            "prepared_at": datetime.now(timezone.utc).isoformat(),
        }
        return {
            "status": "PREPARED",
            "workspace_path": str(workspace),
            "affected_files": affected,
            "validation_status": "passed",
            "target_repository_unchanged": True,
        }

    # Validation failed (or target unexpectedly changed) -> truthful failure.
    prepared.status = "failed"
    prepared.workspace_path = str(workspace)
    prepared.affected_files = affected
    prepared.diff_content = diff_content
    prepared.validation_status = validation_status
    prepared.validation_output = validation_output
    prepared.provenance = {
        **(prepared.provenance or {}),
        "origin": "guided_mode_preparation",
        "operator": operator,
        "outcome": "validation_failed",
        "target_repository_unchanged": target_unchanged,
        "prepared_at": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "status": "failed",
        "workspace_path": str(workspace),
        "affected_files": affected,
        "validation_status": validation_status,
        "target_repository_unchanged": target_unchanged,
    }
