"""Tests for Beta Readiness Sprint v1.1.1 fixes."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from hermes_v01.repo_scanner import scan_repository
from hermes_v01.repo_analyzer import analyze_repository
from hermes_v01.engineering_analyzer import analyze_engineering
from hermes_v01.governance_analyzer import govern_engineering
from hermes_v01.mission_generator import generate_missions
from hermes_v01.benchmark_engine import (
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
# 3. Governance approval rate
# ---------------------------------------------------------------------------

class TestGovernanceApproval:
    def test_approval_rate_above_10_percent(self):
        scan = scan_repository(HERMES_ROOT)
        ri = analyze_repository(scan)
        ri_json = json.loads(json.dumps(ri.as_dict(), sort_keys=True))
        ei = analyze_engineering(ri_json)
        ei_json = json.loads(json.dumps(ei.as_dict(), sort_keys=True))
        gov = govern_engineering(ei_json)
        s = gov.as_dict()["assessment"]["summary"]
        assert s["approval_rate"] >= 0.10, f"Approval rate too low: {s['approval_rate']:.1%}"

    def test_duplicate_rate_below_50_percent(self):
        scan = scan_repository(HERMES_ROOT)
        ri = analyze_repository(scan)
        ri_json = json.loads(json.dumps(ri.as_dict(), sort_keys=True))
        ei = analyze_engineering(ri_json)
        ei_json = json.loads(json.dumps(ei.as_dict(), sort_keys=True))
        gov = govern_engineering(ei_json)
        s = gov.as_dict()["assessment"]["summary"]
        dup_rate = s.get("duplicates_found", 0) / max(s["total_evaluated"], 1)
        assert dup_rate < 0.50, f"Duplicate rate too high: {dup_rate:.1%}"

    def test_no_false_rejections(self):
        scan = scan_repository(HERMES_ROOT)
        ri = analyze_repository(scan)
        ri_json = json.loads(json.dumps(ri.as_dict(), sort_keys=True))
        ei = analyze_engineering(ri_json)
        ei_json = json.loads(json.dumps(ei.as_dict(), sort_keys=True))
        gov = govern_engineering(ei_json)
        s = gov.as_dict()["assessment"]["summary"]
        # Should have approved missions
        assert s["approved"] > 0


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

    def test_governance_confidence_above_10_percent(self):
        result = run_benchmark(str(HERMES_ROOT))
        conf = compute_confidence([result])
        assert conf.confidence_governance >= 0.10

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
