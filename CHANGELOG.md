# Changelog

All notable changes to the Hermes Runtime are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/).

## [1.3.0] - 2026-08-11

### Operational Validation Trial 001 — COMPLETED

Seven-day operational validation trial completed. Hermes Enterprise is now in controlled beta.

**Trial Summary:**
- 7-day validation across 3 repositories (hermes-runtime, flask, express)
- 84 findings generated, 65 unique findings reviewed
- 5 USEFUL, 23 NOT_ACTIONABLE, 36 NEEDS_MORE_EVIDENCE, 1 DUPLICATE
- Governance over-approval: 81.5%–100% (production) → 0.0% (candidate Variant I)
- Safety violations: 0
- Target mutations: 0
- 1325 tests passing

**Key Findings:**
- Production Governance defaults to APPROVED when no rule matches (unsafe)
- Candidate Variant I (default → NEEDS_MORE_EVIDENCE) eliminates over-approval
- USEFUL recall weakly validated (only 1 USEFUL finding in Day 7)
- CONFIGURATION governance unvalidated (0 findings)
- Mission traceability incomplete (0% linkage)

**Decisions:**
- Enterprise: READY_WITH_KNOWN_LIMITATIONS
- Governance: MORE_GOVERNANCE_VALIDATION_REQUIRED
- Production Governance: UNCHANGED
- Recommended Mode: CONTROLLED_BETA with mandatory human review

**Artifacts:**
- OPERATIONAL_VALIDATION_REPORT.md — full trial report
- CONTROLLED_BETA_GUIDE.md — operator workflow guide
- validation/snapshots/day7_final_closure.json — trial completion event

### Added
- **Evidence-Based Finding Adjudication** — first-class capability for human review
  - `FindingAdjudication` model — append-only, immutable adjudication records
  - `MissionFindingLink` model — explicit finding→mission traceability (PRIMARY, SUPPORTING, MERGED_FROM)
  - File context classification (PRODUCTION, TEST, FIXTURE, GENERATED, VENDOR, CONFIGURATION, DOCUMENTATION)
  - Observation/concern/actionability 3-level distinction
  - Threshold exceedance ratio and tier classification (NEAR_THRESHOLD, MODERATE, HIGH, EXTREME)
  - Test-file policy: production thresholds do not auto-apply to test context
  - Configuration requirement validation: must establish expected config before flagging absence
- **Human Review Queue Service** — `enterprise/services/review_service.py`
  - Queue construction with file context, exceedance, observation/concern/actionability
  - Append-only adjudication persistence
  - Review summary with finding precision, actionability rate
  - Mission↔Finding explicit linkage (idempotent, many-to-one)
  - Journal event emission (finding.reviewed, finding.reclassified)
- **Enterprise API** — `/api/review/*` endpoints
  - `GET /api/review/findings` — review queue with filters (repository, severity, category, reviewed)
  - `GET /api/review/findings/{id}` — finding detail with adjudications
  - `POST /api/review/findings/{id}/adjudications` — create classification (append-only)
  - `GET /api/review/summary` — aggregate review metrics
  - `GET /api/review/export` — full review data export
- **Enterprise UI** — Human Review page (`/review`)
  - Summary cards (Pending, Useful, FP, Not Actionable, Needs Evidence, Duplicate, Precision, Actionability)
  - Filterable findings table with file context, observation/concern/actionability status
  - Side panel with full finding detail and one-click classification buttons
  - Re-review support with old adjudications preserved
- **CLI** — `hermes-human-review`
  - `hermes-human-review list` — list findings with filters
  - `hermes-human-review show FINDING-ID` — full finding detail
  - `hermes-human-review classify FINDING-ID CLASSIFICATION` — classify from CLI
  - `hermes-human-review summary` — review metrics
  - `hermes-human-review export` — export review data
- **Journal Integration** — append-only events
  - `finding.reviewed` — operator classified a finding
  - `finding.reclassified` — operator changed previous classification
- **30 Day 2R Operator Classifications** — persisted to database
  - USEFUL: 4, NOT_ACTIONABLE: 12, NEEDS_MORE_EVIDENCE: 13, DUPLICATE: 1
  - Finding Precision: 13.8%, Actionability Rate: 13.3%
