# Changelog

All notable changes to the Hermes Runtime are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/).

## [1.0.0-alpha] - 2026-08-08

### Added
- `LICENSE` file (MIT)
- `ENGINEERING_SCORE.md` — objective quality measurements
- `ARCHITECTURE_SNAPSHOT.md` — module structure and data flow
- `DOGFOODING.md` — real-world validation framework
- `DOGFOOD_FINDINGS.md` — 8 friction findings from dogfooding
- `examples/missions/` — 5 representative mission definitions
- `validation/sample-repo/` — isolated test repository for dogfooding
- **Repository Intelligence v0.1** — static repository analysis subsystem
  - `hermes_v01/repo_intel_models.py` — 17 frozen dataclasses (ModuleInfo, ClassInfo, FunctionInfo, ImportInfo, ModuleGraph, PublicAPI, TestIntelligence, DependencyIntelligence, ArchitectureSummary, ComplexitySignal, DebtSignal, etc.)
  - `hermes_v01/repo_scanner.py` — AST-based static scanner: module discovery, import extraction, class/function extraction with signatures, test discovery with target inference, pyproject.toml + requirements.txt dependency parsing, configuration file discovery, CLI entry point extraction
  - `hermes_v01/repo_analyzer.py` — analysis engine: module graph with cycle detection, public API inventory, complexity signals, technical debt signals, architecture summary
  - `hermes_v01/repo_renderer.py` — JSON and Markdown artifact rendering
  - `hermes_v01/repo_cli.py` — `hermes-repo` CLI with scan/show/check/summary subcommands
  - `REPOSITORY_INTELLIGENCE_SCHEMA.md` — complete schema documentation
  - 68 tests (`test_repo_intelligence.py`) — scanner, analyzer, renderer, CLI, determinism, dogfooding
  - 661 total tests passing
- **Engineering Intelligence v1.0** — evidence-based engineering recommendations
  - `hermes_v01/engineering_intel_models.py` — 10 frozen dataclasses (Finding, Recommendation, CandidateMission, RiskAssessment, PriorityScore, ConfidenceScore, AffectedComponent, EvidenceReference, EngineeringSummary, EngineeringIntelligence)
  - `hermes_v01/engineering_analyzer.py` — analysis engine: 15 finding categories, recommendation engine, mission grouping, priority scoring, risk assessment, health score
  - `hermes_v01/engineering_renderer.py` — JSON and Markdown artifact rendering
  - `hermes_v01/engineering_cli.py` — `hermes-engineering` CLI with scan/show/summary/findings/missions subcommands
  - `ENGINEERING_INTELLIGENCE_SCHEMA.md` — complete schema documentation with scoring formulas
  - 57 tests (`test_engineering_intelligence.py`) — models, findings, recommendations, missions, severity, confidence, evidence, rendering, CLI, malformed input, Hermes self-analysis
  - 718 total tests passing
- **Engineering Governance v1.0** — recommendation validation before mission planning
  - `hermes_v01/governance_intel_models.py` — 8 frozen dataclasses (GovernanceAssessment, RecommendationAssessment, ApprovalDecision, Conflict, DuplicateRecommendation, EvidenceQuality, ArchitectureImpact, ApprovalSummary)
  - `hermes_v01/governance_analyzer.py` — evidence quality evaluation, duplicate detection, conflict detection, architecture impact assessment, approval decisions
  - `hermes_v01/governance_renderer.py` — JSON and Markdown artifact rendering
  - `hermes_v01/governance_cli.py` — `hermes-governance` CLI with scan/show/summary/approved/rejected subcommands
  - `ENGINEERING_GOVERNANCE_SCHEMA.md` — complete schema documentation
  - 31 tests (`test_engineering_governance.py`) — decisions, duplicates, conflicts, evidence, architecture, rendering, CLI, Hermes self-governance
  - 749 total tests passing
- **Mission Recommendation Integration v1.0** — governance-approved recommendations → draft missions
  - `hermes_v01/mission_recommendation_models.py` — DraftMission, GeneratedTask, TraceabilityLink, MissionRecommendations
  - `hermes_v01/mission_generator.py` — ApprovedCandidateMission → Hermes Mission conversion with task templates
  - `hermes_v01/mission_recommendation_renderer.py` — JSON, Markdown, and per-mission export
  - `hermes_v01/mission_recommendation_cli.py` — `hermes-recommend` CLI with generate/show/summary/export
  - Full traceability: every mission links back to governance, engineering, and repository intelligence
  - All missions in DRAFT state — never enqueued automatically
  - 31 tests (`test_mission_recommendations.py`) — generation, schema, traceability, determinism, CLI, pipeline dogfood
  - 780 total tests passing
