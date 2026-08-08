"""Benchmark engine — measures and compares Hermes pipeline performance.

Provides deterministic benchmarking against repositories with snapshot
comparison, trend analysis, and engineering confidence scoring.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .repo_scanner import scan_repository
from .repo_analyzer import analyze_repository
from .engineering_analyzer import analyze_engineering
from .governance_analyzer import govern_engineering
from .mission_generator import generate_missions
from .mission_recommendation_renderer import save_artifacts


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BenchmarkResult:
    """Result of benchmarking a single repository."""

    repository_name: str
    repository_path: str
    repository_url: str
    timestamp: str
    duration_seconds: float
    repo_scan_time: float
    ri_generation_time: float
    ei_generation_time: float
    gov_generation_time: float
    mission_generation_time: float
    peak_memory_bytes: int
    files_scanned: int
    modules_scanned: int
    functions_scanned: int
    classes_scanned: int
    public_apis_scanned: int
    findings_generated: int
    recommendations_generated: int
    approved_recommendations: int
    missions_generated: int
    total_tasks: int
    pipeline_steps: int
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "repository_name": self.repository_name,
            "repository_path": self.repository_path,
            "repository_url": self.repository_url,
            "timestamp": self.timestamp,
            "duration_seconds": round(self.duration_seconds, 4),
            "timing": {
                "repo_scan_seconds": round(self.repo_scan_time, 4),
                "ri_generation_seconds": round(self.ri_generation_time, 4),
                "ei_generation_seconds": round(self.ei_generation_time, 4),
                "gov_generation_seconds": round(self.gov_generation_time, 4),
                "mission_generation_seconds": round(self.mission_generation_time, 4),
                "total_pipeline_seconds": round(self.duration_seconds, 4),
            },
            "memory": {
                "peak_bytes": self.peak_memory_bytes,
                "peak_mb": round(self.peak_memory_bytes / (1024 * 1024), 2),
            },
            "repository_metrics": {
                "files_scanned": self.files_scanned,
                "modules_scanned": self.modules_scanned,
                "functions_scanned": self.functions_scanned,
                "classes_scanned": self.classes_scanned,
                "public_apis_scanned": self.public_apis_scanned,
            },
            "pipeline_output": {
                "findings_generated": self.findings_generated,
                "recommendations_generated": self.recommendations_generated,
                "approved_recommendations": self.approved_recommendations,
                "missions_generated": self.missions_generated,
                "total_tasks": self.total_tasks,
                "pipeline_steps": self.pipeline_steps,
            },
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class BenchmarkComparison:
    """Comparison between two benchmark results."""

    baseline_name: str
    current_name: str
    baseline_timestamp: str
    current_timestamp: str
    duration_change_pct: float
    findings_change: int
    recommendations_change: int
    missions_change: int
    memory_change_pct: float
    regressions: tuple[str, ...] = ()
    improvements: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "baseline": {"name": self.baseline_name, "timestamp": self.baseline_timestamp},
            "current": {"name": self.current_name, "timestamp": self.current_timestamp},
            "changes": {
                "duration_change_pct": round(self.duration_change_pct, 2),
                "findings_change": self.findings_change,
                "recommendations_change": self.recommendations_change,
                "missions_change": self.missions_change,
                "memory_change_pct": round(self.memory_change_pct, 2),
            },
            "regressions": list(self.regressions),
            "improvements": list(self.improvements),
        }


@dataclass(frozen=True)
class BenchmarkSummary:
    """Summary across multiple benchmark results."""

    total_repositories: int
    successful_benchmarks: int
    failed_benchmarks: int
    avg_duration_seconds: float
    avg_findings: float
    avg_recommendations: float
    avg_missions: float
    avg_memory_mb: float
    total_findings: int
    total_recommendations: int
    total_missions: int
    determinism_rate: float
    timestamp: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_repositories": self.total_repositories,
            "successful_benchmarks": self.successful_benchmarks,
            "failed_benchmarks": self.failed_benchmarks,
            "averages": {
                "duration_seconds": round(self.avg_duration_seconds, 4),
                "findings": round(self.avg_findings, 1),
                "recommendations": round(self.avg_recommendations, 1),
                "missions": round(self.avg_missions, 1),
                "memory_mb": round(self.avg_memory_mb, 2),
            },
            "totals": {
                "findings": self.total_findings,
                "recommendations": self.total_recommendations,
                "missions": self.total_missions,
            },
            "determinism_rate": round(self.determinism_rate, 4),
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class TrendEntry:
    """A single trend data point."""

    timestamp: str
    repository_name: str
    duration_seconds: float
    findings: int
    recommendations: int
    missions: int
    memory_mb: float
    health_score: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "repository_name": self.repository_name,
            "duration_seconds": round(self.duration_seconds, 4),
            "findings": self.findings,
            "recommendations": self.recommendations,
            "missions": self.missions,
            "memory_mb": round(self.memory_mb, 2),
            "health_score": round(self.health_score, 2),
        }


@dataclass(frozen=True)
class EngineeringConfidence:
    """Evidence-based confidence scores for the pipeline."""

    confidence_repo_intel: float
    confidence_eng_intel: float
    confidence_governance: float
    confidence_recommendations: float
    confidence_overall: float
    evidence_sources: tuple[str, ...] = ()
    calculation_method: str = "evidence_based"
    timestamp: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "confidence_scores": {
                "repository_intelligence": round(self.confidence_repo_intel, 4),
                "engineering_intelligence": round(self.confidence_eng_intel, 4),
                "governance": round(self.confidence_governance, 4),
                "recommendations": round(self.confidence_recommendations, 4),
                "overall": round(self.confidence_overall, 4),
            },
            "evidence_sources": list(self.evidence_sources),
            "calculation_method": self.calculation_method,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class Snapshot:
    """A saved benchmark snapshot for longitudinal analysis."""

    snapshot_id: str
    timestamp: str
    repository_name: str
    result: BenchmarkResult
    findings_summary: dict[str, Any]
    missions_summary: dict[str, Any]
    engineering_health: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp,
            "repository_name": self.repository_name,
            "result": self.result.as_dict(),
            "findings_summary": self.findings_summary,
            "missions_summary": self.missions_summary,
            "engineering_health": round(self.engineering_health, 2),
        }


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

def _get_peak_memory() -> int:
    """Get current process peak memory usage."""
    import resource
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return usage.ru_maxrss * 1024  # Convert to bytes on macOS


def run_benchmark(repo_path: str, repository_url: str = "") -> BenchmarkResult:
    """Run the full Hermes pipeline against a repository and measure performance."""
    repo = Path(repo_path).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []

    start_time = time.time()
    t0 = time.time()

    # Step 1: Repository scan
    try:
        scan = scan_repository(repo)
    except Exception as e:
        errors.append(f"Repository scan failed: {e}")
        scan = {"repository": {"name": repo.name, "path": str(repo)}, "modules": [], "test_files": [], "dependencies": {}}
    t1 = time.time()
    repo_scan_time = t1 - t0

    # Step 2: Repository Intelligence
    try:
        ri = analyze_repository(scan)
        ri_json = json.loads(json.dumps(ri.as_dict(), sort_keys=True))
    except Exception as e:
        errors.append(f"RI generation failed: {e}")
        ri_json = {"repository": {"name": repo.name, "path": str(repo)}, "modules": [], "public_api": {"classes": [], "functions": [], "cli_entry_points": []}, "module_graph": {"modules": [], "edges": []}, "complexity_signals": [], "debt_signals": [], "architecture_summary": {"total_modules": 0, "total_classes": 0, "total_functions": 0, "total_lines_of_code": 0, "average_module_size": 0, "largest_module": None, "isolated_modules": [], "highly_connected_modules": [], "cycle_count": 0, "health_score": 0.0}}
    t2 = time.time()
    ri_generation_time = t2 - t1

    # Step 3: Engineering Intelligence
    try:
        ei = analyze_engineering(ri_json)
        ei_json = json.loads(json.dumps(ei.as_dict(), sort_keys=True))
    except Exception as e:
        errors.append(f"EI generation failed: {e}")
        ei_json = {"repository": {"name": repo.name}, "findings": [], "recommendations": [], "candidate_missions": [], "engineering_summary": {"total_findings": 0, "total_recommendations": 0, "total_candidate_missions": 0, "health_score": 0.0}}
    t3 = time.time()
    ei_generation_time = t3 - t2

    # Step 4: Engineering Governance
    try:
        gov = govern_engineering(ei_json)
        gov_json = json.loads(json.dumps(gov.as_dict(), sort_keys=True))
    except Exception as e:
        errors.append(f"Governance failed: {e}")
        gov_json = {"repository": {"name": repo.name}, "assessment": {"approved_missions": [], "summary": {"total_evaluated": 0, "approved": 0}}}
    t4 = time.time()
    gov_generation_time = t4 - t3

    # Step 5: Mission Recommendation
    try:
        recs = generate_missions(gov_json)
    except Exception as e:
        errors.append(f"Mission generation failed: {e}")
        from .mission_recommendation_models import MissionRecommendations, MissionRecommendationSummary
        recs = MissionRecommendations(repository={"name": repo.name}, summary=MissionRecommendationSummary(
            total_governance_approvals=0, missions_generated=0, missions_by_type={}, total_tasks=0, traceability_validated=False))
    t5 = time.time()
    mission_generation_time = t5 - t4

    total_time = t5 - start_time

    # Extract metrics
    ri_data = ri_json
    ei_data = ei_json
    gov_data = gov_json

    modules = ri_data.get("modules", [])
    public_api = ri_data.get("public_api", {})
    findings = ei_data.get("findings", [])
    recommendations = ei_data.get("recommendations", [])
    candidate_missions = ei_data.get("candidate_missions", [])
    approved_missions = gov_data.get("assessment", {}).get("approved_missions", [])

    files_scanned = scan.get("repository", {}).get("file_count", 0)
    functions = sum(len(m.get("functions", [])) for m in modules)
    classes = sum(len(m.get("classes", [])) for m in modules)

    return BenchmarkResult(
        repository_name=repo.name,
        repository_path=str(repo),
        repository_url=repository_url,
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        duration_seconds=total_time,
        repo_scan_time=repo_scan_time,
        ri_generation_time=ri_generation_time,
        ei_generation_time=ei_generation_time,
        gov_generation_time=gov_generation_time,
        mission_generation_time=mission_generation_time,
        peak_memory_bytes=_get_peak_memory(),
        files_scanned=files_scanned,
        modules_scanned=len(modules),
        functions_scanned=functions,
        classes_scanned=classes,
        public_apis_scanned=len(public_api.get("classes", [])) + len(public_api.get("functions", [])),
        findings_generated=len(findings),
        recommendations_generated=len(recommendations),
        approved_recommendations=len(approved_missions),
        missions_generated=recs.summary.missions_generated,
        total_tasks=recs.summary.total_tasks,
        pipeline_steps=5,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def compare_benchmarks(baseline: BenchmarkResult, current: BenchmarkResult) -> BenchmarkComparison:
    """Compare two benchmark results, identifying regressions and improvements."""
    regressions: list[str] = []
    improvements: list[str] = []

    duration_pct = 0.0
    if baseline.duration_seconds > 0:
        duration_pct = ((current.duration_seconds - baseline.duration_seconds) / baseline.duration_seconds) * 100
        if duration_pct > 10:
            regressions.append(f"Pipeline duration increased {duration_pct:.1f}%")
        elif duration_pct < -10:
            improvements.append(f"Pipeline duration decreased {abs(duration_pct):.1f}%")

    memory_pct = 0.0
    if baseline.peak_memory_bytes > 0:
        memory_pct = ((current.peak_memory_bytes - baseline.peak_memory_bytes) / baseline.peak_memory_bytes) * 100
        if memory_pct > 20:
            regressions.append(f"Peak memory increased {memory_pct:.1f}%")
        elif memory_pct < -20:
            improvements.append(f"Peak memory decreased {abs(memory_pct):.1f}%")

    findings_change = current.findings_generated - baseline.findings_generated
    recs_change = current.recommendations_generated - baseline.recommendations_generated
    missions_change = current.missions_generated - baseline.missions_generated

    if findings_change < -5:
        regressions.append(f"Findings decreased by {abs(findings_change)}")
    elif findings_change > 5:
        improvements.append(f"Findings increased by {findings_change}")

    return BenchmarkComparison(
        baseline_name=baseline.repository_name,
        current_name=current.repository_name,
        baseline_timestamp=baseline.timestamp,
        current_timestamp=current.timestamp,
        duration_change_pct=round(duration_pct, 2),
        findings_change=findings_change,
        recommendations_change=recs_change,
        missions_change=missions_change,
        memory_change_pct=round(memory_pct, 2),
        regressions=tuple(regressions),
        improvements=tuple(improvements),
    )


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def compute_summary(results: list[BenchmarkResult]) -> BenchmarkSummary:
    """Compute summary statistics across multiple benchmark results."""
    successful = [r for r in results if not r.errors]
    failed = [r for r in results if r.errors]

    if not successful:
        return BenchmarkSummary(
            total_repositories=len(results), successful_benchmarks=0,
            failed_benchmarks=len(failed), avg_duration_seconds=0,
            avg_findings=0, avg_recommendations=0, avg_missions=0,
            avg_memory_mb=0, total_findings=0, total_recommendations=0,
            total_missions=0, determinism_rate=0.0,
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )

    n = len(successful)
    total_findings = sum(r.findings_generated for r in successful)
    total_recs = sum(r.recommendations_generated for r in successful)
    total_missions = sum(r.missions_generated for r in successful)
    total_memory = sum(r.peak_memory_bytes for r in successful)

    # Determinism: compare duplicate runs
    determinism_rate = 1.0
    if len(successful) >= 2:
        durations = [r.duration_seconds for r in successful]
        avg_dur = sum(durations) / len(durations)
        if avg_dur > 0:
            variance = sum((d - avg_dur) ** 2 for d in durations) / len(durations)
            cv = (variance ** 0.5) / avg_dur
            determinism_rate = max(0.0, 1.0 - cv)

    return BenchmarkSummary(
        total_repositories=len(results),
        successful_benchmarks=n,
        failed_benchmarks=len(failed),
        avg_duration_seconds=sum(r.duration_seconds for r in successful) / n,
        avg_findings=total_findings / n,
        avg_recommendations=total_recs / n,
        avg_missions=total_missions / n,
        avg_memory_mb=total_memory / n / (1024 * 1024),
        total_findings=total_findings,
        total_recommendations=total_recs,
        total_missions=total_missions,
        determinism_rate=determinism_rate,
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )


# ---------------------------------------------------------------------------
# Trend
# ---------------------------------------------------------------------------

def compute_trend(snapshots: list[Snapshot]) -> list[TrendEntry]:
    """Compute trend data from snapshots."""
    entries: list[TrendEntry] = []
    for s in sorted(snapshots, key=lambda x: x.timestamp):
        entries.append(TrendEntry(
            timestamp=s.timestamp,
            repository_name=s.repository_name,
            duration_seconds=s.result.duration_seconds,
            findings=s.result.findings_generated,
            recommendations=s.result.recommendations_generated,
            missions=s.result.missions_generated,
            memory_mb=s.result.peak_memory_bytes / (1024 * 1024),
            health_score=s.engineering_health,
        ))
    return entries


def detect_changes(baseline: Snapshot, current: Snapshot) -> dict[str, Any]:
    """Detect what changed between two snapshots."""
    changes: dict[str, Any] = {}
    if baseline.findings_summary.get("total", 0) != current.findings_summary.get("total", 0):
        changes["findings_changed"] = True
        changes["new_findings"] = current.findings_summary.get("total", 0) - baseline.findings_summary.get("total", 0)
    if baseline.missions_summary.get("total", 0) != current.missions_summary.get("total", 0):
        changes["missions_changed"] = True
        changes["new_missions"] = current.missions_summary.get("total", 0) - baseline.missions_summary.get("total", 0)
    health_delta = current.engineering_health - baseline.engineering_health
    if abs(health_delta) > 0.5:
        changes["health_changed"] = True
        changes["health_delta"] = round(health_delta, 2)
    changes["repository_changed"] = len(changes) > 0
    return changes


# ---------------------------------------------------------------------------
# Engineering confidence
# ---------------------------------------------------------------------------

def compute_confidence(results: list[BenchmarkResult], snapshots: list[Snapshot] | None = None) -> EngineeringConfidence:
    """Compute evidence-based engineering confidence scores.

    Formulas:
    - RI confidence: min(1.0, modules_scanned / max(files_scanned, 1))
      Measures coverage of Python files by the scanner.
    - EI confidence: min(1.0, findings_per_module / 3.0)
      Measures finding density. 3+ findings per module = high confidence.
    - Governance confidence: approved / max(total_recs, 1)
      Measures approval rate after deduplication.
    - Recommendation confidence: min(1.0, missions / max(approved, 1))
      Measures conversion of approved recommendations to missions.
    - Overall: 0.25*RI + 0.30*EI + 0.25*Gov + 0.20*Rec
    """
    evidence: list[str] = []

    if not results:
        return EngineeringConfidence(
            confidence_repo_intel=0.0, confidence_eng_intel=0.0,
            confidence_governance=0.0, confidence_recommendations=0.0,
            confidence_overall=0.0, evidence_sources=(), timestamp="",
        )

    successful = [r for r in results if not r.errors]
    n = len(successful)

    # RI confidence: modules discovered as fraction of files scanned
    total_modules = sum(r.modules_scanned for r in successful)
    total_files = sum(r.files_scanned for r in successful)
    ri_confidence = min(1.0, total_modules / max(total_files, 1)) if total_files > 0 else 0.0
    evidence.append(f"RI: {total_modules} modules / {total_files} files = {ri_confidence:.2%}")

    # EI confidence: findings per module (3+ = high confidence)
    total_findings = sum(r.findings_generated for r in successful)
    findings_per_module = total_findings / max(total_modules, 1)
    ei_confidence = min(1.0, findings_per_module / 3.0)
    evidence.append(f"EI: {total_findings} findings / {total_modules} modules = {findings_per_module:.1f}/mod, confidence={ei_confidence:.2%}")

    # Governance confidence: approval rate
    total_recs = sum(r.recommendations_generated for r in successful)
    total_approved = sum(r.approved_recommendations for r in successful)
    gov_confidence = total_approved / max(total_recs, 1) if total_recs > 0 else 0.0
    evidence.append(f"Gov: {total_approved} approved / {total_recs} recommendations = {gov_confidence:.2%}")

    # Recommendation confidence: missions per approval
    total_missions = sum(r.missions_generated for r in successful)
    rec_confidence = min(1.0, total_missions / max(total_approved, 1)) if total_approved > 0 else 0.0
    evidence.append(f"Rec: {total_missions} missions / {total_approved} approved = {rec_confidence:.2%}")

    # Overall: weighted average
    overall = (0.25 * ri_confidence + 0.30 * ei_confidence + 0.25 * gov_confidence + 0.20 * rec_confidence)
    evidence.append(f"Overall: {overall:.2%}")

    # Determinism evidence
    if len(successful) >= 2:
        durations = [r.duration_seconds for r in successful]
        avg = sum(durations) / len(durations)
        variance = sum((d - avg) ** 2 for d in durations) / len(durations)
        cv = (variance ** 0.5) / avg if avg > 0 else 0
        evidence.append(f"Determinism CV: {cv:.4f}")

    return EngineeringConfidence(
        confidence_repo_intel=ri_confidence,
        confidence_eng_intel=ei_confidence,
        confidence_governance=gov_confidence,
        confidence_recommendations=rec_confidence,
        confidence_overall=overall,
        evidence_sources=tuple(evidence),
        calculation_method="evidence_based",
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )


# ---------------------------------------------------------------------------
# Snapshot persistence
# ---------------------------------------------------------------------------

def save_snapshot(snapshot: Snapshot, snapshots_dir: Path) -> Path:
    """Save a snapshot to disk."""
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    path = snapshots_dir / f"{snapshot.snapshot_id}.json"
    path.write_text(json.dumps(snapshot.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_snapshots(snapshots_dir: Path) -> list[Snapshot]:
    """Load all snapshots from a directory."""
    if not snapshots_dir.exists():
        return []
    snapshots: list[Snapshot] = []
    for p in sorted(snapshots_dir.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        result_data = data["result"]
        result = BenchmarkResult(
            repository_name=result_data["repository_name"],
            repository_path=result_data["repository_path"],
            repository_url=result_data.get("repository_url", ""),
            timestamp=result_data["timestamp"],
            duration_seconds=result_data["duration_seconds"],
            repo_scan_time=result_data["timing"]["repo_scan_seconds"],
            ri_generation_time=result_data["timing"]["ri_generation_seconds"],
            ei_generation_time=result_data["timing"]["ei_generation_seconds"],
            gov_generation_time=result_data["timing"]["gov_generation_seconds"],
            mission_generation_time=result_data["timing"]["mission_generation_seconds"],
            peak_memory_bytes=result_data["memory"]["peak_bytes"],
            files_scanned=result_data["repository_metrics"]["files_scanned"],
            modules_scanned=result_data["repository_metrics"]["modules_scanned"],
            functions_scanned=result_data["repository_metrics"]["functions_scanned"],
            classes_scanned=result_data["repository_metrics"]["classes_scanned"],
            public_apis_scanned=result_data["repository_metrics"]["public_apis_scanned"],
            findings_generated=result_data["pipeline_output"]["findings_generated"],
            recommendations_generated=result_data["pipeline_output"]["recommendations_generated"],
            approved_recommendations=result_data["pipeline_output"]["approved_recommendations"],
            missions_generated=result_data["pipeline_output"]["missions_generated"],
            total_tasks=result_data["pipeline_output"]["total_tasks"],
            pipeline_steps=result_data["pipeline_output"]["pipeline_steps"],
            errors=tuple(result_data.get("errors", [])),
            warnings=tuple(result_data.get("warnings", [])),
        )
        snapshots.append(Snapshot(
            snapshot_id=data["snapshot_id"],
            timestamp=data["timestamp"],
            repository_name=data["repository_name"],
            result=result,
            findings_summary=data.get("findings_summary", {}),
            missions_summary=data.get("missions_summary", {}),
            engineering_health=data.get("engineering_health", 0.0),
        ))
    return snapshots