- **Human Review Report** — `HUMAN_REVIEW_REPORT_DAY2R.md`
- **41 focused tests** — file context, threshold, actionability, linkage, journal, Day 2R persistence

### Fixed
- Mission uniqueness constraint changed from global `unique=True` to per-repository `UniqueConstraint("mission_id", "repository_id")` (DEF-001)
- Frontend STAGE_ORDER updated to match 9 canonical pipeline stages

## [1.2.0] - 2026-08-10

### Added
- **7-Day Operational Validation Program** — infrastructure for evidence-driven daily operations
  - `POST /api/trial` — create and manage operational trials
  - `GET /api/trial/{id}` — get trial status
  - `POST /api/trial/{id}/complete` / `abort` — trial lifecycle
  - `POST /api/trial/{id}/snapshots/{date}` — create immutable daily snapshots
  - `GET /api/trial/{id}/snapshots` — list trial snapshots
  - `GET /api/trial/{id}/dashboard` — 7-day trial dashboard
- **Operator Feedback** — classify findings during trial
  - `POST /api/feedback` — submit feedback (USEFUL, FALSE_POSITIVE, NOT_ACTIONABLE, NEEDS_MORE_EVIDENCE, DUPLICATE, UNKNOWN)
  - `GET /api/feedback` — list feedback with trial/finding filters
- **Friction Journal** — record operational friction
  - `POST /api/friction` — record friction (category, severity, description, workaround)
  - `GET /api/friction` — list friction with category/severity filters
- **Trust Metrics** — evidence-based trust indicators
  - Finding Precision, Operator Acceptance Rate, Scan Reliability, Retry Recovery Rate
  - Safety Violation Count, Journal Integrity Failure Count
  - `GET /api/operations/trust-metrics`
- **Daily Morning Brief** — extended overnight summary
  - Time-of-day greeting, scan/findings/governance/friction metrics
  - Recommended review order, repositories requiring attention
  - `GET /api/operations/morning-brief`
- **Daily Operational Metrics** — per-day aggregation
  - `GET /api/operations/daily-metrics/{date}`
  - Repository operations, engineering intelligence, governance, quality, performance
- **Final Report Generator** — OPERATIONAL_VALIDATION_REPORT.md generation
  - `GET /api/trial/{id}/report` (via service)
  - Executive summary, cohort, reliability, findings, governance, friction, safety
- **Feature Proposals** — evidence-based feature acceptance
  - `POST /api/proposals` — propose feature with problem, evidence, frequency
  - `POST /api/proposals/{id}/decide` — ACCEPT, DEFER, REJECT, NEEDS_MORE_EVIDENCE
  - `GET /api/proposals` — list proposals with decision filter
- **Scheduling** — read-only repository analysis scheduling
  - `GET /api/scheduling/repositories` — list schedulable repositories
  - `POST /api/scheduling/validate` — validate schedule with safety check
- **Safety Boundary** — enforcement of read-only trial mode
  - Forbidden: modify_source_code, create_branch, commit, push, create_pull_request, merge, modify_github_settings, modify_workflows, execute_mission
  - `enterprise/services/safety.py` — check_safety_boundary(), enforce_read_only()
- **5 new database models**: OperationalTrial, DailySnapshot, OperatorFeedback, FrictionRecord, FeatureProposal
- **41 focused tests** covering trial lifecycle, snapshots, feedback, friction, trust, morning brief, dashboard, proposals, scheduling, safety, report generation, schema validation

## [1.1.0] - 2026-08-10

### Added
- **Scan Lifecycle Control** — full scan management with cancel and retry
  - `POST /api/scans/{id}/cancel` — cancel queued or running scans (idempotent)
  - `POST /api/scans/{id}/retry` — retry failed/cancelled scans with lineage tracking
  - Scan attempt counting with `attempt` and `previous_scan_id` fields
  - Cancellation timestamps: `cancellation_requested_at`, `cancelled_at`
  - Failure classification: `auth_error`, `not_found`, `rate_limit`, `timeout`, `network_error`, `unknown`
  - `requested_by` tracking for user-initiated actions
  - Engineering Journal events emitted for `scan.cancelled`, `scan.completed`, `scan.failed`, `scan.retried`