- **Mission Recommendation → Planner Integration v1.0** — approval workflow + planner consumption
  - `hermes_v01/mission_recommendation_models.py` — extended DraftMission with DRAFT/APPROVED/REJECTED states, approve()/reject() transitions
  - `hermes_v01/draft_mission_translator.py` — APPROVED DraftMission → Mission translation with traceability preservation
  - `hermes_v01/mission_recommendation_cli.py` — extended with approve/reject/status commands
  - `hermes_v01/mission.py` — MissionPlanner.validate_recommendation() rejects DRAFT/REJECTED recommendation artifacts
  - Only APPROVED missions accepted by planner; DRAFT and REJECTED rejected
  - Traceability preserved: governance, engineering, repository intelligence sources
  - All missions remain in DRAFT state by default — never auto-approved or auto-enqueued
  - 44 tests (`test_planner_integration.py`) — approve, reject, status, duplicate idempotency, planner rejection, traceability, CLI, backward compatibility
  - 824 total tests passing
- **Validation & Benchmark Program v1.1** — engineering confidence and validation
  - `hermes_v01/benchmark_engine.py` — BenchmarkResult, BenchmarkComparison, BenchmarkSummary, TrendEntry, EngineeringConfidence, Snapshot models
  - `hermes_v01/benchmark_cli.py` — `hermes-benchmark` CLI with run/compare/summary/trend/report/confidence
  - `validation/` — directory structure for golden repositories, snapshots, benchmarks
  - `validation/benchmark_config.json` — 7 golden repositories (requests, click, flask, fastapi, django, numpy, pandas)
  - `validation/golden_repositories/hermes-runtime.json` — Hermes self-validation dataset
  - `validation/clone_golden_repos.sh` — script to clone golden repositories
  - Snapshot persistence and longitudinal trend analysis
  - Evidence-based engineering confidence scoring
  - Determinism verification across multiple runs
  - Drift detection between snapshots
  - 32 tests (`test_benchmark.py`) — calculations, comparison, trend, golden validation, determinism, CLI, confidence, persistence
  - 856 total tests passing
  - `BENCHMARKING.md` — benchmarking guide
  - `VALIDATION_GUIDE.md` — validation guide

### Changed
- Version bumped to `1.0.0a0` (PEP 440 alpha) across `pyproject.toml` and `__init__.py`
- `pyproject.toml` now includes authors, classifiers, and license metadata
- `reviewer.py` imports `sha256_file` from `utils` instead of `evidence` (decoupled module dependency)
- Removed stale `hermes_runtime_v01.egg-info` directory
- Removed unused imports: `hashlib`, `os`, `stat`, `tempfile` from `reviewer.py`; `Any` from `health.py`; `tempfile` from `plan_cli.py`
- `atomic_write_json()` extracted to `utils.py` as shared utility

### Fixed
- Version mismatch between `pyproject.toml` (0.9.5) and `__init__.py` (0.9.6) — both now `1.0.0a0`
- README.md genericized: removed hardcoded `/Users/david/EVOS` paths

## [0.9.6] - 2026-08-08

### Added
- Extended `MissionReport` with lifecycle, evidence, review, health, and concurrency summary fields
- `MissionReportGenerator` builds comprehensive reports from runner state + existing health/metrics systems
- `render_markdown()` produces human-readable Markdown from the same model as JSON
- Deterministic JSON serialization with stable key ordering (`sort_keys=True`)
- Atomic report persistence under `reports/<mission-id>/MISSION_REPORT.json` and `.md`
- `hermes-mission generate-report <mission-id>` CLI subcommand
- `MISSION_REPORT_SCHEMA.md` schema documentation
- 64 report tests (`test_mission_report.py`)

### Changed
- `MissionReport.as_dict()` now includes v0.9.6 fields when set (backward compatible)
- `MissionRunner.run()` automatically generates and persists JSON + Markdown report artifacts
- Reports include `lifecycle_state`, `tasks_cancelled`, `tasks_aborted` fields
- Reports include `evidence_summary`, `independent_review_summary`, `health_summary` aggregates

