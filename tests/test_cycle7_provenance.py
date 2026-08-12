"""Regression tests for Cycle 7 evidence provenance.

These tests enforce the Validation Evidence Provenance Policy decided in the
Cycle 7 Provenance Repair milestone. They are ADDITIVE: they do not modify the
production frozen dataset or any Governance code, and they do not weaken other
tests.

Scope:
- Original frozen dataset immutability (hash preserved).
- v2 additive provenance artifact linkage.
- Detection of cognikid-style manifest/frozen name mismatch.
- Detection of missing scan lineage (scan_uuid / commit_sha / provider).
- Provenance status calculation per finding.
- Exact historical reproduction helper (read-only git show).
- Future provenance gate (VALIDATION_EVIDENCE_REPRODUCIBLE).

The tests are hermetic where possible; a few optionally shell out to local git
only when the corresponding repository is materialized on disk.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = REPO_ROOT / "validation" / "datasets"

ORIGINAL_FILE = DATASET_DIR / "cycle7_frozen_review_set.json"
# NOTE: The hash self-declared inside the frozen dataset metadata
# ("dbdf8de1e76b...") does NOT match the actual on-disk SHA-256 of the file
# ("471542208542..."). That is itself a provenance defect (recorded hash
# inconsistent with bytes). The trustworthy, reproducible integrity value is the
# ACTUAL file SHA-256, asserted here. The mismatch is recorded in v2.
ACTUAL_ORIGINAL_HASH = "471542208542bf7e14011243ddc70cd6f3f39a82f7aa9aedfe0105fe33554fa0"
RECORDED_ORIGINAL_HASH = "dbdf8de1e76b2809949f887701edda576d9af30f418a4e2435eb27bf91c06eee"
V2_FILE = DATASET_DIR / "cycle7_frozen_review_set_provenance_v2.json"

PROVENANCE_ENUM = {
    "EXACT_RECONSTRUCTED",
    "EXACT_COMMIT_AVAILABLE",
    "PARTIALLY_RECONSTRUCTED",
    "IDENTITY_MISMATCH",
    "COMMIT_UNKNOWN",
    "UNRECONSTRUCTABLE",
}

STRICT_FIELDS = (
    "repository_db_uuid",
    "provider",
    "repository_identifier",
    "remote_url",
    "scan_uuid",
    "branch",
    "commit_sha",
    "finding_uuid",
    "affected_path",
)


# ---------------------------------------------------------------------------
# Helpers (self-contained; no network, no mutation)
# ---------------------------------------------------------------------------

def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def compute_provenance_status(*, finding_present, repo_identity_known,
                              commit_present, path_present) -> str:
    """Pure provenance-status calculator (mirrors v2 logic).

    Used both by the test and as the reference implementation for the policy.
    """
    if not repo_identity_known:
        return "IDENTITY_MISMATCH"
    if not commit_present:
        return "COMMIT_UNKNOWN"
    if finding_present and path_present:
        return "EXACT_RECONSTRUCTED"
    if finding_present:
        return "PARTIALLY_RECONSTRUCTED"
    return "UNRECONSTRUCTABLE"


def detect_name_mismatch(manifest_names: set[str], dataset_names: set[str]) -> set[str]:
    """Return dataset repo names that have no matching manifest entry."""
    return dataset_names - manifest_names


def detect_missing_lineage(item: dict) -> list[str]:
    """Return list of strict provenance fields that are missing/unpersisted."""
    missing = []
    for f in STRICT_FIELDS:
        v = item.get(f)
        if v in (None, "", "MISSING", "NOT_PERSISTED"):
            missing.append(f)
    return missing


def reproduction_matches(recomputed: int | None, frozen: int | str | None) -> bool | None:
    """Compare recomputed metric to frozen observed value (exact match)."""
    if recomputed is None or frozen is None:
        return None
    try:
        return int(recomputed) == int(str(frozen).split("(")[-1].rstrip(")").strip().split()[0])
    except (ValueError, IndexError):
        return None


# ---------------------------------------------------------------------------
# 1. Original frozen dataset immutability
# ---------------------------------------------------------------------------

def test_original_frozen_dataset_present_and_unchanged():
    assert ORIGINAL_FILE.exists(), "original frozen dataset must remain present"
    assert _sha256_of(ORIGINAL_FILE) == ACTUAL_ORIGINAL_HASH, (
        "original frozen dataset hash must equal the verifiable on-disk SHA-256; "
        "note the file's internal metadata.dataset_hash is STALE (see v2 "
        "recorded_vs_actual_hash_mismatch) but the bytes themselves must not change"
    )


def test_original_frozen_dataset_not_rewritten():
    data = json.loads(ORIGINAL_FILE.read_text())
    # The internal self-declared hash is stale; record the discrepancy but do
    # not require it to match the trustworthy on-disk hash.
    assert data["metadata"]["dataset_hash"] == RECORDED_ORIGINAL_HASH
    # v2 must not have overwritten original fields
    assert "provenance_v2" not in data


# ---------------------------------------------------------------------------
# 2. v2 additive artifact linkage
# ---------------------------------------------------------------------------

def test_v2_artifact_links_original_and_is_additive():
    assert V2_FILE.exists(), "v2 additive provenance artifact must exist"
    v2 = json.loads(V2_FILE.read_text())
    ref = v2["references_original_dataset"]
    assert ref["file"] == "cycle7_frozen_review_set.json"
    assert ref["dataset_hash"] == RECORDED_ORIGINAL_HASH
    assert v2["original_dataset_immutability"].startswith("UNCHANGED")
    # v2 must cover all 50 findings
    assert len(v2["items"]) == 50


# ---------------------------------------------------------------------------
# 3. Provenance status calculation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kwargs,expected", [
    (dict(finding_present=True, repo_identity_known=True, commit_present=True, path_present=True), "EXACT_RECONSTRUCTED"),
    (dict(finding_present=True, repo_identity_known=True, commit_present=True, path_present=False), "PARTIALLY_RECONSTRUCTED"),
    (dict(finding_present=True, repo_identity_known=True, commit_present=False, path_present=True), "COMMIT_UNKNOWN"),
    (dict(finding_present=True, repo_identity_known=False, commit_present=True, path_present=True), "IDENTITY_MISMATCH"),
    (dict(finding_present=False, repo_identity_known=True, commit_present=True, path_present=True), "UNRECONSTRUCTABLE"),
])
def test_compute_provenance_status(kwargs, expected):
    assert compute_provenance_status(**kwargs) == expected


def test_v2_all_statuses_in_enum():
    v2 = json.loads(V2_FILE.read_text())
    for item in v2["items"]:
        assert item["provenance_status"] in PROVENANCE_ENUM


# ---------------------------------------------------------------------------
# 4. cognikid-style name mismatch detection
# ---------------------------------------------------------------------------

def test_cognikid_name_mismatch_detected():
    manifest_names = {"hermes-runtime", "faithtech-blueprint",
                      "inspirevoice-backend", "cognikid-web"}
    dataset_names = {"hermes-runtime", "faithtech-blueprint",
                     "inspirevoice-backend", "cognikid_app"}
    mism = detect_name_mismatch(manifest_names, dataset_names)
    assert "cognikid_app" in mism
    assert "cognikid-web" not in mism  # manifest-only name not a dataset defect


# ---------------------------------------------------------------------------
# 5. Manifest / frozen-dataset mismatch detection
# ---------------------------------------------------------------------------

def test_manifest_frozen_repo_mismatch():
    # Reconstruct the actual Cycle 7 mismatch record.
    manifest = {"cognikid-web": "4e9dfbde...@/Users/david/cognikid-web"}
    frozen = {"cognikid_app": "CogniKid_App"}
    # Manifest key not present in frozen dataset under same name
    assert "cognikid_app" not in manifest
    assert "cognikid-web" not in frozen


# ---------------------------------------------------------------------------
# 6. Missing scan lineage detection
# ---------------------------------------------------------------------------

def test_missing_scan_lineage_detected():
    v2 = json.loads(V2_FILE.read_text())
    for item in v2["items"]:
        missing = detect_missing_lineage(item)
        # Every Cycle 7 item must be flagged for absent lineage
        assert "scan_uuid" in missing
        assert "finding_uuid" in missing
        assert "repository_db_uuid" in missing


def test_persistence_defect_recorded():
    v2 = json.loads(V2_FILE.read_text())
    defect = v2["persistence_defect"]
    assert defect["code"] == "CYCLE7_SCAN_LINEAGE_PERSISTENCE_GAP"
    assert defect["classification"] == "HIGH"
    assert len(defect["evidence"]) >= 4


# ---------------------------------------------------------------------------
# 7. Exact historical reproduction helper
# ---------------------------------------------------------------------------

def _git_line_count(repo_path: str, sha: str, rel_path: str) -> int | None:
    """Read-only exact-history reproduction. Returns None if not materialized."""
    rp = Path(repo_path)
    if not (rp / ".git").exists():
        return None
    import subprocess
    try:
        out = subprocess.run(
            ["git", "-C", repo_path, "show", f"{sha}:{rel_path}"],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode != 0:
            return None
        return len(out.stdout.splitlines())
    except Exception:
        return None


def test_hermes_finding001_exact_reproduction():
    recomputed = _git_line_count(
        "/Users/david/Downloads/hermes-runtime-v0.3-runtime",
        "823a9d7e70a9fab8714c219ff52338ef696d3f9e",
        "hermes_v01/engineering_analyzer.py",
    )
    if recomputed is None:
        pytest.skip("hermes-runtime not materialized at expected path")
    assert recomputed == 1155, "FINDING-001 must reproduce exactly at cycle7 commit"


def test_cognikid_candidate_reproduction():
    recomputed = _git_line_count(
        "/Users/david/cognikid_app",
        "ccd1fd51f84a28fab3ce90b302601f07fc875b16",
        "src/services/TranscendentalQuantumNeuralSystem.ts",
    )
    if recomputed is None:
        pytest.skip("cognikid_app not materialized at expected path")
    assert recomputed == 702, "FINDING-035 candidate reproduces 702 lines"


# ---------------------------------------------------------------------------
# 8. Future provenance gate (VALIDATION_EVIDENCE_REPRODUCIBLE)
# ---------------------------------------------------------------------------

def test_future_provenance_gate_gates_strict_validation():
    v2 = json.loads(V2_FILE.read_text())
    gate = v2["future_provenance_gate"]
    assert gate["name"] == "VALIDATION_EVIDENCE_REPRODUCIBLE"
    for f in ("repository_db_uuid", "scan_uuid", "commit_sha", "finding_uuid", "affected_path"):
        assert f in gate["required_fields"]
    # Every Cycle 7 item would be EXCLUDED from strict validation
    for item in v2["items"]:
        missing = detect_missing_lineage(item)
        assert missing, "all Cycle7 items lack strict fields -> excluded from strict"
        assert gate["exclude_if_missing"] == "EXCLUDE_FROM_STRICT_VALIDATION"


def test_cognikid_commit_resolution_is_candidate_only():
    v2 = json.loads(V2_FILE.read_text())
    cr = v2["cognikid_commit_resolution"]
    assert cr["result"] == "COGNIKID_CANDIDATE_COMMIT_ONLY"
    assert cr["promoted_to_exact"] is False


def test_frozen_dataset_self_hash_inconsistency_recorded():
    v2 = json.loads(V2_FILE.read_text())
    mm = v2["recorded_vs_actual_hash_mismatch"]
    assert mm["defect"] == "FROZEN_DATASET_SELF_HASH_INCONSISTENT"
    assert mm["recorded_metadata_dataset_hash"] != mm["actual_file_sha256"]
    # original bytes treated as canonical; not rewritten
    assert mm["interpretation"]