- **Scan Model Hardening** — extended ScanJob with operational metadata
  - `attempt` — scan retry attempt number
  - `previous_scan_id` — links retry to original scan
  - `requested_by` — user who initiated the scan
  - `cancellation_requested_at` / `cancelled_at` — cancellation timing
  - `failure_classification` — structured error categorization
  - `stage_timings` — per-stage timing with started_at, completed_at, duration_seconds
  - Migration `003_scan_hardening` for backward-compatible schema evolution
- **Pipeline Timings** — per-stage performance tracking
  - 6 stages tracked: metadata, repository_analysis, engineering_analysis, governance_analysis, journal_sync, finding_generation
  - Duration in seconds for each stage
  - Total scan duration persisted
  - Timing exposed in `GET /api/scans/{id}` and `GET /api/scans/{id}/history`
- **Dashboard Activity API** — aggregated operational metrics
  - `GET /api/dashboard/activity-v2?since=<timestamp>` — real-time dashboard metrics
  - `repositories_total`, `repositories_ready`, `repositories_blocked`
  - `scans_queued`, `scans_running`, `scans_completed_since`, `scans_failed_since`
  - `new_findings_since`, `governance_approved_since`, `governance_rejected_since`
  - `draft_missions_since`, `ci_failures_since`
  - `latest_activity` — recent journal events
  - `average_repository_health`
- **Overnight Summary API** — daily operational summary
  - `GET /api/dashboard/overnight?window_start=<ts>&window_end=<ts>`
  - `repositories_scanned`, `blocked_repositories`
  - `successful_scans`, `failed_scans`
  - `new_findings`, `resolved_findings`
  - `governance_decisions`, `draft_missions`, `ci_failures`
  - `top_repositories_requiring_attention` — repos with recent failures or blocked status
  - Natural language `summary` text
- **Frontend Dashboard** — real Command Center landing page
  - Time-of-day greeting with user name
  - 11 metric cards: repositories, ready, blocked, queued scans, running scans, completed, failed, new findings, approved recs, draft missions, avg health
  - Overnight summary section with scan and activity metrics
  - Recent activity feed from journal events
- **Repository List UI** — card-based repository view
  - Repository cards with name, provider, visibility, branch, commit SHA
  - Health score and findings count badges
  - Last sync and scan timestamps
  - Open, Sync, Scan action buttons
  - Click-through to repository detail
- **Repository Detail UI** — tabbed repository view
  - Overview tab: provider, visibility, branch, commit, health, findings, sync/scan timestamps
  - Scans tab: scan job list with timeline detail view
  - Findings tab: severity-filtered finding list
  - Scan timeline visualization: metadata → repository_analysis → engineering_analysis → governance_analysis → journal_sync → finding_generation
- **Scan Actions UI** — scan management from browser
  - Cancel button for pending/running scans with confirmation
  - Retry button for failed/cancelled scans
  - Optimistic UI updates after actions
  - Error display for rejected operations
- **Live Status** — scan progress without page reload
  - Scan list shows current stage, attempt, duration
  - Scan detail timeline shows per-stage progress
  - Status badges with color coding
- **Error Handling** — structured error responses
  - GitHub permission denied: "GitHub sync failed"
  - Repository unavailable: "Repository not found"
  - Scan failed: failure classification in response
  - Cancel/retry rejected: specific error messages
  - Auth expired: 401 with clear message
- **Testing** — 77 enterprise backend tests (34 new)
  - Scan create, start, cancel, retry lifecycle
  - Cancel idempotency
  - Cancel of completed scan (no-op)
  - Retry lineage tracking
  - Attempt counting
  - Stage timings validation
  - Scan history recording
  - Journal event emission for cancel/retry
  - Dashboard activity aggregation
  - Overnight summary generation
  - Malformed timestamp handling
  - Auth boundary verification
- **Alembic Migrations** — 002_scan_jobs, 003_scan_hardening

### Changed
- Repository model: added `provider`, `identifier`, `commit_sha`, `visibility`, `last_synced_at`
- ScanJob model: added `attempt`, `previous_scan_id`, `requested_by`, `cancellation_requested_at`, `cancelled_at`, `failure_classification`, `stage_timings`
- Repository router: added `provider` filter, auto-identifier detection on create, `POST /{repo_id}/sync`
- Dashboard router: added `activity-v2` and `overnight` endpoints
- Frontend: updated Repository type with new fields, added ScanJob and ScanHistory types

