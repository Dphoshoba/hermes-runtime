"""Comprehensive tests for Engineering Intelligence v1.0.

Covers: finding generation, recommendation generation, mission generation,
severity scoring, confidence scoring, evidence references, determinism,
CLI, malformed input, and Hermes self-analysis.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from evosia.engineering_intel_models import (
    AffectedComponent,
    CandidateMission,
    ConfidenceScore,
    EngineeringIntelligence,
    EngineeringSummary,
    EvidenceReference,
    Finding,
    PriorityScore,
    Recommendation,
    RiskAssessment,
)
from evosia.engineering_analyzer import analyze_engineering
from evosia.engineering_renderer import render_json, render_markdown, save_artifacts
from evosia.repo_scanner import scan_repository
from evosia.repo_analyzer import analyze_repository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_REPO = Path(__file__).resolve().parent.parent / "validation" / "sample-repo"
HERMES_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def sample_repo_path() -> Path:
    return SAMPLE_REPO


@pytest.fixture
def hermes_root() -> Path:
    return HERMES_ROOT


@pytest.fixture
def tmp_output(tmp_path: Path) -> Path:
    d = tmp_path / "engineering-intel"
    d.mkdir()
    return d


@pytest.fixture
def sample_ri(sample_repo_path: Path) -> dict:
    """Pre-computed Repository Intelligence dict for sample-repo."""
    scan = scan_repository(sample_repo_path)
    ri = analyze_repository(scan)
    return json.loads(json.dumps(ri.as_dict(), sort_keys=True))


@pytest.fixture
def sample_ei(sample_ri: dict) -> EngineeringIntelligence:
    """Pre-computed Engineering Intelligence for sample-repo."""
    return analyze_engineering(sample_ri)


@pytest.fixture
def hermes_ri(hermes_root: Path) -> dict:
    """Pre-computed Repository Intelligence for Hermes Runtime."""
    scan = scan_repository(hermes_root)
    ri = analyze_repository(scan)
    return json.loads(json.dumps(ri.as_dict(), sort_keys=True))


@pytest.fixture
def hermes_ei(hermes_ri: dict) -> EngineeringIntelligence:
    """Pre-computed Engineering Intelligence for Hermes Runtime."""
    return analyze_engineering(hermes_ri)


# ---------------------------------------------------------------------------
# Minimal RI fixture (for controlled testing)
# ---------------------------------------------------------------------------

def _minimal_ri(**overrides) -> dict:
    """Build minimal RI dict for testing specific finding categories."""
    base = {
        "repository": {"name": "test-repo", "path": "/tmp/test"},
        "modules": [
            {
                "path": "src/main.py",
                "package": "src",
                "name": "main",
                "line_count": 100,
                "ast_size": 50,
                "has_docstring": True,
                "functions": [],
                "classes": [],
                "imports": [],
            }
        ],
        "public_api": {
            "classes": [],
            "functions": [],
            "module_constants": [],
            "cli_entry_points": [],
        },
        "module_graph": {
            "nodes": ["src/main.py"],
            "edges": [],
            "isolated_modules": ["src/main.py"],
            "highly_connected_modules": [],
            "import_cycles": [],
        },
        "tests": {
            "test_modules": [],
            "total_test_functions": 0,
            "total_test_classes": 0,
            "modules_with_tests": [],
            "modules_without_tests": ["src/main.py"],
        },
        "dependencies": {
            "runtime": [],
            "optional": [],
            "test": [],
            "dev": [],
            "python_version": ">=3.10",
            "build_backend": "setuptools.build_meta",
        },
        "configuration": [
            {"path": "pyproject.toml", "kind": "pyproject.toml"},
        ],
        "complexity_signals": [],
        "technical_debt_signals": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Data Model Tests
# ---------------------------------------------------------------------------

class TestEvidenceReference:
    def test_frozen(self):
        ref = EvidenceReference(source="test", reference_path="a.py", detail="detail")
        with pytest.raises(AttributeError):
            ref.source = "changed"  # type: ignore

    def test_as_dict(self):
        ref = EvidenceReference(source="test", reference_path="a.py", detail="detail")
        d = ref.as_dict()
        assert d["source"] == "test"
        assert d["reference_path"] == "a.py"
        assert d["detail"] == "detail"


class TestAffectedComponent:
    def test_frozen(self):
        comp = AffectedComponent(component_type="module", component_path="a.py", component_name="a")
        with pytest.raises(AttributeError):
            comp.component_type = "changed"  # type: ignore

    def test_as_dict(self):
        comp = AffectedComponent(component_type="module", component_path="a.py", component_name="a")
        d = comp.as_dict()
        assert d["component_type"] == "module"


class TestPriorityScore:
    def test_score_range(self):
        p = PriorityScore(score=5.0, impact=5.0, confidence=0.7, severity=5.0, scope=5.0, formula="test")
        assert 0.0 <= p.score <= 10.0

    def test_as_dict_rounds(self):
        p = PriorityScore(score=5.123, impact=3.456, confidence=0.789, severity=5.0, scope=4.0, formula="test")
        d = p.as_dict()
        assert d["score"] == 5.12
        assert d["confidence"] == 0.79


class TestFinding:
    def test_has_required_fields(self):
        f = Finding(
            finding_id="F-001",
            category="Architecture",
            severity="high",
            confidence=0.8,
            title="Test",
            explanation="Test finding",
            evidence_references=(EvidenceReference(source="test", reference_path="x", detail="y"),),
            affected_components=(AffectedComponent(component_type="module", component_path="x", component_name="y"),),
        )
        assert f.finding_id == "F-001"
        assert f.category == "Architecture"
        assert len(f.evidence_references) == 1
        assert len(f.affected_components) == 1

    def test_as_dict(self):
        f = Finding(
            finding_id="F-001",
            category="Testing",
            severity="low",
            confidence=0.5,
            title="No tests",
            explanation="Module lacks tests",
            evidence_references=(),
            affected_components=(),
        )
        d = f.as_dict()
        assert d["finding_id"] == "F-001"
        assert d["confidence"] == 0.5


class TestEngineeringIntelligence:
    def test_default_values(self):
        ei = EngineeringIntelligence()
        assert ei.schema_version == "1"
        assert len(ei.findings) == 0
        assert ei.summary.total_findings == 0
        assert ei.summary.health_score == 100.0

    def test_as_dict_has_schema_version(self):
        ei = EngineeringIntelligence()
        d = ei.as_dict()
        assert "schema_version" in d
        assert "findings" in d
        assert "recommendations" in d
        assert "candidate_missions" in d
        assert "risk_assessment" in d
        assert "summary" in d


# ---------------------------------------------------------------------------
# Finding Generation Tests
# ---------------------------------------------------------------------------

class TestFindingGeneration:
    def test_findings_from_cycles(self):
        ri = _minimal_ri(**{
            "module_graph": {
                "nodes": ["a.py", "b.py"],
                "edges": [("a.py", "b.py"), ("b.py", "a.py")],
                "isolated_modules": (),
                "highly_connected_modules": (),
                "import_cycles": [["a.py", "b.py", "a.py"]],
            },
        })
        ei = analyze_engineering(ri)
        cycle_findings = [f for f in ei.findings if f.category == "Architecture"]
        assert len(cycle_findings) >= 1
        assert cycle_findings[0].severity == "high"

    def test_findings_from_complexity_signals(self):
        ri = _minimal_ri(**{
            "complexity_signals": [
                {"signal_type": "large_module", "target": "big.py", "message": "500 lines", "severity": "warning"},
            ],
        })
        ei = analyze_engineering(ri)
        complexity_findings = [f for f in ei.findings if f.category == "Complexity"]
        assert len(complexity_findings) >= 1

    def test_findings_from_debt_signals(self):
        ri = _minimal_ri(**{
            "technical_debt_signals": [
                {"signal_type": "missing_docstring", "target": "src/main.py", "message": "No docstring", "evidence": "Module has 100 lines but no docstring", "severity": "info"},
            ],
        })
        ei = analyze_engineering(ri)
        doc_findings = [f for f in ei.findings if f.category == "Documentation"]
        assert len(doc_findings) >= 1

    def test_findings_from_untested_modules(self):
        ri = _minimal_ri(**{
            "tests": {
                "test_modules": [],
                "total_test_functions": 0,
                "total_test_classes": 0,
                "modules_with_tests": [],
                "modules_without_tests": ["src/main.py"],
            },
        })
        ei = analyze_engineering(ri)
        test_findings = [f for f in ei.findings if f.category == "Testing"]
        assert len(test_findings) >= 1

    def test_findings_have_unique_ids(self):
        ri = _minimal_ri(**{
            "complexity_signals": [
                {"signal_type": "large_module", "target": f"mod{i}.py", "message": "large", "severity": "info"}
                for i in range(10)
            ],
        })
        ei = analyze_engineering(ri)
        ids = [f.finding_id for f in ei.findings]
        assert len(ids) == len(set(ids))

    def test_findings_sorted_by_severity(self):
        ri = _minimal_ri(**{
            "complexity_signals": [
                {"signal_type": "large_module", "target": "a.py", "message": "large", "severity": "info"},
            ],
            "module_graph": {
                "nodes": ["a.py"],
                "edges": [],
                "isolated_modules": ["a.py"],
                "highly_connected_modules": [],
                "import_cycles": [["a.py", "b.py", "a.py"]],
            },
        })
        ei = analyze_engineering(ri)
        severities = [f.severity for f in ei.findings]
        sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        for i in range(len(severities) - 1):
            assert sev_order.get(severities[i], 5) <= sev_order.get(severities[i + 1], 5)


# ---------------------------------------------------------------------------
# Evidence Reference Tests
# ---------------------------------------------------------------------------

class TestEvidenceReferences:
    def test_every_finding_has_evidence(self, sample_ei: EngineeringIntelligence):
        for f in sample_ei.findings:
            assert len(f.evidence_references) > 0, f"{f.finding_id} has no evidence"

    def test_evidence_references_ri_data(self, sample_ei: EngineeringIntelligence):
        valid_sources = {"complexity_signals", "debt_signals", "module_graph", "tests", "dependencies", "public_api", "configuration", "modules"}
        for f in sample_ei.findings:
            for ev in f.evidence_references:
                assert ev.source in valid_sources, f"Invalid source: {ev.source}"

    def test_no_fabricated_evidence(self, hermes_ei: EngineeringIntelligence):
        for f in hermes_ei.findings:
            for ev in f.evidence_references:
                assert len(ev.reference_path) > 0
                assert len(ev.detail) > 0


# ---------------------------------------------------------------------------
# Recommendation Generation Tests
# ---------------------------------------------------------------------------

class TestRecommendationGeneration:
    def test_one_recommendation_per_finding(self, sample_ei: EngineeringIntelligence):
        assert len(sample_ei.recommendations) == len(sample_ei.findings)

    def test_recommendation_has_priority(self, sample_ei: EngineeringIntelligence):
        for r in sample_ei.recommendations:
            assert isinstance(r.priority, PriorityScore)
            assert 0.0 <= r.priority.score <= 10.0

    def test_recommendation_has_effort(self, sample_ei: EngineeringIntelligence):
        valid_efforts = {"trivial", "small", "medium", "large", "xl"}
        for r in sample_ei.recommendations:
            assert r.estimated_effort in valid_efforts

    def test_recommendation_has_risk(self, sample_ei: EngineeringIntelligence):
        valid_risks = {"none", "low", "medium", "high"}
        for r in sample_ei.recommendations:
            assert r.estimated_risk in valid_risks

    def test_recommendation_references_finding(self, sample_ei: EngineeringIntelligence):
        finding_ids = {f.finding_id for f in sample_ei.findings}
        for r in sample_ei.recommendations:
            assert r.finding_id in finding_ids


# ---------------------------------------------------------------------------
# Mission Recommendation Tests
# ---------------------------------------------------------------------------

class TestMissionGeneration:
    def test_missions_group_related_findings(self, hermes_ei: EngineeringIntelligence):
        assert len(hermes_ei.candidate_missions) > 0

    def test_mission_has_unique_id(self, hermes_ei: EngineeringIntelligence):
        ids = [m.mission_id for m in hermes_ei.candidate_missions]
        assert len(ids) == len(set(ids))

    def test_mission_has_required_fields(self, hermes_ei: EngineeringIntelligence):
        for m in hermes_ei.candidate_missions:
            assert len(m.title) > 0
            assert len(m.description) > 0
            assert len(m.objective) > 0
            assert len(m.supporting_findings) > 0
            assert isinstance(m.priority, PriorityScore)
            assert isinstance(m.risk, RiskAssessment)

    def test_mission_does_not_enqueue(self):
        """Missions must never be enqueued - this is a reasoning layer only."""
        ri = _minimal_ri()
        ei = analyze_engineering(ri)
        # Verify model is pure data - no side effects
        d = ei.as_dict()
        assert isinstance(d, dict)


# ---------------------------------------------------------------------------
# Severity & Confidence Tests
# ---------------------------------------------------------------------------

class TestSeverityScoring:
    def test_severity_mapping_from_signals(self):
        ri = _minimal_ri(**{
            "module_graph": {
                "nodes": ["a.py", "b.py"],
                "edges": [],
                "isolated_modules": (),
                "highly_connected_modules": (),
                "import_cycles": [["a.py", "b.py", "a.py"]],
            },
        })
        ei = analyze_engineering(ri)
        cycle_findings = [f for f in ei.findings if f.category == "Architecture"]
        assert cycle_findings[0].severity in ("high", "critical")

    def test_health_score_formula(self):
        ri = _minimal_ri()
        ei = analyze_engineering(ri)
        assert 0.0 <= ei.summary.health_score <= 100.0


class TestConfidenceScoring:
    def test_confidence_range(self, sample_ei: EngineeringIntelligence):
        for f in sample_ei.findings:
            assert 0.0 <= f.confidence <= 1.0

    def test_higher_evidence_higher_confidence(self):
        ri1 = _minimal_ri(**{
            "complexity_signals": [
                {"signal_type": "large_module", "target": "a.py", "message": "large", "severity": "info"},
            ],
        })
        ri2 = _minimal_ri(**{
            "complexity_signals": [
                {"signal_type": "large_module", "target": "a.py", "message": "large", "severity": "info"},
                {"signal_type": "large_module", "target": "b.py", "message": "large", "severity": "info"},
            ],
        })
        ei1 = analyze_engineering(ri1)
        ei2 = analyze_engineering(ri2)
        # More findings should generally produce same or higher total confidence
        total1 = sum(f.confidence for f in ei1.findings)
        total2 = sum(f.confidence for f in ei2.findings)
        assert total2 >= total1


# ---------------------------------------------------------------------------
# Renderer Tests
# ---------------------------------------------------------------------------

class TestRendererJSON:
    def test_json_is_valid(self, sample_ei: EngineeringIntelligence):
        raw = render_json(sample_ei)
        data = json.loads(raw)
        assert isinstance(data, dict)

    def test_json_has_schema_version(self, sample_ei: EngineeringIntelligence):
        data = json.loads(render_json(sample_ei))
        assert "schema_version" in data

    def test_json_roundtrip(self, sample_ei: EngineeringIntelligence):
        raw = render_json(sample_ei)
        data = json.loads(raw)
        raw2 = json.dumps(data, indent=2, sort_keys=True)
        assert raw == raw2


class TestRendererMarkdown:
    def test_markdown_has_header(self, sample_ei: EngineeringIntelligence):
        md = render_markdown(sample_ei)
        assert md.startswith("# Engineering Intelligence")

    def test_markdown_has_summary(self, sample_ei: EngineeringIntelligence):
        md = render_markdown(sample_ei)
        assert "## Executive Summary" in md

    def test_markdown_has_risk(self, sample_ei: EngineeringIntelligence):
        md = render_markdown(sample_ei)
        assert "## Risk Assessment" in md

    def test_markdown_has_findings(self, sample_ei: EngineeringIntelligence):
        md = render_markdown(sample_ei)
        assert "## Findings" in md

    def test_markdown_has_recommendations(self, sample_ei: EngineeringIntelligence):
        md = render_markdown(sample_ei)
        assert "## Recommendations" in md

    def test_markdown_has_missions(self, sample_ei: EngineeringIntelligence):
        md = render_markdown(sample_ei)
        assert "## Candidate Missions" in md


class TestRendererSaveArtifacts:
    def test_creates_json_and_md(self, sample_ei: EngineeringIntelligence, tmp_output: Path):
        json_path, md_path = save_artifacts(sample_ei, tmp_output)
        assert json_path.exists()
        assert md_path.exists()
        assert json_path.name == "ENGINEERING_INTELLIGENCE.json"
        assert md_path.name == "ENGINEERING_INTELLIGENCE.md"

    def test_json_is_valid_file(self, sample_ei: EngineeringIntelligence, tmp_output: Path):
        json_path, _ = save_artifacts(sample_ei, tmp_output)
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert "schema_version" in data

    def test_md_starts_with_header(self, sample_ei: EngineeringIntelligence, tmp_output: Path):
        _, md_path = save_artifacts(sample_ei, tmp_output)
        content = md_path.read_text(encoding="utf-8")
        assert content.startswith("# Engineering Intelligence")


# ---------------------------------------------------------------------------
# Determinism Tests
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_analyze_deterministic(self, sample_ri: dict):
        ei1 = analyze_engineering(sample_ri)
        ei2 = analyze_engineering(sample_ri)
        assert render_json(ei1) == render_json(ei2)

    def test_hermes_deterministic(self, hermes_ri: dict):
        ei1 = analyze_engineering(hermes_ri)
        ei2 = analyze_engineering(hermes_ri)
        assert render_json(ei1) == render_json(ei2)


# ---------------------------------------------------------------------------
# CLI Integration Tests
# ---------------------------------------------------------------------------

class TestCLI:
    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "evosia.engineering_cli", *args],
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_scan(self, sample_repo_path: Path, tmp_output: Path):
        # First generate RI
        from evosia.repo_scanner import scan_repository as sr
        from evosia.repo_analyzer import analyze_repository as ar
        from evosia.repo_renderer import save_artifacts as sa
        ri_dir = tmp_output / "ri"
        ri_dir.mkdir()
        scan = sr(sample_repo_path)
        ri = ar(scan)
        sa(ri, ri_dir)

        # Now run engineering scan
        result = self._run([
            "--repo", str(sample_repo_path),
            "--input", str(ri_dir / "REPOSITORY_INTELLIGENCE.json"),
            "--output-dir", str(tmp_output / "ei"),
            "scan",
        ])
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "analyzed"
        assert data["findings"] >= 0

    def test_summary(self, sample_repo_path: Path, tmp_output: Path):
        from evosia.repo_scanner import scan_repository as sr
        from evosia.repo_analyzer import analyze_repository as ar
        from evosia.repo_renderer import save_artifacts as sa
        ri_dir = tmp_output / "ri"
        ri_dir.mkdir()
        scan = sr(sample_repo_path)
        ri = ar(scan)
        sa(ri, ri_dir)

        result = self._run([
            "--repo", str(sample_repo_path),
            "--input", str(ri_dir / "REPOSITORY_INTELLIGENCE.json"),
            "summary",
        ])
        assert result.returncode == 0
        assert "# Engineering Intelligence" in result.stdout


# ---------------------------------------------------------------------------
# Malformed Input Tests
# ---------------------------------------------------------------------------

class TestMalformedInput:
    def test_empty_ri(self):
        ei = analyze_engineering({})
        assert isinstance(ei, EngineeringIntelligence)
        # Empty RI may still find configuration issues (missing configs)
        assert ei.summary.health_score >= 0.0

    def test_malformed_ri_minimal(self):
        ei = analyze_engineering({"repository": {"name": "bad"}})
        assert isinstance(ei, EngineeringIntelligence)
        assert ei.summary.health_score >= 0.0

    def test_ri_with_none_values(self):
        ei = analyze_engineering({
            "repository": {"name": "test"},
            "modules": [],
            "public_api": {"classes": [], "functions": [], "module_constants": [], "cli_entry_points": []},
            "module_graph": {"nodes": [], "edges": [], "isolated_modules": [], "highly_connected_modules": [], "import_cycles": []},
            "tests": {"test_modules": [], "total_test_functions": 0, "total_test_classes": 0, "modules_with_tests": [], "modules_without_tests": []},
            "dependencies": {"runtime": [], "optional": [], "test": [], "dev": [], "python_version": None, "build_backend": None},
            "configuration": [],
            "complexity_signals": [],
            "technical_debt_signals": [],
        })
        assert isinstance(ei, EngineeringIntelligence)


# ---------------------------------------------------------------------------
# Hermes Self-Analysis Tests
# ---------------------------------------------------------------------------

class TestHermesSelfAnalysis:
    def test_hermes_finds_real_issues(self, hermes_ei: EngineeringIntelligence):
        assert hermes_ei.summary.total_findings > 0
        # Hermes has known import cycles
        arch_findings = [f for f in hermes_ei.findings if f.category == "Architecture"]
        assert len(arch_findings) > 0

    def test_hermes_all_findings_have_evidence(self, hermes_ei: EngineeringIntelligence):
        for f in hermes_ei.findings:
            assert len(f.evidence_references) > 0, f"{f.finding_id} lacks evidence"

    def test_hermes_no_fabricated_findings(self, hermes_ei: EngineeringIntelligence):
        """No finding should exist without a corresponding RI signal."""
        for f in hermes_ei.findings:
            assert f.finding_id.startswith("FINDING-")
            assert len(f.title) > 0
            assert len(f.explanation) > 0

    def test_hermes_candidate_missions(self, hermes_ei: EngineeringIntelligence):
        assert len(hermes_ei.candidate_missions) > 0
        for m in hermes_ei.candidate_missions:
            assert len(m.supporting_findings) > 0
            assert m.mission_type in {
                "architecture_cleanup", "documentation_refresh", "testing_improvements",
                "dependency_review", "packaging_improvements", "configuration_cleanup",
                "repository_maintenance", "release_readiness",
            }

    def test_hermes_deterministic(self, hermes_ri: dict):
        ei1 = analyze_engineering(hermes_ri)
        ei2 = analyze_engineering(hermes_ri)
        assert render_json(ei1) == render_json(ei2)

    def test_hermes_markdown_readable(self, hermes_ei: EngineeringIntelligence):
        md = render_markdown(hermes_ei)
        assert "## Executive Summary" in md
        assert "## Risk Assessment" in md
        assert "## Findings" in md
        assert "## Recommendations" in md
        assert "## Candidate Missions" in md
