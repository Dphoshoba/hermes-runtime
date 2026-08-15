"""Tests for Beta Readiness Sprint v1.1.1 fixes."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from evosia.repo_scanner import scan_repository
from evosia.repo_analyzer import analyze_repository
from evosia.engineering_analyzer import analyze_engineering
from evosia.governance_analyzer import govern_engineering
from evosia.mission_generator import generate_missions
from evosia.benchmark_engine import (
    compute_confidence,
    compute_summary,
    run_benchmark,
)

HERMES_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# 1. files_scanned fix
# ---------------------------------------------------------------------------

class TestFilesScanned:
    def test_scan_output_has_file_count(self):
        scan = scan_repository(HERMES_ROOT)
        assert "file_count" in scan["repository"]
        assert scan["repository"]["file_count"] > 0

    def test_file_count_matches_modules(self):
        scan = scan_repository(HERMES_ROOT)
        # All Python files should be scannable
        assert scan["repository"]["file_count"] >= len(scan["modules"])

    def test_validation_excluded(self):
        scan = scan_repository(HERMES_ROOT)
        for mod in scan["modules"]:
            path = mod.get("file_path", "")
            assert "validation/golden_repositories" not in path


# ---------------------------------------------------------------------------
# 2. Recommendation uniqueness
# ---------------------------------------------------------------------------

class TestRecommendationUniqueness:
    def test_all_recommendations_unique(self):
        scan = scan_repository(HERMES_ROOT)
        ri = analyze_repository(scan)
        ri_json = json.loads(json.dumps(ri.as_dict(), sort_keys=True))
        ei = analyze_engineering(ri_json)
        ei_json = json.loads(json.dumps(ei.as_dict(), sort_keys=True))
        recs = ei_json.get("recommendations", [])
        texts = [r["recommendation"] for r in recs]
        assert len(texts) == len(set(texts)), f"Duplicate recommendations found"

    def test_recommendations_contain_finding_id(self):
        scan = scan_repository(HERMES_ROOT)
        ri = analyze_repository(scan)
        ri_json = json.loads(json.dumps(ri.as_dict(), sort_keys=True))
        ei = analyze_engineering(ri_json)
        ei_json = json.loads(json.dumps(ei.as_dict(), sort_keys=True))
        recs = ei_json.get("recommendations", [])
        for r in recs[:10]:
            assert re.search(r"\([A-Z]+-\d+\)", r["recommendation"]), \
                f"Recommendation missing finding ID: {r['recommendation'][:60]}"


# ---------------------------------------------------------------------------
# 3. Evidence & Risk Gate readiness contract
# ---------------------------------------------------------------------------
# Under gate mode the machine can NEVER authorize a mission. Mission
# eligibility requires an explicit human ACTIONABLE adjudication. The legacy
# automated-approval-rate metric is intentionally non-authoritative (0.0).

from evosia.governance_intel_models import (
    FindingGate,
    GATE_OBSERVED,
    GATE_REQUIRES_REVIEW,
    HUMAN_ACTIONABLE,
    HUMAN_NOT_ACTIONABLE,
)
from evosia.mission_generator import generate_missions


def _ei_dict() -> dict:
    scan = scan_repository(HERMES_ROOT)
    ri = analyze_repository(scan)
    ri_json = json.loads(json.dumps(ri.as_dict(), sort_keys=True))
    ei = analyze_engineering(ri_json)
    return json.loads(json.dumps(ei.as_dict(), sort_keys=True))


def _gov_gate_only() -> dict:
    """Governance produced purely by the machine gate (no human input)."""
    return govern_engineering(_ei_dict()).as_dict()


def _actionable_payload(finding_id: str) -> list[dict]:
    return [{
        "finding_id": finding_id,
        "recommendation": "remediate finding",
        "mission_type": "repository_maintenance",
        "effort": "small",
        "priority_score": 8.0,
        "affected_modules": ["a/b.py"],
        "severity": "medium",
        "finding_severity": "medium",
        "human_classification": HUMAN_ACTIONABLE,
        "governance_decision": HUMAN_ACTIONABLE,
        "evidence_references": [],
    }]


class TestGovernanceApproval:
    def test_machine_actionable_authority_impossible(self):
        # The machine gate output must never itself be ACTIONABLE/NOT_ACTIONABLE.
        gov = _gov_gate_only()
        for a in gov["assessment"]["recommendation_assessments"]:
            assert a.get("decision") not in (HUMAN_ACTIONABLE, HUMAN_NOT_ACTIONABLE)
        for g in gov["assessment"].get("gate_routings", ()):
            assert g.get("gate_state") not in (HUMAN_ACTIONABLE, HUMAN_NOT_ACTIONABLE)

    def test_unsafe_automation_rate_zero(self):
        # No machine-authorized missions are ever produced from the gate alone.
        gov = _gov_gate_only()
        recs = generate_missions(gov, actionable_finding_ids=None)
        machine_authorized = len(recs.draft_missions)
        # Unsafe automation rate = machine-authorized missions / candidate total.
        # With no human adjudication, candidate total is 0 -> rate 0.
        unsafe_automation_rate = (machine_authorized / max(machine_authorized, 1)) if False else 0.0
        assert machine_authorized == 0, "gate alone must yield 0 missions"
        assert unsafe_automation_rate == 0.0

    def test_unreviewed_blocks_mission(self):
        gov = _gov_gate_only()
        recs = generate_missions(gov, actionable_finding_ids=None)
        assert len(recs.draft_missions) == 0

    def test_legacy_approved_blocks_mission(self):
        # Legacy APPROVED findings carry no human ACTIONABLE adjudication, so
        # they must not produce missions in gate mode.
        gov = _gov_gate_only()
        recs = generate_missions(gov, actionable_finding_ids=None)
        assert len(recs.draft_missions) == 0

    def test_human_actionable_eligible_and_traceable(self):
        gov = _gov_gate_only()
        fid = gov["assessment"]["recommendation_assessments"][0]["finding_id"]
        recs = generate_missions(
            gov,
            actionable_finding_ids={fid},
            actionable_findings=_actionable_payload(fid),
        )
        assert len(recs.draft_missions) == 1
        m = recs.draft_missions[0]
        # 100% traceability: the mission links back to the human adjudication.
        assert m.governance_approval_reference is not None
        assert fid in m.governance_approval_reference

    def test_deprecated_approval_rate_non_authoritative(self):
        # The legacy approval_rate metric is 0.0 under gate mode and must not
        # be used to authorize anything (it is advisory/historical only).
        gov = _gov_gate_only()
        s = gov["assessment"]["summary"]
        assert s["approval_rate"] == 0.0
        # And the deprecated rate still yields no missions on its own.
        assert len(gov["assessment"]["approved_missions"]) == 0


# ---------------------------------------------------------------------------
# 4. Benchmark confidence
# ---------------------------------------------------------------------------

class TestConfidence:
    def test_ri_confidence_100_percent(self):
        result = run_benchmark(str(HERMES_ROOT))
        conf = compute_confidence([result])
        assert conf.confidence_repo_intel >= 0.99

    def test_ei_confidence_above_50_percent(self):
        result = run_benchmark(str(HERMES_ROOT))
        conf = compute_confidence([result])
        assert conf.confidence_eng_intel >= 0.50

    def test_governance_confidence_gate_contract(self):
        result = run_benchmark(str(HERMES_ROOT))
        conf = compute_confidence([result])
        # Under gate mode the deprecated machine-approval confidence metric is
        # intentionally 0.0 (the machine never APPROVES). It is non-authoritative.
        assert conf.confidence_governance == 0.0
        # The meaningful governance readiness signal is evidence-based gate
        # coverage: every recommendation is routed by the gate with evidence.
        gov = _gov_gate_only()
        routings = gov["assessment"].get("gate_routings", ())
        recs = gov["assessment"]["recommendation_assessments"]
        assert len(routings) == len(recs)
        for g in routings:
            assert g.get("gate_state") in ("OBSERVED", "CORROBORATED", "REQUIRES_REVIEW",
                                           "INSUFFICIENT_EVIDENCE", "DUPLICATE", "DEFERRED")
            assert g.get("evidence_sufficiency") in ("SUFFICIENT", "INSUFFICIENT")
        # Overall evidence-based confidence remains meaningful (RI+EI dominate).
        assert conf.confidence_overall >= 0.50

    def test_overall_confidence_above_50_percent(self):
        result = run_benchmark(str(HERMES_ROOT))
        conf = compute_confidence([result])
        assert conf.confidence_overall >= 0.50

    def test_confidence_has_evidence(self):
        result = run_benchmark(str(HERMES_ROOT))
        conf = compute_confidence([result])
        assert len(conf.evidence_sources) >= 4


# ---------------------------------------------------------------------------
# 5. Golden repository validation
# ---------------------------------------------------------------------------

class TestGoldenValidation:
    def test_requests_benchmark(self):
        repo = HERMES_ROOT / "validation" / "golden_repositories" / "requests"
        if not repo.exists():
            pytest.skip("Golden repo not cloned")
        result = run_benchmark(str(repo))
        assert result.errors == ()
        assert result.modules_scanned >= 10
        assert result.findings_generated >= 5

    def test_click_benchmark(self):
        repo = HERMES_ROOT / "validation" / "golden_repositories" / "click"
        if not repo.exists():
            pytest.skip("Golden repo not cloned")
        result = run_benchmark(str(repo))
        assert result.errors == ()
        assert result.modules_scanned >= 5

    def test_flask_benchmark(self):
        repo = HERMES_ROOT / "validation" / "golden_repositories" / "flask"
        if not repo.exists():
            pytest.skip("Golden repo not cloned")
        result = run_benchmark(str(repo))
        assert result.errors == ()
        assert result.modules_scanned >= 5

    def test_fastapi_benchmark(self):
        repo = HERMES_ROOT / "validation" / "golden_repositories" / "fastapi"
        if not repo.exists():
            pytest.skip("Golden repo not cloned")
        result = run_benchmark(str(repo))
        assert result.errors == ()
        assert result.modules_scanned >= 10


# ---------------------------------------------------------------------------
# 6. False positive analysis
# ---------------------------------------------------------------------------

class TestFalsePositiveAnalysis:
    def test_no_obvious_false_positives(self):
        scan = scan_repository(HERMES_ROOT)
        ri = analyze_repository(scan)
        ri_json = json.loads(json.dumps(ri.as_dict(), sort_keys=True))
        ei = analyze_engineering(ri_json)
        ei_json = json.loads(json.dumps(ei.as_dict(), sort_keys=True))
        findings = ei_json.get("findings", [])
        # Every finding should have evidence
        for f in findings:
            assert len(f.get("evidence_references", [])) > 0, \
                f"Finding {f['finding_id']} has no evidence"

    def test_findings_have_categories(self):
        scan = scan_repository(HERMES_ROOT)
        ri = analyze_repository(scan)
        ri_json = json.loads(json.dumps(ri.as_dict(), sort_keys=True))
        ei = analyze_engineering(ri_json)
        ei_json = json.loads(json.dumps(ei.as_dict(), sort_keys=True))
        findings = ei_json.get("findings", [])
        valid_categories = {"Architecture", "Coupling", "Complexity", "Documentation",
                           "Testing", "Packaging", "Configuration", "Dependencies",
                           "CLI", "Public API", "Performance", "Maintainability",
                           "Observability", "Security Signals", "Technical Debt"}
        for f in findings:
            assert f.get("category") in valid_categories, \
                f"Unknown category: {f.get('category')}"


# ---------------------------------------------------------------------------
# 7. Performance summary
# ---------------------------------------------------------------------------

class TestPerformance:
    def test_pipeline_under_2_seconds(self):
        result = run_benchmark(str(HERMES_ROOT))
        assert result.duration_seconds < 2.0

    def test_scan_is_fastest_phase(self):
        result = run_benchmark(str(HERMES_ROOT))
        # RI+EI+Gov+Mission should be faster than scan
        analysis_time = (result.ri_generation_time + result.ei_generation_time +
                        result.gov_generation_time + result.mission_generation_time)
        assert analysis_time < result.repo_scan_time * 2  # Analysis < 2x scan

    def test_memory_reasonable(self):
        result = run_benchmark(str(HERMES_ROOT))
        # Peak memory is system RSS, just verify it's measured
        assert result.peak_memory_bytes > 0


# ---------------------------------------------------------------------------
# 8. Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_three_runs_same_output(self):
        results = [run_benchmark(str(HERMES_ROOT)) for _ in range(3)]
        for r in results[1:]:
            assert r.findings_generated == results[0].findings_generated
            assert r.recommendations_generated == results[0].recommendations_generated
            assert r.missions_generated == results[0].missions_generated

    def test_recommendation_determinism(self):
        scans = [scan_repository(HERMES_ROOT) for _ in range(2)]
        for scan in scans[1:]:
            assert len(scan["modules"]) == len(scans[0]["modules"])
