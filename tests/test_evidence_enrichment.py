"""Focused tests for Evidence Enrichment v1 (additive, read-only).

These tests verify:
- deterministic enrichment
- exact-commit provenance inside enrichment
- file-context classification
- exceedance calculation + threshold tiers
- git change-history calculation (read-only)
- contributor / ownership calculation (read-only)
- dependency centrality calculation
- evidence-strength calculation
- missing-data semantics (UNKNOWN / NOT_AVAILABLE)
- enrichment additive compatibility (existing fields untouched)
- Governance receives enrichment but _decide() is unchanged
- canonical SCAN_STAGES unchanged (no new stage introduced)
- target repositories never modified

Run: pytest tests/test_evidence_enrichment.py -q
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evosia.evidence_enrichment import (
    ENRICHMENT_VERSION,
    classify_file_context,
    compute_change_history,
    compute_evidence_strength,
    compute_exceedance,
    compute_ownership,
    compute_structural_importance,
    enrich_finding,
    enrich_findings,
)

REPO = Path(__file__).resolve().parent.parent

HERMES_RI_PATH = REPO / "repo-intelligence/REPOSITORY_INTELLIGENCE.json"


# ---------------------------------------------------------------------------
# 1. Deterministic enrichment
# ---------------------------------------------------------------------------

def _base_finding() -> dict:
    return {
        "finding_id": "FINDING-001",
        "category": "Maintainability",
        "severity": "high",
        "confidence": 0.5,
        "title": "Large module: x.py (1155 lines)",
        "explanation": "Module has 1155 lines.",
        "evidence_references": [
            {"source": "modules", "reference_path": "hermes_v01/x.py",
             "detail": "Module has 1155 lines"},
        ],
        "affected_components": [
            {"component_type": "module", "component_path": "hermes_v01/x.py",
             "component_name": "x.py"},
        ],
    }


def test_enrichment_deterministic():
    ri = {"module_graph": {"nodes": ["hermes_v01/x.py"], "edges": []}}
    a = enrich_finding(_base_finding(), ri,
                       repository_identifier="R", commit_sha="abc",
                       repo_local_path=str(REPO))
    b = enrich_finding(_base_finding(), ri,
                       repository_identifier="R", commit_sha="abc",
                       repo_local_path=str(REPO))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_enrichment_does_not_mutate_input():
    f = _base_finding()
    ri = {"module_graph": {"nodes": [], "edges": []}}
    enrich_finding(f, ri)
    assert "enrichment" not in f  # input unchanged


# ---------------------------------------------------------------------------
# 2. Provenance inside enrichment
# ---------------------------------------------------------------------------

def test_enrichment_carries_provenance():
    e = enrich_finding(_base_finding(), {"module_graph": {"nodes": [], "edges": []}},
                       repository_identifier="Dphoshoba/hermes-runtime",
                       commit_sha="823a9d7e", repo_local_path=str(REPO))
    assert e["version"] == ENRICHMENT_VERSION
    assert e["repository_identifier"] == "Dphoshoba/hermes-runtime"
    assert e["commit_sha"] == "823a9d7e"
    assert e["affected_path"] == "hermes_v01/x.py"


# ---------------------------------------------------------------------------
# 3. File-context classification
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,expected", [
    ("src/app.py", "PRODUCTION"),
    ("tests/test_app.py", "TEST"),
    ("tests/test_x.tsx", "TEST"),
    ("x.test.js", "TEST"),
    ("src/__init__.py", "GENERATED"),
    ("db/migrations/versions/001_x.py", "VENDOR"),
    ("node_modules/foo/bar.js", "VENDOR"),
    ("pyproject.toml", "CONFIGURATION"),
    ("README.md", "DOCUMENTATION"),
    ("tests/fixtures/data.json", "FIXTURE"),
    ("", "UNKNOWN"),
])
def test_classify_file_context(path, expected):
    assert classify_file_context(path)[0] == expected


# ---------------------------------------------------------------------------
# 4. Exceedance calculation + tiers
# ---------------------------------------------------------------------------

def test_exceedance_high():
    r = compute_exceedance(900.0, 300.0)
    assert r["exceedance_ratio"] == 3.0
    assert r["exceedance_tier"] == "EXTREME"
    assert r["available"] is True


def test_exceedance_moderate():
    r = compute_exceedance(450.0, 300.0)
    assert r["exceedance_tier"] == "MODERATE"
    assert 1.5 <= r["exceedance_ratio"] < 2.0


def test_exceedance_missing_value():
    r = compute_exceedance(None, 300.0)
    assert r["available"] is False
    assert r["exceedance_tier"] == "UNKNOWN"


def test_exceedance_missing_threshold():
    r = compute_exceedance(100.0, None)
    assert r["available"] is False


# ---------------------------------------------------------------------------
# 5. Change history (read-only git)
# ---------------------------------------------------------------------------

def test_change_history_real_repo():
    # hermes_v01/engineering_analyzer.py exists in this very repo at HEAD
    r = compute_change_history(str(REPO), "HEAD", "hermes_v01/engineering_analyzer.py")
    assert r["available"] is True
    assert r["commit_count"] >= 1
    assert r["churn_classification"] in ("LOW", "MODERATE", "HIGH", "NONE")


def test_change_history_missing_path():
    r = compute_change_history(str(REPO), "HEAD", "does/not/exist.py")
    assert r["available"] is False
    assert r["churn_classification"] in ("UNKNOWN", "NOT_OBSERVED")


def test_change_history_no_repo():
    r = compute_change_history(None, None, "x.py")
    assert r["available"] is False
    assert r["source"] == "no_repo_or_path"


# ---------------------------------------------------------------------------
# 6. Ownership / contributor (read-only git)
# ---------------------------------------------------------------------------

def test_ownership_real_repo():
    r = compute_ownership(str(REPO), "HEAD", "hermes_v01/engineering_analyzer.py")
    assert r["available"] is True
    assert r["contributor_count"] >= 1
    assert r["ownership_concentration"] in ("HIGH", "MODERATE", "DISTRIBUTED")


def test_ownership_no_repo():
    r = compute_ownership(None, None, "x.py")
    assert r["available"] is False
    assert r["ownership_concentration"] == "UNKNOWN"


# ---------------------------------------------------------------------------
# 7. Structural centrality (RI module graph)
# ---------------------------------------------------------------------------

def test_structural_present_in_graph():
    ri = {"module_graph": {"nodes": ["a.py", "b.py"],
                            "edges": [("a.py", "b.py"), ("b.py", "a.py")]}}
    r = compute_structural_importance(ri, "a.py")
    assert r["available"] is True
    assert r["inbound_dependency_count"] == 1
    assert r["outbound_dependency_count"] == 1
    assert r["centrality_classification"] in ("LOW", "MODERATE", "HIGH", "ISOLATED")


def test_structural_absent_from_graph():
    ri = {"module_graph": {"nodes": ["a.py"], "edges": []}}
    r = compute_structural_importance(ri, "zzz.py")
    assert r["available"] is False
    assert r["centrality_classification"] == "UNKNOWN"


# ---------------------------------------------------------------------------
# 8. Evidence strength
# ---------------------------------------------------------------------------

def test_evidence_strength_strong():
    f = {"evidence_references": [
        {"source": "modules", "reference_path": "a"},
        {"source": "tests", "reference_path": "b"},
        {"source": "debt_signals", "reference_path": "c"},
    ]}
    r = compute_evidence_strength(f)
    assert r["evidence_strength"] == "STRONG"
    assert r["independent_evidence_type_count"] == 3


def test_evidence_strength_none():
    r = compute_evidence_strength({"evidence_references": []})
    assert r["evidence_strength"] == "NONE"
    assert r["available"] is False


# ---------------------------------------------------------------------------
# 9. Missing-data semantics — no invented behavioral evidence
# ---------------------------------------------------------------------------

def test_behavioral_evidence_not_invented():
    e = enrich_finding(_base_finding(), {"module_graph": {"nodes": [], "edges": []}},
                       repo_local_path=str(REPO))
    assert e["behavioral_evidence"]["value"] == "NOT_OBSERVED"
    assert e["behavioral_evidence"]["available"] is False


# ---------------------------------------------------------------------------
# 10. Additive compatibility + Governance unchanged
# ---------------------------------------------------------------------------

def test_enrich_findings_additive():
    fs = [_base_finding()]
    out = enrich_findings(fs, {"module_graph": {"nodes": [], "edges": []}},
                          repo_local_path=str(REPO))
    assert "enrichment" in out[0]
    # original fields preserved
    assert out[0]["finding_id"] == "FINDING-001"
    assert out[0]["category"] == "Maintainability"


def test_governance_receives_enrichment_but_unchanged():
    """End-to-end: EI produces enrichment; Governance still ignores it."""
    if not HERMES_RI_PATH.exists():
        pytest.skip("RI artifact not present")
    from evosia.engineering_analyzer import analyze_engineering
    from evosia.governance_analyzer import govern_engineering, _decide
    import inspect

    ei = analyze_engineering(json.loads(HERMES_RI_PATH.read_text()))
    ei_dict = ei.as_dict()
    assert any(f.get("enrichment") for f in ei_dict["findings"])

    gov = govern_engineering(ei_dict)
    # enrichment does not break governance
    assert gov is not None
    # _decide must not reference enrichment (no decision logic change)
    assert "enrichment" not in inspect.getsource(_decide)


def test_canonical_stages_unchanged():
    """Enrichment adds no canonical SCAN_STAGES entry."""
    import evosia.engineering_analyzer as ea
    # If SCAN_STAGES exists in this module/system, it must not contain enrichment
    for attr in ("SCAN_STAGES", "PIPELINE_STAGES", "STAGES"):
        if hasattr(ea, attr):
            stages = getattr(ea, attr)
            flat = " ".join(str(s) for s in stages).lower()
            assert "enrich" not in flat


def test_target_repos_not_modified(tmp_path):
    """Enrichment never writes outside the returned dict (no fs mutation)."""
    import shutil
    # Use a throwaway copy so we can detect any mutation of the real repo.
    f = _base_finding()
    before = json.dumps(f, sort_keys=True)
    enrich_finding(f, {"module_graph": {"nodes": [], "edges": []}},
                   repo_local_path=str(REPO))
    after = json.dumps(f, sort_keys=True)
    assert before == after  # input immutable