## [1.0.0-beta] - 2026-08-09

### Added
- **Engineering Command Center v1.0** — first web application for Hermes Enterprise
  - FastAPI backend with SQLAlchemy ORM and SQLite/PostgreSQL support
  - JWT authentication with bcrypt password hashing
  - Repository Registry — CRUD operations for repository management
  - Dashboard API — aggregated stats (repositories, findings, missions, health, journal activity)
  - Journal API — query and filter engineering journal events
  - Findings API — query findings by severity, category, status
  - Missions API — query mission queue by status and type
  - Reports API — query mission execution reports
  - React + TypeScript frontend with Vite
  - Dashboard view with stats cards and recent activity feed
  - Repositories view with health scores and status badges
  - Journal view with event type filtering
  - Findings view with severity filtering
  - Missions view with status filtering
  - Reports view with task completion details
  - Alembic migration infrastructure with initial schema
  - 43 comprehensive backend tests covering auth, CRUD, filtering, and integration
- **Engineering Journal v1.0** — append-only observability for the entire pipeline
  - `JournalEvent` frozen dataclass with content-addressed integrity (SHA-256 payload hash)
  - `JournalStore` with append-only JSONL persistence, file locking, and immutable writes
  - `JournalEmitter` with 26 stage-specific emit helpers covering all pipeline stages
  - `OvernightSummary` generator with deterministic aggregation and Markdown rendering
  - `hermes-journal` CLI: `record`, `list`, `show`, `summary`, `integrity`, `types`, `export`
  - 26 event types across 10 pipeline stages: readiness, repository intelligence, engineering intelligence, governance, mission recommendation, mission planning, mission execution, evidence, review, health, GitHub
  - Concurrent-safe append with `fcntl.flock` locking
  - Deterministic event ordering by timestamp
  - Content integrity verification via SHA-256 payload hashing
  - Daily JSONL file storage with atomic writes
  - 98 comprehensive tests covering model, storage, emitter, summary, CLI, and integration
- **Repository Readiness Assessment** — mandatory pre-pipeline safety gate
  - `RepositoryReadiness` canonical model with 20+ fields
  - `assess_readiness()` function for version control, working tree, baseline integrity, analysis confidence, and mission safety checks
  - `assert_ready()` pipeline guard that raises `ReadinessBlocked` when execution is not allowed
  - `hermes-ready` CLI command with JSON and Markdown output
  - Protected untracked file tracking to prevent worktree contamination
- **Operational maturity** — roadmap transition from feature-driven to evidence-driven development
  - Evidence-Driven Evolution policy documented in ROADMAP.md and ENGINEERING_MANIFEST.md
  - Feature Acceptance Policy requiring problem statement, evidence, and rollback strategy
  - Operational roadmap: v1.0.0-beta → v1.0.1 (bug fixes) → v1.0.2 (performance) → v1.1.0 (evidence-justified features)
  - Worktree recommendation when user work is present
- **Safety module** — worktree isolation and diff scope validation
  - `check_worktree_isolation()` detects unauthorized file contamination
  - `check_diff_scope()` validates commit diff matches declared mission scope
  - New file detection, insertion limits, scope boundary enforcement
- **Multi-language scanning** — JavaScript and TypeScript support via `JavaScriptScanner`
  - `.js`, `.jsx`, `.mjs`, `.cjs`, `.ts`, `.tsx` file extensions
  - `package.json` and `tsconfig.json` manifest detection
  - React component detection (function components, hooks, memo, forwardRef)
  - Import/export parsing (ESM and CommonJS)
  - Dependency extraction from `package.json`
  - Configuration file detection (eslint, prettier, vite, webpack, etc.)
  - Complexity signals (large modules, high hook concentration, API concentration)
  - Debt signals (hardcoded credentials, missing tests, large components)
- **Scanner registry** — `ScannerRegistry` abstraction for pluggable language scanners
  - `RepositoryScanner` ABC with `detect()` and `scan()` interface
  - Auto-detection of repository languages
  - Multi-scanner result merging
