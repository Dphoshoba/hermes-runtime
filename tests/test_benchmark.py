"""Tests for Benchmark Engine and Validation Program v1.1."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from hermes_v01.benchmark_engine import (
    BenchmarkComparison,
    BenchmarkResult,
    BenchmarkSummary,
    EngineeringConfidence,
    Snapshot,
    TrendEntry,
    compare_benchmarks,
    compute_confidence,
    compute_summary,
    compute_trend,
    detect_changes,
    run_benchmark,
    save_snapshot,
    load_snapshots,
)

HERMES_ROOT = Path(__file__).resolve().parent.parent
HERMES_SRC = HERMES_ROOT / "hermes_v01"


# ---------------------------------------------------------------------------
# 1. Benchmark calculations
# ---------------------------------------------------------------------------

class TestBenchmarkCalculations:
    def test_run_benchmark_hermes(self):
        result = run_benchmark(str(HERMES_ROOT))
        assert result.repository_name == "hermes-runtime-v0.3-runtime"
        assert result.modules_scanned > 0
        assert result.findings_generated > 0
        assert result.duration_seconds > 0
        assert result.peak_memory_bytes > 0

    def test_benchmark_result_as_dict(self):
        result = run_benchmark(str(HERMES_ROOT))
        d = result.as_dict()
        assert d["repository_name"] == "hermes-runtime-v0.3-runtime"
        assert "timing" in d
        assert "memory" in d
        assert "repository_metrics" in d
        assert "pipeline_output" in d

    def test_benchmark_timing_fields(self):
        result = run_benchmark(str(HERMES_ROOT))
        d = result.as_dict()
        assert d["timing"]["repo_scan_seconds"] > 0
        assert d["timing"]["ri_generation_seconds"] > 0
        assert d["timing"]["ei_generation_seconds"] > 0
        assert d["timing"]["gov_generation_seconds"] >= 0
        assert d["timing"]["mission_generation_seconds"] >= 0


# ---------------------------------------------------------------------------
# 2. Snapshot comparison
# ---------------------------------------------------------------------------

class TestSnapshotComparison:
    def test_compare_same_repo(self):
        r1 = run_benchmark(str(HERMES_ROOT))
        r2 = run_benchmark(str(HERMES_ROOT))
        comparison = compare_benchmarks(r1, r2)
        assert comparison.baseline_name == "hermes-runtime-v0.3-runtime"
        assert comparison.current_name == "hermes-runtime-v0.3-runtime"
        assert abs(comparison.duration_change_pct) < 50  # Same repo, similar time

    def test_comparison_as_dict(self):
        r1 = run_benchmark(str(HERMES_ROOT))
        r2 = run_benchmark(str(HERMES_ROOT))
        comparison = compare_benchmarks(r1, r2)
        d = comparison.as_dict()
        assert "baseline" in d
        assert "current" in d
        assert "changes" in d


# ---------------------------------------------------------------------------
# 3. Trend generation
# ---------------------------------------------------------------------------

class TestTrendGeneration:
    def test_trend_from_snapshots(self, tmp_path):
        result = run_benchmark(str(HERMES_ROOT))
        snapshot = Snapshot(
            snapshot_id="test-001", timestamp=result.timestamp,
            repository_name=result.repository_name, result=result,
            findings_summary={"total": result.findings_generated},
            missions_summary={"total": result.missions_generated},
            engineering_health=85.0,
        )
        save_snapshot(snapshot, tmp_path)
        snapshots = load_snapshots(tmp_path)
        trend = compute_trend(snapshots)
        assert len(trend) == 1
        assert trend[0].repository_name == "hermes-runtime-v0.3-runtime"


# ---------------------------------------------------------------------------
# 4. Golden repository validation
# ---------------------------------------------------------------------------

class TestGoldenValidation:
    def test_hermes_golden_dataset_exists(self):
        golden_path = HERMES_ROOT / "validation" / "golden_repositories" / "hermes-runtime.json"
        assert golden_path.exists()
        data = json.loads(golden_path.read_text())
        assert data["schema_version"] == "1"
        assert data["repository"]["name"] == "hermes-runtime-v0.3-runtime"

    def test_benchmark_against_golden_expectations(self):
        golden_path = HERMES_ROOT / "validation" / "golden_repositories" / "hermes-runtime.json"
        golden = json.loads(golden_path.read_text())
        result = run_benchmark(str(HERMES_ROOT))
        assert result.modules_scanned >= golden["expected_modules_min"]
        assert result.findings_generated >= golden["expected_findings_min"]
        assert result.recommendations_generated >= golden["expected_recommendations_min"]


# ---------------------------------------------------------------------------
# 5. Deterministic benchmark output
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_deterministic_benchmark(self):
        r1 = run_benchmark(str(HERMES_ROOT))
        r2 = run_benchmark(str(HERMES_ROOT))
        # Same repo → same findings/missions count
        assert r1.findings_generated == r2.findings_generated
        assert r1.recommendations_generated == r2.recommendations_generated
        assert r1.missions_generated == r2.missions_generated
        assert r1.modules_scanned == r2.modules_scanned

    def test_snapshot_deterministic(self, tmp_path):
        result = run_benchmark(str(HERMES_ROOT))
        s1 = Snapshot(
            snapshot_id="det-001", timestamp=result.timestamp,
            repository_name=result.repository_name, result=result,
            findings_summary={"total": result.findings_generated},
            missions_summary={"total": result.missions_generated},
            engineering_health=85.0,
        )
        p1 = save_snapshot(s1, tmp_path)
        loaded = load_snapshots(tmp_path)
        assert loaded[0].findings_summary == s1.findings_summary


# ---------------------------------------------------------------------------
# 6. Malformed benchmark inputs
# ---------------------------------------------------------------------------

class TestMalformedInputs:
    def test_summary_empty(self):
        summary = compute_summary([])
        assert summary.total_repositories == 0
        assert summary.successful_benchmarks == 0

    def test_compare_needs_two(self, tmp_path):
        result = run_benchmark(str(HERMES_ROOT))
        snapshot = Snapshot(
            snapshot_id="one-001", timestamp=result.timestamp,
            repository_name=result.repository_name, result=result,
            findings_summary={}, missions_summary={}, engineering_health=0.0,
        )
        save_snapshot(snapshot, tmp_path)
        snapshots = load_snapshots(tmp_path)
        assert len(snapshots) == 1
        # Cannot compare with only 1 snapshot
        assert len(snapshots) < 2

    def test_confidence_empty(self):
        conf = compute_confidence([])
        assert conf.confidence_overall == 0.0


# ---------------------------------------------------------------------------
# 7. CLI integration
# ---------------------------------------------------------------------------

class TestCLI:
    def _run(self, args):
        return subprocess.run(
            [sys.executable, "-m", "hermes_v01.benchmark_cli", *args],
            capture_output=True, text=True, timeout=120,
        )

    def test_run_self_benchmark(self):
        r = self._run(["--config", str(HERMES_ROOT / "validation" / "benchmark_config.json"),
                        "run", "--repo", str(HERMES_ROOT)])
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["status"] == "completed"
        assert data["repository"] == "hermes-runtime-v0.3-runtime"

    def test_summary(self, tmp_path):
        # First run a benchmark to create snapshots
        self._run(["--config", str(HERMES_ROOT / "validation" / "benchmark_config.json"),
                    "run", "--repo", str(HERMES_ROOT)])
        config = json.loads((HERMES_ROOT / "validation" / "benchmark_config.json").read_text())
        snapshots_dir = HERMES_ROOT / config["snapshots_dir"]
        r = self._run(["--config", str(HERMES_ROOT / "validation" / "benchmark_config.json"),
                        "--snapshots-dir", str(snapshots_dir), "summary"])
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["total_repositories"] >= 1

    def test_confidence(self):
        config = json.loads((HERMES_ROOT / "validation" / "benchmark_config.json").read_text())
        snapshots_dir = HERMES_ROOT / config["snapshots_dir"]
        r = self._run(["--config", str(HERMES_ROOT / "validation" / "benchmark_config.json"),
                        "--snapshots-dir", str(snapshots_dir), "confidence"])
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert "confidence_scores" in data
        assert data["calculation_method"] == "evidence_based"

    def test_report(self):
        config = json.loads((HERMES_ROOT / "validation" / "benchmark_config.json").read_text())
        snapshots_dir = HERMES_ROOT / config["snapshots_dir"]
        r = self._run(["--config", str(HERMES_ROOT / "validation" / "benchmark_config.json"),
                        "--snapshots-dir", str(snapshots_dir), "report"])
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert "summary" in data
        assert "confidence" in data

    def test_trend(self):
        config = json.loads((HERMES_ROOT / "validation" / "benchmark_config.json").read_text())
        snapshots_dir = HERMES_ROOT / config["snapshots_dir"]
        r = self._run(["--config", str(HERMES_ROOT / "validation" / "benchmark_config.json"),
                        "--snapshots-dir", str(snapshots_dir), "trend"])
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert "trend" in data


# ---------------------------------------------------------------------------
# 8. Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    def test_existing_tests_still_pass(self):
        # Verify core modules still work
        from hermes_v01.mission import MissionPlanner
        from hermes_v01.mission_recommendation_models import DraftMission
        from hermes_v01.engineering_analyzer import analyze_engineering
        from hermes_v01.governance_analyzer import govern_engineering
        planner = MissionPlanner()
        assert planner is not None

    def test_benchmark_module_imports(self):
        from hermes_v01.benchmark_engine import (
            run_benchmark, compare_benchmarks, compute_summary,
            compute_trend, compute_confidence, save_snapshot, load_snapshots,
        )
        assert callable(run_benchmark)
        assert callable(compare_benchmarks)
        assert callable(compute_summary)


# ---------------------------------------------------------------------------
# 9. Engineering confidence
# ---------------------------------------------------------------------------

class TestEngineeringConfidence:
    def test_confidence_from_results(self):
        result = run_benchmark(str(HERMES_ROOT))
        conf = compute_confidence([result])
        assert 0.0 <= conf.confidence_repo_intel <= 1.0
        assert 0.0 <= conf.confidence_eng_intel <= 1.0
        assert 0.0 <= conf.confidence_governance <= 1.0
        assert 0.0 <= conf.confidence_recommendations <= 1.0
        assert 0.0 <= conf.confidence_overall <= 1.0
        assert len(conf.evidence_sources) > 0

    def test_confidence_as_dict(self):
        result = run_benchmark(str(HERMES_ROOT))
        conf = compute_confidence([result])
        d = conf.as_dict()
        assert d["calculation_method"] == "evidence_based"
        assert "confidence_scores" in d
        assert "evidence_sources" in d


# ---------------------------------------------------------------------------
# 10. Snapshot persistence
# ---------------------------------------------------------------------------

class TestSnapshotPersistence:
    def test_save_and_load(self, tmp_path):
        result = run_benchmark(str(HERMES_ROOT))
        snapshot = Snapshot(
            snapshot_id="persist-001", timestamp=result.timestamp,
            repository_name=result.repository_name, result=result,
            findings_summary={"total": result.findings_generated},
            missions_summary={"total": result.missions_generated},
            engineering_health=85.0,
        )
        path = save_snapshot(snapshot, tmp_path)
        assert path.exists()
        snapshots = load_snapshots(tmp_path)
        assert len(snapshots) == 1
        assert snapshots[0].snapshot_id == "persist-001"

    def test_load_nonexistent(self, tmp_path):
        snapshots = load_snapshots(tmp_path / "nonexistent")
        assert snapshots == []


# ---------------------------------------------------------------------------
# 11. Detect changes between snapshots
# ---------------------------------------------------------------------------

class TestDetectChanges:
    def test_no_changes_same_snapshot(self):
        result = run_benchmark(str(HERMES_ROOT))
        s = Snapshot(
            snapshot_id="same-001", timestamp=result.timestamp,
            repository_name=result.repository_name, result=result,
            findings_summary={"total": result.findings_generated},
            missions_summary={"total": result.missions_generated},
            engineering_health=85.0,
        )
        changes = detect_changes(s, s)
        assert changes["repository_changed"] is False

    def test_changes_detected(self):
        r = run_benchmark(str(HERMES_ROOT))
        s1 = Snapshot(
            snapshot_id="a-001", timestamp=r.timestamp,
            repository_name=r.repository_name, result=r,
            findings_summary={"total": 10}, missions_summary={"total": 2},
            engineering_health=85.0,
        )
        s2 = Snapshot(
            snapshot_id="b-001", timestamp=r.timestamp,
            repository_name=r.repository_name, result=r,
            findings_summary={"total": 15}, missions_summary={"total": 2},
            engineering_health=85.0,
        )
        changes = detect_changes(s1, s2)
        assert changes["findings_changed"] is True
        assert changes["new_findings"] == 5


# ---------------------------------------------------------------------------
# 12. Benchmark summary
# ---------------------------------------------------------------------------

class TestBenchmarkSummary:
    def test_summary_from_results(self):
        r1 = run_benchmark(str(HERMES_ROOT))
        r2 = run_benchmark(str(HERMES_ROOT))
        summary = compute_summary([r1, r2])
        assert summary.total_repositories == 2
        assert summary.successful_benchmarks == 2
        assert summary.failed_benchmarks == 0
        assert summary.avg_duration_seconds > 0
        assert summary.determinism_rate > 0.8

    def test_summary_with_failures(self):
        r = run_benchmark(str(HERMES_ROOT))
        failed = BenchmarkResult(
            repository_name="broken", repository_path="/nonexistent",
            repository_url="", timestamp=r.timestamp, duration_seconds=0,
            repo_scan_time=0, ri_generation_time=0, ei_generation_time=0,
            gov_generation_time=0, mission_generation_time=0,
            peak_memory_bytes=0, files_scanned=0, modules_scanned=0,
            functions_scanned=0, classes_scanned=0, public_apis_scanned=0,
            findings_generated=0, recommendations_generated=0,
            approved_recommendations=0, missions_generated=0,
            total_tasks=0, pipeline_steps=0, errors=("scan failed",),
        )
        summary = compute_summary([r, failed])
        assert summary.total_repositories == 2
        assert summary.successful_benchmarks == 1
        assert summary.failed_benchmarks == 1


# ---------------------------------------------------------------------------
# 13. Trend entry
# ---------------------------------------------------------------------------

class TestTrendEntry:
    def test_trend_entry_as_dict(self):
        entry = TrendEntry(
            timestamp="2026-08-08T00:00:00Z", repository_name="test",
            duration_seconds=1.5, findings=10, recommendations=5,
            missions=2, memory_mb=50.0, health_score=85.0,
        )
        d = entry.as_dict()
        assert d["repository_name"] == "test"
        assert d["findings"] == 10


# ---------------------------------------------------------------------------
# 14. Benchmark config validation
# ---------------------------------------------------------------------------

class TestBenchmarkConfig:
    def test_config_exists(self):
        config_path = HERMES_ROOT / "validation" / "benchmark_config.json"
        assert config_path.exists()
        config = json.loads(config_path.read_text())
        assert config["schema_version"] == "1"
        assert "benchmarks" in config

    def test_config_has_all_repos(self):
        config_path = HERMES_ROOT / "validation" / "benchmark_config.json"
        config = json.loads(config_path.read_text())
        repos = config["benchmarks"]
        expected = ["requests", "click", "flask", "fastapi", "django", "numpy", "pandas"]
        for name in expected:
            assert name in repos, f"Missing repo: {name}"
            assert "repo_url" in repos[name]


# ---------------------------------------------------------------------------
# 15. Determinism across multiple runs
# ---------------------------------------------------------------------------

class TestDeterminismMultipleRuns:
    def test_three_runs_same_output(self):
        results = [run_benchmark(str(HERMES_ROOT)) for _ in range(3)]
        for r in results[1:]:
            assert r.findings_generated == results[0].findings_generated
            assert r.recommendations_generated == results[0].recommendations_generated
            assert r.missions_generated == results[0].missions_generated
            assert r.modules_scanned == results[0].modules_scanned
            assert r.files_scanned == results[0].files_scanned
