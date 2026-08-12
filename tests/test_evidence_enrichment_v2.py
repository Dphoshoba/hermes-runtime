"""Focused tests for Evidence Enrichment v2 (discriminative signal discovery).

These are ADDITIVE tests for the v2 milestone. They verify:
- deterministic v2 extraction
- human-label firewall (extraction is label-free)
- git-history extraction (read-only) at exact commit
- churn normalization (repo-relative, deterministic)
- co-change calculation (bounded, documented)
- structural centrality (intra-cohort import graph; NOT_AVAILABLE when absent)
- unsupported-language semantics (NOT_AVAILABLE, not zero)
- static test relationships (STATIC_TEST_RELATIONSHIP, runtime NOT_AVAILABLE)
- finding corroboration (counts independent signals, not dup rows)
- repository percentiles
- missing-data behavior (NOT_AVAILABLE)
- provenance inside v2
- exact-commit operation (no checkout)
- no repository mutation (input immutable; read-only git)
- Governance unchanged (decisions identical with/without v2)
- SCAN_STAGES unchanged
- backward compatibility with v1 (v1 still attaches; v2 optional)

Run: pytest tests/test_evidence_enrichment_v2.py -q
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from hermes_v01.evidence_enrichment_v2 import (
    ENRICHMENT_V2_VERSION,
    build_repo_context,
    extract_v2,
    percentile_rank,
)

REPO = Path(__file__).resolve().parent.parent
HERMES_RI = REPO / "repo-intelligence/REPOSITORY_INTELLIGENCE.json"


def _base_finding() -> dict:
    return {
        "finding_id": "FINDING-001",
        "category": "Maintainability",
        "severity": "high",
        "confidence": 0.5,
        "title": "Large module: hermes_v01/x.py (1155 lines)",
        "explanation": "Module has 1155 lines.",
        "evidence_references": [{"source": "modules", "reference_path": "hermes_v01/x.py",
                                  "detail": "Module has 1155 lines"}],
        "affected_components": [{"component_type": "module",
                                  "component_path": "hermes_v01/x.py",
                                  "component_name": "x.py"}],
    }


# ---------------------------------------------------------------------------
# 1. Deterministic extraction
# ---------------------------------------------------------------------------

def test_v2_deterministic():
    ctx = {"file_commits": {}, "cochanges": {}, "test_refs": {},
           "repo_file_graph": None}
    a = extract_v2(_base_finding(), repository_path=str(REPO),
                   commit_sha="823a9d7e70a9fab8714c219ff52338ef696d3f9e",
                   affected_path="hermes_v01/x.py", repo_history=ctx)
    b = extract_v2(_base_finding(), repository_path=str(REPO),
                   commit_sha="823a9d7e70a9fab8714c219ff52338ef696d3f9e",
                   affected_path="hermes_v01/x.py", repo_history=ctx)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_v2_input_immutable():
    f = _base_finding()
    ctx = {"file_commits": {}, "cochanges": {}, "test_refs": {},
           "repo_file_graph": None}
    extract_v2(f, repo_history=ctx)
    assert "enrichment_v2" not in f


# ---------------------------------------------------------------------------
# 2. Human-label firewall
# ---------------------------------------------------------------------------

def test_label_firewall():
    """Same finding + same context + DIFFERENT label -> identical v2 output."""
    ctx = {"file_commits": {}, "cochanges": {}, "test_refs": {},
           "repo_file_graph": None}
    a = extract_v2({**_base_finding(), "human_classification": "USEFUL"},
                   repo_history=ctx)
    b = extract_v2({**_base_finding(), "human_classification": "NOT_ACTIONABLE"},
                   repo_history=ctx)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# ---------------------------------------------------------------------------
# 3. Git-history extraction (read-only, exact commit)
# ---------------------------------------------------------------------------

def test_churn_git_history():
    ctx = build_repo_context(str(REPO), "823a9d7e70a9fab8714c219ff52338ef696d3f9e",
                             file_list=["hermes_v01/engineering_analyzer.py"])
    e = extract_v2(_base_finding(), repository_path=str(REPO),
                   commit_sha="823a9d7e70a9fab8714c219ff52338ef696d3f9e",
                   affected_path="hermes_v01/engineering_analyzer.py",
                   repo_history=ctx)
    assert e["churn"]["available"] is True
    assert e["churn"]["commits_touching_file"] >= 1
    assert e["cochange"]["available"] is True


def test_churn_normalization_deterministic():
    ctx = build_repo_context(str(REPO), "823a9d7e70a9fab8714c219ff52338ef696d3f9e",
                             file_list=["hermes_v01/engineering_analyzer.py"])
    e1 = extract_v2(_base_finding(), repository_path=str(REPO),
                    commit_sha="823a9d7e70a9fab8714c219ff52338ef696d3f9e",
                    affected_path="hermes_v01/engineering_analyzer.py", repo_history=ctx)
    e2 = extract_v2(_base_finding(), repository_path=str(REPO),
                    commit_sha="823a9d7e70a9fab8714c219ff52338ef696d3f9e",
                    affected_path="hermes_v01/engineering_analyzer.py", repo_history=ctx)
    assert e1["churn"]["change_frequency_rel_repo"] == \
           e2["churn"]["change_frequency_rel_repo"]


def test_cochange_bounded():
    ctx = build_repo_context(str(REPO), "823a9d7e70a9fab8714c219ff52338ef696d3f9e",
                             file_list=["hermes_v01/engineering_analyzer.py",
                                        "hermes_v01/engineering_intel_models.py"])
    e = extract_v2(_base_finding(), repository_path=str(REPO),
                   commit_sha="823a9d7e70a9fab8714c219ff52338ef696d3f9e",
                   affected_path="hermes_v01/engineering_analyzer.py", repo_history=ctx)
    c = e["cochange"]
    # strongest ratio is bounded in [0,1]; classification in documented set
    assert 0.0 <= (c["strongest_cochange_ratio"] or 0.0) <= 1.0
    assert c["change_coupling_classification"] in (
        "ISOLATED", "LOW_COUPLING", "MODERATE_COUPLING", "HIGH_COUPLING",
        "NOT_AVAILABLE")


# ---------------------------------------------------------------------------
# 4. Structural centrality
# ---------------------------------------------------------------------------

def test_structural_centrality_graph():
    graph = {"nodes": ["a.py", "b.py"], "edges": [("a.py", "b.py"),
                                                    ("b.py", "a.py")]}
    e = extract_v2(_base_finding(), affected_path="a.py", repo_file_graph=graph)
    assert e["structural_centrality"]["available"] is True
    assert e["structural_centrality"]["inbound_dependency_count"] == 1
    assert e["structural_centrality"]["language_supported"] is True


def test_structural_centrality_unsupported_lang():
    e = extract_v2(_base_finding(), affected_path="x.rb", repo_file_graph=None)
    # ruby unsupported -> NOT_AVAILABLE, not zero
    assert e["structural_centrality"]["available"] is False
    assert e["structural_centrality"]["language_supported"] is False
    assert e["structural_centrality"]["inbound_dependency_count"] is None


# ---------------------------------------------------------------------------
# 5. Test relationships (static only)
# ---------------------------------------------------------------------------

def test_test_relationship_static_only():
    ctx = {"file_commits": {}, "cochanges": {}, "test_refs": {
        "hermes_v01/x.py": ["tests/test_x.py"]}}
    e = extract_v2(_base_finding(), affected_path="hermes_v01/x.py", repo_history=ctx)
    tr = e["test_relationship"]
    assert tr["relationship_type"] in ("STATIC_TEST_RELATIONSHIP",
                                       "NO_STATIC_TEST_REFERENCE")
    # runtime coverage must NEVER be claimed
    assert tr["runtime_coverage"] == "NOT_AVAILABLE"


# ---------------------------------------------------------------------------
# 6. Finding corroboration
# ---------------------------------------------------------------------------

def test_corroboration_counts_independent_signals():
    e = extract_v2(_base_finding(), all_finding_components=["hermes_v01/x.py"])
    cor = e["corroboration"]
    assert cor["findings_on_same_component"] == 1
    assert cor["corroboration_strength"] in ("WEAK", "MODERATE", "HIGH")
    assert cor["available"] is True


# ---------------------------------------------------------------------------
# 7. Repository percentiles
# ---------------------------------------------------------------------------

def test_percentile_rank():
    vals = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert percentile_rank(vals, 3.0) == 0.4
    # unknown when empty
    import math
    assert math.isnan(percentile_rank([], 1.0))


# ---------------------------------------------------------------------------
# 8. Missing-data behavior
# ---------------------------------------------------------------------------

def test_missing_data_not_available():
    e = extract_v2(_base_finding())  # no context, no path
    assert e["churn"]["available"] is False
    assert e["churn"]["source"] == "no_history"
    assert e["structural_centrality"]["available"] is False


def test_provenance_inside_v2():
    e = extract_v2(_base_finding(), repository_path="R",
                   commit_sha="abc", affected_path="hermes_v01/x.py")
    assert e["version"] == ENRICHMENT_V2_VERSION
    assert e["commit_sha"] == "abc"
    assert e["affected_path"] == "hermes_v01/x.py"


# ---------------------------------------------------------------------------
# 9. No repository mutation (read-only git)
# ---------------------------------------------------------------------------

def test_no_repo_mutation():
    before = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    ctx = build_repo_context(str(REPO), "823a9d7e70a9fab8714c219ff52338ef696d3f9e",
                             file_list=["hermes_v01/engineering_analyzer.py"])
    extract_v2(_base_finding(), repository_path=str(REPO),
               commit_sha="823a9d7e70a9fab8714c219ff52338ef696d3f9e",
               affected_path="hermes_v01/engineering_analyzer.py",
               repo_history=ctx)
    after = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                           capture_output=True, text=True).stdout.strip()
    assert before == after


# ---------------------------------------------------------------------------
# 10. Governance unchanged (with vs without v2)
# ---------------------------------------------------------------------------

def test_governance_unchanged_with_v2():
    if not HERMES_RI.exists():
        pytest.skip("RI artifact not present")
    from hermes_v01.engineering_analyzer import analyze_engineering
    from hermes_v01.governance_analyzer import govern_engineering, _decide
    import inspect

    ri = json.loads(HERMES_RI.read_text())
    ei_no_v2 = analyze_engineering(ri)
    gov_no_v2 = govern_engineering(ei_no_v2.as_dict())

    v2_ctx = {"repository_path": str(REPO), "commit_sha": "HEAD",
              "repo_history": {"file_commits": {}, "cochanges": {}, "test_refs": {}},
              "repo_file_graph": None, "all_finding_components": []}
    ei_v2 = analyze_engineering(ri, v2_context=v2_ctx)
    gov_v2 = govern_engineering(ei_v2.as_dict())

    # v2 attaches enrichment_v2
    assert any(f.enrichment_v2 for f in ei_v2.findings)
    # decisions identical value-for-value
    d1 = [d.decision for d in gov_no_v2.assessment.approval_decisions]
    d2 = [d.decision for d in gov_v2.assessment.approval_decisions]
    assert d1 == d2
    # _decide still does not reference enrichment
    assert "enrichment" not in inspect.getsource(_decide)


def test_scan_stages_unchanged():
    import hermes_v01.engineering_analyzer as ea
    for attr in ("SCAN_STAGES", "PIPELINE_STAGES", "STAGES"):
        if hasattr(ea, attr):
            s = " ".join(str(x) for x in getattr(ea, attr)).lower()
            assert "enrich" not in s


def test_v1_backward_compat():
    """v1 still attaches enrichment; v2 is optional and separate."""
    from hermes_v01.engineering_analyzer import analyze_engineering
    ri = json.loads(HERMES_RI.read_text())
    ei = analyze_engineering(ri)
    assert any(f.enrichment for f in ei.findings)
    # without v2_context no enrichment_v2
    assert not any(f.enrichment_v2 for f in ei.findings)