- **Language detector** — `detect_languages()` and `detect_project_type()` functions
  - File extension mapping for 13 languages
  - Framework detection (React, Vue, Angular, Svelte, Next, Nuxt, Express, Fastify, Django, Flask, FastAPI)
  - Confidence scoring based on file counts and manifest presence

### Fixed
- **Critical: PythonScanner.scan() circular recursion** — `PythonScanner.scan()` called `scan_repository()`, which called `registry.scan()`, which called `PythonScanner.scan()` again, creating infinite recursion. The `scanner_registry.scan()` caught the resulting `RecursionError` silently (via broad `except Exception: continue`), causing 0 modules to be returned. Fixed by having `PythonScanner.scan()` call internal scanning functions directly.
- **Analyzer schema mismatch** — `repo_analyzer.py` assumed all modules have `path` key, but JavaScript scanner produces modules with `file_path` key. Added normalization in `analyze_repository()` to handle both formats.
- **Import key mismatch** — `repo_analyzer.py` assumed all imports have `module` key, but JavaScript scanner produces imports with `source` key. Updated `_build_module_graph()` and `_raw_to_module()` to handle both formats.
- **ComplexitySignal/DebtSignal field mismatch** — Scanner-produced signals used `file` and `evidence` keys, but the analyzer passed `file_path` and `description` to model constructors. Fixed to use correct field names (`target`, `message`, `evidence`).
- **JS scanner validation exclusion** — JavaScript scanner did not exclude `validation/` directory, causing it to scan golden repository files. Added exclusion to match Python scanner behavior.
- **Test data merging** — `ScannerRegistry.scan()` did not merge `test_modules`, `modules_with_tests`, or `modules_without_tests` fields from Python scanner, causing `KeyError` in tests expecting these fields.
- **DependencyInfo field mismatch** — `repo_analyzer.py` passed `version` and `type` kwargs to `DependencyInfo`, but the model uses `version_spec` and `category`. Fixed to use correct field names.
- **Missing Path import** — `repo_analyzer.py` used `Path` without importing it from `pathlib`. Added the import.
- **Custom hook detection** — `js_scanner.py` had `hook_name[3:0].isupper()` (empty slice) instead of `hook_name[3].isupper()`. Fixed to correctly detect custom hooks.
- **Export default detection** — `js_scanner.py` did not detect `export default identifier` on its own line. Added pattern for standalone default exports.
- **Scanner registry JS/TS field merging** — `ScannerRegistry.scan()` did not merge `components`, `hooks`, `routes`, or `fetch_calls` from JavaScript scanner. Added these fields to the merge logic.
- **test_check_stale cleanup** — Test left ephemeral files behind if assertion failed before cleanup. Added `try/finally` block.
- **test_module_has_package** — Test asserted all modules have `package` key, but root-level modules don't. Fixed to only check modules in subdirectories.

### Changed
- Version bumped to `1.0.0b0` (PEP 440 beta) across `pyproject.toml` and `__init__.py`
- Development Status classifier updated from `3 - Alpha` to `4 - Beta`
- `pyproject.toml` now includes `py.typed` marker

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
- **Beta Readiness Sprint v1.1.1** — validation fixes and engineering confidence
  - Fixed `files_scanned=0` bug in repo scanner (added `file_count` to scan output)
  - Fixed governance confidence: unique recommendations per finding (appended finding ID)
  - Fixed governance threshold: lowered evidence quality gate from 0.6 to 0.4
  - Governance approval rate improved from 0.19% to 62%
  - Added `validation/` directory exclusion to scanner
  - Capped mission generation at 50 for performance
  - 7 golden repositories benchmarked (requests, click, flask, fastapi, django, numpy, pandas)
  - Confidence scores: RI=100%, EI=100%, Gov=13.26%, Rec=72.17%, Overall=72.75%
  - `BETA_READINESS.md` — beta readiness report
  - `FALSE_POSITIVE_ANALYSIS.md` — false positive analysis
  - `PERFORMANCE_PROFILE.md` — performance profile
  - 24 tests (`test_beta_readiness.py`) — files_scanned, uniqueness, governance, confidence, golden validation, performance, determinism
  - 880 total tests passing

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
