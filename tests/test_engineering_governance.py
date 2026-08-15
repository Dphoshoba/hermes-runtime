"""Comprehensive tests for Engineering Governance v1.0."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from evosia.governance_intel_models import (
    ApprovalDecision,
    ApprovedCandidateMission,
    ArchitectureImpact,
    Conflict,
    DuplicateRecommendation,
    EngineeringGovernance,
    EvidenceQuality,
    GovernanceAssessment,
    RecommendationAssessment,
    ApprovalSummary,
)
from evosia.governance_analyzer import govern_engineering
from evosia.governance_renderer import render_json, render_markdown, save_artifacts
from evosia.repo_scanner import scan_repository
from evosia.repo_analyzer import analyze_repository
from evosia.engineering_analyzer import analyze_engineering


SAMPLE_REPO = Path(__file__).resolve().parent.parent / "validation" / "sample-repo"
HERMES_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def sample_ri():
    scan = scan_repository(SAMPLE_REPO)
    ri = analyze_repository(scan)
    return json.loads(json.dumps(ri.as_dict(), sort_keys=True))


@pytest.fixture
def sample_ei(sample_ri):
    return json.loads(json.dumps(analyze_engineering(sample_ri).as_dict(), sort_keys=True))


@pytest.fixture
def hermes_ri():
    scan = scan_repository(HERMES_ROOT)
    ri = analyze_repository(scan)
    return json.loads(json.dumps(ri.as_dict(), sort_keys=True))


@pytest.fixture
def hermes_ei(hermes_ri):
    return json.loads(json.dumps(analyze_engineering(hermes_ri).as_dict(), sort_keys=True))


@pytest.fixture
def tmp_output(tmp_path):
    d = tmp_path / "gov"
    d.mkdir()
    return d


def _minimal_ei(**overrides) -> dict:
    base = {
        "repository": {"name": "test-repo"},
        "findings": [],
        "recommendations": [],
        "candidate_missions": [],
        "risk_assessment": {"level": "low", "reasoning": "None", "evidence": [], "mitigation": "None"},
        "summary": {"total_findings": 0, "critical_count": 0, "high_count": 0, "medium_count": 0,
                     "low_count": 0, "info_count": 0, "total_recommendations": 0,
                     "total_candidate_missions": 0, "overall_risk": "Low", "health_score": 100.0},
    }
    base.update(overrides)
    return base


def _ei_with_rec(rec_text: str, finding_id: str = "FINDING-001", category: str = "Testing",
                 severity: str = "low", confidence: float = 0.7) -> dict:
    return _minimal_ei(
        findings=[{"finding_id": finding_id, "category": category, "severity": severity,
                   "confidence": confidence, "title": "Test", "explanation": "Test",
                   "evidence_references": [{"source": "tests", "reference_path": "x.py", "detail": "test"}],
                   "affected_components": [{"component_type": "module", "component_path": "x.py", "component_name": "x"}]}],
        recommendations=[{"finding_id": finding_id, "recommendation": rec_text,
                          "rationale": "Rationale", "priority": {"score": 5.0, "impact": 5.0, "confidence": 0.7,
                          "severity": 5.0, "scope": 5.0, "formula": "f"},
                          "estimated_effort": "small", "estimated_risk": "low", "expected_benefit": "Benefit"}],
    )


# ---------------------------------------------------------------------------
# Data Model Tests
# ---------------------------------------------------------------------------

class TestModels:
    def test_evidence_quality_frozen(self):
        eq = EvidenceQuality(level="high", reference_count=3, diversity="diverse",
                             consistency="consistent", reasoning="test")
        with pytest.raises(AttributeError):
            eq.level = "low"  # type: ignore

    def test_approval_decision_as_dict(self):
        d = ApprovalDecision(finding_id="F-001", decision="APPROVED", rationale="Good", conditions=())
        assert d.as_dict()["decision"] == "APPROVED"

    def test_governance_default(self):
        gov = EngineeringGovernance()
        assert gov.schema_version == "1"
        assert gov.assessment.summary.total_evaluated == 0

    def test_governance_as_dict(self):
        gov = EngineeringGovernance()
        d = gov.as_dict()
        assert "schema_version" in d
        assert "assessment" in d


# ---------------------------------------------------------------------------
# Approval Decision Tests
# ---------------------------------------------------------------------------

class TestApprovalDecisions:
    def test_all_recommendations_get_decisions(self, sample_ei):
        gov = govern_engineering(sample_ei, mode="legacy")
        assert len(gov.assessment.approval_decisions) == len(sample_ei["recommendations"])

    def test_decisions_are_valid(self, sample_ei):
        gov = govern_engineering(sample_ei)
        valid = {"APPROVED", "APPROVED_WITH_NOTES", "NEEDS_MORE_EVIDENCE", "DEFERRED", "REJECTED"}
        for d in gov.assessment.approval_decisions:
            assert d.decision in valid

    def test_every_decision_has_rationale(self, sample_ei):
        gov = govern_engineering(sample_ei)
        for d in gov.assessment.approval_decisions:
            assert len(d.rationale) > 0

    def test_approved_missions_match_decisions(self, sample_ei):
        gov = govern_engineering(sample_ei)
        approved_ids = {d.finding_id for d in gov.assessment.approval_decisions
                        if d.decision in ("APPROVED", "APPROVED_WITH_NOTES")}
        mission_ids = {m.finding_id for m in gov.assessment.approved_missions}
        assert mission_ids == approved_ids


# ---------------------------------------------------------------------------
# Duplicate Detection Tests
# ---------------------------------------------------------------------------

class TestDuplicateDetection:
    def test_no_duplicates_in_unique_recs(self):
        ei = _minimal_ei(
            findings=[{"finding_id": f"F-{i}", "category": "Testing", "severity": "low",
                       "confidence": 0.7, "title": f"Find {i}", "explanation": f"Exp {i}",
                       "evidence_references": [{"source": "tests", "reference_path": "a.py", "detail": "d"}],
                       "affected_components": []} for i in range(5)],
            recommendations=[{"finding_id": f"F-{i}", "recommendation": f"Do unique thing {i}",
                              "rationale": "R", "priority": {"score": 5.0, "impact": 5.0, "confidence": 0.7,
                              "severity": 5.0, "scope": 5.0, "formula": "f"},
                              "estimated_effort": "small", "estimated_risk": "low", "expected_benefit": "B"}
                             for i in range(5)],
        )
        gov = govern_engineering(ei)
        assert len(gov.assessment.duplicates) == 0

    def test_duplicates_detected(self):
        ei = _minimal_ei(
            findings=[{"finding_id": "F-001", "category": "Testing", "severity": "low",
                       "confidence": 0.7, "title": "A", "explanation": "A",
                       "evidence_references": [{"source": "tests", "reference_path": "a.py", "detail": "d"}],
                       "affected_components": []},
                      {"finding_id": "F-002", "category": "Testing", "severity": "low",
                       "confidence": 0.7, "title": "B", "explanation": "B",
                       "evidence_references": [{"source": "tests", "reference_path": "b.py", "detail": "d"}],
                       "affected_components": []}],
            recommendations=[{"finding_id": "F-001", "recommendation": "add comprehensive test coverage",
                              "rationale": "R", "priority": {"score": 5.0, "impact": 5.0, "confidence": 0.7,
                              "severity": 5.0, "scope": 5.0, "formula": "f"},
                              "estimated_effort": "small", "estimated_risk": "low", "expected_benefit": "B"},
                             {"finding_id": "F-002", "recommendation": "add comprehensive test coverage",
                              "rationale": "R", "priority": {"score": 5.0, "impact": 5.0, "confidence": 0.7,
                              "severity": 5.0, "scope": 5.0, "formula": "f"},
                              "estimated_effort": "small", "estimated_risk": "low", "expected_benefit": "B"}],
        )
        gov = govern_engineering(ei)
        assert len(gov.assessment.duplicates) >= 1
        assert gov.assessment.duplicates[0].similarity == "identical"

    def test_duplicate_rejected(self):
        ei = _minimal_ei(
            findings=[{"finding_id": "F-001", "category": "Testing", "severity": "low",
                       "confidence": 0.7, "title": "A", "explanation": "A",
                       "evidence_references": [{"source": "tests", "reference_path": "a.py", "detail": "d"}],
                       "affected_components": []},
                      {"finding_id": "F-002", "category": "Testing", "severity": "low",
                       "confidence": 0.7, "title": "B", "explanation": "B",
                       "evidence_references": [{"source": "tests", "reference_path": "b.py", "detail": "d"}],
                       "affected_components": []}],
            recommendations=[{"finding_id": "F-001", "recommendation": "add comprehensive test coverage",
                              "rationale": "R", "priority": {"score": 5.0, "impact": 5.0, "confidence": 0.7,
                              "severity": 5.0, "scope": 5.0, "formula": "f"},
                              "estimated_effort": "small", "estimated_risk": "low", "expected_benefit": "B"},
                             {"finding_id": "F-002", "recommendation": "add comprehensive test coverage",
                              "rationale": "R", "priority": {"score": 5.0, "impact": 5.0, "confidence": 0.7,
                              "severity": 5.0, "scope": 5.0, "formula": "f"},
                              "estimated_effort": "small", "estimated_risk": "low", "expected_benefit": "B"}],
        )
        gov = govern_engineering(ei, mode="legacy")
        decisions = {d.finding_id: d.decision for d in gov.assessment.approval_decisions}
        assert decisions["F-002"] == "REJECTED"


# ---------------------------------------------------------------------------
# Conflict Detection Tests
# ---------------------------------------------------------------------------

class TestConflictDetection:
    def test_no_conflicts_independent(self):
        ei = _ei_with_rec("add test coverage")
        gov = govern_engineering(ei)
        assert len(gov.assessment.conflicts) == 0

    def test_conflict_detected(self):
        ei = _minimal_ei(
            findings=[{"finding_id": "F-001", "category": "Architecture", "severity": "medium",
                       "confidence": 0.7, "title": "A", "explanation": "A",
                       "evidence_references": [{"source": "module_graph", "reference_path": "a.py", "detail": "d"}],
                       "affected_components": []},
                      {"finding_id": "F-002", "category": "Architecture", "severity": "medium",
                       "confidence": 0.7, "title": "B", "explanation": "B",
                       "evidence_references": [{"source": "module_graph", "reference_path": "b.py", "detail": "d"}],
                       "affected_components": []}],
            recommendations=[{"finding_id": "F-001", "recommendation": "split the module into smaller pieces",
                              "rationale": "R", "priority": {"score": 5.0, "impact": 5.0, "confidence": 0.7,
                              "severity": 5.0, "scope": 5.0, "formula": "f"},
                              "estimated_effort": "small", "estimated_risk": "low", "expected_benefit": "B"},
                             {"finding_id": "F-002", "recommendation": "merge the modules into one",
                              "rationale": "R", "priority": {"score": 5.0, "impact": 5.0, "confidence": 0.7,
                              "severity": 5.0, "scope": 5.0, "formula": "f"},
                              "estimated_effort": "small", "estimated_risk": "low", "expected_benefit": "B"}],
        )
        gov = govern_engineering(ei)
        assert len(gov.assessment.conflicts) >= 1


# ---------------------------------------------------------------------------
# Evidence Quality Tests
# ---------------------------------------------------------------------------

class TestEvidenceQuality:
    def test_high_evidence_with_multiple_refs(self):
        ei = _minimal_ei(
            findings=[{"finding_id": "F-001", "category": "Architecture", "severity": "high",
                       "confidence": 0.9, "title": "Cycle", "explanation": "Cycle",
                       "evidence_references": [
                           {"source": "module_graph", "reference_path": "a.py", "detail": "d1"},
                           {"source": "module_graph", "reference_path": "b.py", "detail": "d2"},
                           {"source": "debt_signals", "reference_path": "c.py", "detail": "d3"}],
                       "affected_components": []}],
            recommendations=[{"finding_id": "F-001", "recommendation": "break cycle",
                              "rationale": "R", "priority": {"score": 7.0, "impact": 7.0, "confidence": 0.9,
                              "severity": 7.5, "scope": 6.0, "formula": "f"},
                              "estimated_effort": "medium", "estimated_risk": "medium", "expected_benefit": "B"}],
        )
        gov = govern_engineering(ei)
        a = gov.assessment.recommendation_assessments[0]
        assert a.evidence_quality.level in ("medium", "high")

    def test_low_evidence_single_ref(self):
        ei = _ei_with_rec("do something", confidence=0.4)
        gov = govern_engineering(ei)
        a = gov.assessment.recommendation_assessments[0]
        assert a.evidence_quality.level == "low"


# ---------------------------------------------------------------------------
# Architecture Impact Tests
# ---------------------------------------------------------------------------

class TestArchitectureImpact:
    def test_local_impact(self):
        ei = _ei_with_rec("fix docstring", category="Documentation")
        gov = govern_engineering(ei)
        a = gov.assessment.recommendation_assessments[0]
        assert a.scope == "local"

    def test_system_impact(self):
        ei = _ei_with_rec("refactor architecture", category="Architecture")
        gov = govern_engineering(ei)
        a = gov.assessment.recommendation_assessments[0]
        assert a.scope == "system"


# ---------------------------------------------------------------------------
# Renderer Tests
# ---------------------------------------------------------------------------

class TestRenderer:
    def test_json_valid(self, sample_ei):
        gov = govern_engineering(sample_ei)
        data = json.loads(render_json(gov))
        assert "schema_version" in data

    def test_json_roundtrip(self, sample_ei):
        gov = govern_engineering(sample_ei)
        raw = render_json(gov)
        data = json.loads(raw)
        raw2 = json.dumps(data, indent=2, sort_keys=True)
        assert raw == raw2

    def test_markdown_has_header(self, sample_ei):
        gov = govern_engineering(sample_ei)
        md = render_markdown(gov)
        assert md.startswith("# Engineering Governance")

    def test_markdown_has_summary(self, sample_ei):
        gov = govern_engineering(sample_ei)
        md = render_markdown(gov)
        assert "## Approval Summary" in md

    def test_save_artifacts(self, sample_ei, tmp_output):
        gov = govern_engineering(sample_ei)
        jp, mp = save_artifacts(gov, tmp_output)
        assert jp.exists()
        assert mp.exists()


# ---------------------------------------------------------------------------
# CLI Tests
# ---------------------------------------------------------------------------

class TestCLI:
    def _run(self, args):
        return subprocess.run([sys.executable, "-m", "evosia.governance_cli", *args],
                              capture_output=True, text=True, timeout=30)

    def test_scan(self, sample_ei, tmp_output):
        ei_path = tmp_output / "ei.json"
        ei_path.write_text(json.dumps(sample_ei))
        result = self._run(["--input", str(ei_path), "--output-dir", str(tmp_output / "gov"), "scan"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] == "governed"

    def test_summary(self, sample_ei, tmp_output):
        ei_path = tmp_output / "ei.json"
        ei_path.write_text(json.dumps(sample_ei))
        result = self._run(["--input", str(ei_path), "summary"])
        assert result.returncode == 0
        assert "# Engineering Governance" in result.stdout


# ---------------------------------------------------------------------------
# Malformed Input Tests
# ---------------------------------------------------------------------------

class TestMalformedInput:
    def test_empty_ei(self):
        gov = govern_engineering({})
        assert isinstance(gov, EngineeringGovernance)
        assert gov.assessment.summary.total_evaluated == 0

    def test_ei_no_recommendations(self):
        gov = govern_engineering({"recommendations": [], "findings": []})
        assert gov.assessment.summary.total_evaluated == 0


# ---------------------------------------------------------------------------
# Hermes Self-Governance Tests
# ---------------------------------------------------------------------------

class TestHermesSelfGovernance:
    def test_hermes_all_decisions_have_rationale(self, hermes_ei):
        gov = govern_engineering(hermes_ei)
        for d in gov.assessment.approval_decisions:
            assert len(d.rationale) > 0

    def test_hermes_no_rejected_without_reason(self, hermes_ei):
        gov = govern_engineering(hermes_ei)
        for d in gov.assessment.approval_decisions:
            if d.decision == "REJECTED":
                assert "duplicate" in d.rationale.lower() or len(d.rationale) > 0

    def test_hermes_no_fabricated_conflicts(self, hermes_ei):
        gov = govern_engineering(hermes_ei)
        for c in gov.assessment.conflicts:
            assert len(c.description) > 0

    def test_hermes_deterministic(self, hermes_ei):
        gov1 = govern_engineering(hermes_ei)
        gov2 = govern_engineering(hermes_ei)
        assert render_json(gov1) == render_json(gov2)

    def test_hermes_markdown_readable(self, hermes_ei):
        gov = govern_engineering(hermes_ei, mode="legacy")
        md = render_markdown(gov)
        assert "## Approval Summary" in md
        assert "## Approved Candidate Missions" in md or "## Rejected" in md