## [0.9.5] - 2026-08-08

### Added
- `MissionState` dataclass with full lifecycle state machine: READY → RUNNING → PAUSED → COMPLETED/CANCELLED/ABORTED/FAILED
- `MissionStateStore` for atomic persistence of mission lifecycle state
- `MissionControlCommand` and `MissionControlStore` for atomic cross-process lifecycle control
- `MissionRunner` lifecycle methods: `pause()`, `resume()`, `cancel()`, `abort()`, `status()`
- File-backed lifecycle control: CLI writes `mission_control.json`, runner polls and applies
- Stale command replay prevention via `command_id > last_control_command_id` check
- Mission-scoped control: commands rejected if `mission_id` does not match active mission
- Terminal state escape prevention: no transitions from COMPLETED/CANCELLED/ABORTED/FAILED
- CLI subcommands: `hermes-mission status`, `pause`, `resume`, `cancel`, `abort`
- 71 lifecycle tests covering state model, persistence, control store, and runner integration

### Changed
- `MissionRunner.run()` now persists mission state at start and end of execution
- Sequential and concurrent execution loops check lifecycle events each iteration
- `MissionReport.status` now also reflects CANCELLED and ABORTED states

## [0.9.4] - 2026-08-07

### Added
- `WorkQueueManager.dispatch_ready(max_concurrent)` for batch dispatch of up to N READY tasks
- `MissionRunner` concurrent execution path via `ThreadPoolExecutor`
- `--concurrency N` CLI flag on `hermes-mission run`
- `MissionReport.max_concurrency` and `peak_concurrent_tasks` fields
- `ConcurrentMissionMetrics` dataclass and `compute_concurrent_mission_metrics()`
- 37 concurrency tests (`test_concurrent_execution.py`)

### Fixed
- Re-entrant deadlock: `WorkQueueManager` now uses `RLock` to allow nested acquisitions during state normalization
- Spin-loop starvation: dispatch loop yields when no futures complete, preventing pool worker starvation
- Retry future-key collision: futures dict uses `{task_id}:{attempts}` keys to prevent overwrite on retry

## [0.9.3] - 2026-08-07

### Added
- `ConstraintEngine` with 7 built-in constraint types
- `RequiredCapabilityConstraint`, `RuntimeVersionConstraint`, `RepositoryConstraint`
- `WorkingDirectoryConstraint`, `ResourceLimitConstraint`, `ExecutionWindowConstraint`
- `DependencyPolicyConstraint`
- `validate_mission_constraints()` convenience function
- `hermes-mission constraints <mission.json>` CLI subcommand
- 59 constraint tests (`test_mission_constraints.py`)

## [0.9.2] - 2026-08-07

### Added
- `MissionType` abstract base class for extensible mission types
- `MissionTypeRegistry` singleton with entry point discovery
- 7 built-in mission types: repository-maintenance, dependency-upgrade, documentation-refresh, security-audit, performance-audit, release-preparation, ci-verification
- `hermes-mission types` and `hermes-mission type-show <name>` CLI subcommands
- 48 mission type tests (`test_mission_types.py`)

## [0.9.1] - 2026-08-06

### Added
- `MissionRunner` for orchestrating full mission execution
- `MissionReport` deterministic, machine-readable report
- `hermes-mission run <mission.json>` and `hermes-mission report <report.json>` CLI
- Dependency-aware execution with deadlock detection
- 21 mission runner tests (`test_mission_runner.py`)

## [0.8] - 2026-08-05

### Added
- Mission JSON schema and `MissionPlanner`
- `hermes-plan validate`, `hermes-plan build`, `hermes-plan show`, `hermes-plan enqueue` CLI
- Plan serialization, enqueue, and backward-compatible queue integration
- 85 mission and plan tests

## [0.7] - 2026-08-04

### Added
- Retry and recovery (v0.7.1), scheduler (v0.7.2), observability (v0.7.3)
- Queue maintenance (v0.7.4), capability plugins (v0.7.5), resilience testing (v0.7.6)
- 93 chaos/resilience tests across 10 failure domains

## [0.6] - 2026-08-03

### Added
- Work Queue CLI (`hermes-queue`), supervisor-queue integration
- Evidence/recorder queue integration, reviewer queue integration
- Runtime state projection with queue summary
- Runtime orchestrator (`hermes-runtime`)
