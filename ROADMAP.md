# Hermes Runtime Roadmap

## Evidence-Driven Evolution

Hermes evolves only when operational evidence demonstrates a need.

New capabilities require one or more of:

- Repeated pilot failures
- Repeated operator requests
- Benchmark deficiencies
- Measurable performance bottlenecks
- Verified engineering defects

Ideas alone are insufficient.

### Feature Acceptance Policy

Every future feature proposal must include:

1. **Problem Statement** — What is the observed problem?
2. **Observed Evidence** — What data demonstrates the problem?
3. **Repositories Affected** — Which repositories exhibit this problem?
4. **Pilot References** — Which pilots encountered this issue?
5. **Benchmark References** — What benchmark data supports this?
6. **Alternatives Considered** — What other approaches were evaluated?
7. **Why Existing Capabilities Are Insufficient** — Why can't Hermes solve this today?
8. **Expected Benefit** — What measurable improvement is expected?
9. **Success Criteria** — How will we know the fix works?
10. **Rollback Strategy** — How do we revert if the fix causes problems?

If these sections are absent, the proposal should not be accepted.

---

## Operational Roadmap

| Version | Focus |
|---------|-------|
| v1.0.0-beta | External validation |
| v1.0.1 | Bug fixes from pilot users |
| v1.0.2 | Performance improvements |
| v1.1.0 | Features justified by operational evidence |

---

## v1.0.0-beta — External Validation 🔄 IN PROGRESS

- Multi-language scanning (Python + JavaScript/TypeScript) ✅
- Scanner registry with pluggable language scanners ✅
- Language detection and framework identification ✅
- Critical bug fixes (circular recursion, schema mismatches) ✅
- Repository Readiness Assessment (pre-pipeline safety gate) ✅
- Safety module (worktree isolation, diff scope validation) ✅
- **Next:** External validation with real-world JavaScript/TypeScript repositories

## v1.0.1 — Bug Fixes from Pilot Users
- Awaiting operational evidence from external pilots

## v1.0.2 — Performance Improvements
- Awaiting benchmark evidence from real-world usage

## v1.1.0 — Features Justified by Operational Evidence
- Awaiting measured needs from production deployments

---

## Completed Development History

The following milestones have been completed and are preserved for reference.
- Work Queue CLI (`hermes-queue`)
- Supervisor → Queue integration (remediation tasks)
- Evidence → Queue integration (`--task-id --work-queue`)
- Reviewer → Queue integration (`--task-id --work-queue`)
- Runtime State projection includes queue summary
- Runtime Orchestrator (`hermes-runtime --task-id/--next --work-queue`)
- End-to-end validation: full queue lifecycle verified

## Program III v0.7 — Autonomous Runtime ✅ COMPLETE

### v0.7.1 — Retry & Recovery ✅ COMPLETE
- Configurable retry policy (max_retries, retry_delay_seconds, max_retry_delay_seconds, retry_backoff_multiplier, retryable)
- Exponential backoff with cap
- Recoverable vs terminal failures (can_retry logic)
- Manual retry (retry_task)
- Crash recovery (recover_incomplete_tasks)
- Automatic retry scheduling on failure (mark_failed)

### v0.7.2 — Scheduler ✅ COMPLETE
- Delayed execution (scheduled_at, is_due)
- Periodic execution (recurring, interval_seconds, reschedule_recurring)
- Priority scheduling (get_due_tasks, dispatch_next_due)
- Manual scheduling (schedule_task)
- Fairness via priority + task_id ordering

### v0.7.3 — Observability ✅ COMPLETE
- Structured metrics module (metrics.py)
- Metrics CLI (`hermes-metrics`)
- Queue metrics (tasks by state, attempts, retryable counts)
- Runtime metrics (duration stats, throughput, execution history)
- Failure classification (INFRASTRUCTURE, TRANSIENT, DEPENDENCY, VALIDATION)
- Recoverable vs non-recoverable failure detection
- Metrics report output (JSON + Markdown)

### v0.7.4 — Queue Maintenance ✅ COMPLETE
- Queue compaction (compact() archives COMPLETE tasks)
- Archiving completed work to separate file
- Pruning old COMPLETE tasks by age (prune_terminal_tasks)
- State integrity verification (verify_integrity)
- Automatic repair of common issues (repair_common_issues)

### v0.7.5 — Capability Plugins ✅ COMPLETE
- Pluggable task executors (ExecutorPlugin ABC, LocalExecutorPlugin)
- Capability registry with enable/disable, health checks (CapabilityRegistry)
- Capability discovery from plugin directories (PluginDiscovery)
- CapabilityManager ties registry + discovery + executor loading
- `hermes-capabilities` CLI (list, show, discover, enable, disable, check, check-all)
- `hermes-runtime` CLI accepts `--executor` and `--plugin-dirs`
- `run_pipeline` accepts optional executor/capability_manager params
- 15 focused tests (test_capabilities.py)

### v0.7.6 — Resilience Testing ✅ COMPLETE
- 93 chaos/resilience tests across 10 failure domains
- Runtime interruption: interrupted tasks not falsely marked COMPLETE, recoverable
- Queue corruption: invalid JSON fails clearly, unrecoverable corruption not silently rewritten
- Partial writes: canonical file survives failed atomic write, temp files don't replace valid state
- Evidence failures: failing executor not promoted, queue state remains recoverable
- Review failures: REVIEW_FAILED/REVIEW_INCOMPLETE never result in COMPLETE, retry path available
- Health failures: malformed inputs degrade safely, no crash
- Scheduler restart: scheduled work, attempts, retry budgets survive reload
- Capability failure: disabled executor blocked, broken entry_point reports UNHEALTHY
- Compaction/maintenance safety: active tasks never removed, integrity valid after maintenance
- Chaos tests: interrupted running task, restart recovery, corrupted queue, malformed evidence, failed review, partial atomic write, scheduler restart, exhausted retry budget, disabled executor, maintenance during active work, stale persisted state, health degradation
- Defect fixed: CapabilityManager.get_executor now checks registry enabled status before returning cached executors

## Program III v0.8 — Mission Planning ✅ COMPLETE

### v0.8.1 — Mission Schema & Planner
- Mission JSON schema (mission_id, title, description, tasks, goals, constraints, metadata)
- MissionTask dataclass (title, command, dependencies, priority, retry_policy, required_capabilities)
- RetryPolicy integration (inherits defaults from mission-level default_retry_policy)
- MissionPlanner: validate() detects duplicate IDs, unknown deps, cycles, invalid retry policies
- MissionPlanner: build() produces Plan artifact with deterministic task IDs
- Plan dataclass with plan_hash (SHA-256), dependency_graph, valid flag, schema_version
- Capability validation against CapabilityRegistry (checks enabled + available)
- Working directory inheritance (mission → task override)

### v0.8.2 — CLI & Enqueue
- `hermes-plan validate` — validates mission JSON, outputs structured result
- `hermes-plan build` — builds plan artifact, writes to file or stdout
- `hermes-plan show` — displays plan artifact as formatted JSON
- `hermes-plan enqueue` — enqueues validated plan into work queue, outputs summary
- Plan serialization (save_plan / load_plan)
- enqueue_plan: converts PlanTask → WorkItem, respecting dependencies, retry, priority
- Backward-compatible with existing queue state (no breaking changes)
- 85 tests (test_mission.py, test_plan_cli.py)

## Program III v0.9 — Autonomous Mission Execution 🔄 IN PROGRESS

### v0.9.1 — Mission Runner ✅ COMPLETE
- MissionRunner: orchestrates full mission execution (plan → enqueue → execute → report)
- MissionReport: deterministic, machine-readable report after every mission
  - Fields: mission_id, mission_title, mission_type, status, duration, tasks_planned/completed/failed/skipped
  - Evidence records, independent reviews, queue summary, runtime health, metrics summary
  - Warnings, errors, artifacts_produced
- `hermes-mission run <mission.json>` — execute a complete mission end-to-end
- `hermes-mission report <report.json>` — display a saved mission report
- Accepts both mission JSON and plan JSON as input
- Dependency-aware execution: tasks run in topological order
- Deadlock detection: identifies tasks blocked by failed dependencies
- Health and metrics collected automatically after mission completion
- 21 tests (test_mission_runner.py)
- 314 total tests passing

### v0.9.2 — Mission Type Registry ✅ COMPLETE
- MissionType ABC: extensible base class for mission types
  - `get_metadata()`: return MissionTypeMetadata (name, version, description, category, constraints, capabilities)
  - `validate_mission()`: type-specific validation beyond base planner
  - `build_tasks()`: optional automated task generation
  - `get_default_constraints()` / `get_required_capabilities()`: introspection
- MissionTypeRegistry: singleton registry with register/unregister/get/list/discover
  - Entry point discovery via `hermes_v01.mission_types` group
  - Category filtering, sorted listing, idempotent registration
- 7 built-in mission types:
  - `repository-maintenance` (category: maintenance)
  - `dependency-upgrade` (category: maintenance)
  - `documentation-refresh` (category: documentation)
  - `security-audit` (category: security, requires: security-scanner)
  - `performance-audit` (category: performance)
  - `release-preparation` (category: release)
  - `ci-verification` (category: testing)
- Type-specific validation integrated into MissionRunner
- `hermes-mission types` — list available mission types
- `hermes-mission type-show <name>` — display type details
- `hermes-mission run --mission-type <name>` — run with type validation
- MissionReport includes `mission_type` field
- 48 tests (test_mission_types.py)
- 362 total tests passing

### v0.9.3 — Mission Constraint Engine ✅ COMPLETE
- ConstraintEngine: validates missions against a set of constraints before execution
- 7 built-in constraint types:
  - `RequiredCapabilityConstraint`: checks all required capabilities are registered and enabled
  - `RuntimeVersionConstraint`: checks Python runtime version (min/max)
  - `RepositoryConstraint`: checks repository path exists and is accessible
  - `WorkingDirectoryConstraint`: checks working directories exist and are writable
  - `ResourceLimitConstraint`: checks available disk space and memory
  - `ExecutionWindowConstraint`: checks execution time windows, excluded days
  - `DependencyPolicyConstraint`: checks network access, determinism policies
- ConstraintResult: deterministic, machine-readable result per constraint
- `validate_mission_constraints()`: convenience function for mission validation
- `MissionPlanner.build()` accepts `constraint_context` for automatic validation
- `hermes-mission constraints <mission.json>` — validate constraints against a mission
  - `--repository <path>`, `--cwd <path>` for context
  - `--json` for structured output
- Exit code 1 if any constraints are unsatisfied
- 59 tests (test_mission_constraints.py)
- 421 total tests passing

### v0.9.4 — Concurrent Mission Execution ✅ COMPLETE
- WorkQueueManager.dispatch_ready(max_concurrent): batch dispatch up to N READY tasks atomically
- MissionRunner concurrent path: ThreadPoolExecutor-based parallel task execution
  - `max_concurrency` parameter (default 1 = sequential)
  - `--concurrency N` CLI flag on `hermes-mission run`
  - `_queue_lock` (threading.Lock) protects shared counters
  - Dependency-aware: only dispatches tasks whose dependencies are COMPLETE/VERIFIED
  - Failure isolation: failed tasks don't block independent siblings
- MissionReport additions: `max_concurrency`, `peak_concurrent_tasks` fields
- ConcurrentMissionMetrics: parallelism_ratio, sequential_equivalent detection
- Concurrency defects found and fixed during implementation:
  - Re-entrant deadlock: WorkQueueManager._replace_item held Lock while calling _normalize → _normalize_item which also acquired Lock. Fixed: Lock → RLock.
  - Spin-loop starvation: main dispatch loop had no yield when no futures completed, starving pool workers. Fixed: sleep(0.01) when no progress.
  - Retry future-key collision: futures dict keyed by task_id; on retry new future overwrote old. Fixed: key = `{task_id}:{attempts}`.
- 37 concurrency tests (test_concurrent_execution.py)
- 458 total tests passing
- E2E validated: 6-task mission with dependencies, concurrent execution, and failure isolation

### v0.9.5 — Mission Lifecycle Control ✅ COMPLETE
- MissionState dataclass with full lifecycle state machine (READY → RUNNING → PAUSED → COMPLETED/CANCELLED/ABORTED/FAILED)
- MissionStateStore for atomic persistence of lifecycle state
- MissionControlCommand and MissionControlStore for cross-process lifecycle control
- MissionRunner lifecycle methods: pause(), resume(), cancel(), abort(), status()
- File-backed control: CLI writes mission_control.json, runner polls each iteration
- Stale command replay prevention via command_id ordering
- Mission-scoped control: wrong mission_id is rejected
- Terminal state escape prevention: no transitions out of terminal states
- CLI subcommands: status, pause, resume, cancel, abort
- 71 lifecycle tests (test_mission_lifecycle.py)
- 529 total tests passing

### v0.9.6 — Mission Reports ✅ COMPLETE
- Extended MissionReport with lifecycle, evidence, review, health, and concurrency summaries
- MissionReportGenerator builds comprehensive reports from runner state + existing systems
- Markdown renderer generates human-readable reports from the same model as JSON
- Deterministic JSON serialization with stable key ordering
- Atomic report persistence under reports/<mission-id>/MISSION_REPORT.json and .md
- CLI: hermes-mission generate-report <mission-id>
- 64 report tests (test_mission_report.py)
- MISSION_REPORT_SCHEMA.md documentation
- 593 total tests passing

## Quality Standard
Every milestone must improve: Correctness, Reliability, Maintainability, Observability, Documentation, Test Coverage.

## Program III v1.0 — Alpha Hardening 🔄 IN PROGRESS

### v1.0.0-alpha — Release Readiness
- Version alignment: pyproject.toml, __init__.py both at `1.0.0a0`
- LICENSE file added (MIT)
- pyproject.toml metadata: authors, classifiers, license
- Code quality: removed unused imports, extracted shared `atomic_write_json`
- Decoupled fragile import: `reviewer.py` → `utils.py` for `sha256_file`
- README.md genericized (no hardcoded user paths)
- Stale egg-info cleaned up
- 593 tests passing

### v1.0.0-alpha — Real-World Validation & Dogfooding ✅ COMPLETE
- Dogfooding framework: DOGFOODING.md, examples/missions/, validation/sample-repo/
- 5 representative mission definitions (repo-maintenance, doc-refresh, ci-verify, dep-review, release-readiness)
- 3 end-to-end missions executed against validation/sample-repo
- 8 friction findings documented in DOGFOOD_FINDINGS.md
- All failures attributable to target repository (not Hermes defects)
- Evidence, reviews, and mission reports verified
- 593 tests still passing

## Candidate v1.1 Improvements (from dogfooding evidence)

1. **Per-mission queue isolation** — prevent task ID collision between missions (DF-002)
2. **Prerequisite task support** — install dependencies before dependent tasks (DF-001)
3. **Mission vs execution status separation** — distinguish infrastructure health from task outcomes (DF-003)
4. **Python version compatibility validation** — check command compatibility with min Python (DF-005)
5. **Built-in task helpers** — common operations without inline Python (DF-004)
6. **Per-task environment control** — env vars and working directory overrides (DF-006)

## Repository Intelligence v0.1 ✅ COMPLETE

- Static repository analysis subsystem
- AST-based module discovery, import extraction, class/function extraction
- Test discovery with target inference
- Dependency extraction from pyproject.toml and requirements.txt
- Module graph with cycle detection, isolated/highly-connected module identification
- Public API inventory (classes, functions, CLI entry points)
- Complexity signals (large modules, complex functions, deep nesting)
- Technical debt signals (no docstrings, no tests, import cycles, isolated modules)
- `hermes-repo` CLI: scan, show, check, summary
- Deterministic JSON output (identical scans produce byte-identical artifacts)
- REPOSITORY_INTELLIGENCE_SCHEMA.md documentation
- 68 tests covering scanner, analyzer, renderer, CLI, determinism, and Hermes self-scan
- 661 total tests passing

## Engineering Intelligence v1.0 ✅ COMPLETE

- Evidence-based engineering recommendation layer
- Consumes Repository Intelligence JSON — never scans independently
- 15 finding categories: Architecture, Coupling, Complexity, Documentation, Testing, Packaging, Configuration, Dependencies, CLI, Public API, Performance, Maintainability, Observability, Security Signals, Technical Debt
- 10 frozen dataclasses: Finding, Recommendation, CandidateMission, RiskAssessment, PriorityScore, ConfidenceScore, AffectedComponent, EvidenceReference, EngineeringSummary, EngineeringIntelligence
- Priority scoring model: `0.40*impact + 0.20*(confidence*10) + 0.25*severity + 0.15*scope`
- Health score: 100.0 minus capped deductions per severity level
- Risk assessment: low/moderate/high/critical with evidence-backed reasoning
- Mission recommendation engine: groups findings into 8 mission types
- `hermes-engineering` CLI: scan, show, summary, findings, missions
- Deterministic JSON output (byte-identical for same RI input)
- ENGINEERING_INTELLIGENCE_SCHEMA.md with scoring formulas and limitations
- 57 tests covering models, findings, recommendations, missions, rendering, CLI, malformed input, Hermes self-analysis
- 718 total tests passing

## Engineering Governance v1.0 ✅ COMPLETE

- Validates engineering recommendations before mission planning
- Consumes Engineering Intelligence JSON — never scans independently
- Evidence quality evaluation: low/medium/high based on reference count, diversity, consistency
- Architecture impact assessment: local/package/system
- Duplicate detection: text normalization with identical/overlapping classification
- Conflict detection: keyword pattern matching for contradictory recommendations
- 5 decision types: APPROVED, APPROVED_WITH_NOTES, NEEDS_MORE_EVIDENCE, DEFERRED, REJECTED
- Every decision includes rationale and conditions
- ApprovedCandidateMission generated for approved recommendations only
- `hermes-governance` CLI: scan, show, summary, approved, rejected
- Deterministic JSON output
- ENGINEERING_GOVERNANCE_SCHEMA.md documentation
- 31 tests covering decisions, duplicates, conflicts, evidence, architecture, rendering, CLI, Hermes self-governance
- 749 total tests passing

## Mission Recommendation Integration v1.0 ✅ COMPLETE

- Governance-approved recommendations → draft Hermes Mission artifacts
- DraftMission supports DRAFT/APPROVED/REJECTED states with explicit transitions
- approve()/reject() methods with timestamp and operator tracking
- Only APPROVED missions accepted by MissionPlanner
- DRAFT and REJECTED missions rejected by planner validation
- Traceability preserved through planning: governance, engineering, repository intelligence
- `hermes-recommend` CLI: generate, show, summary, export, approve, reject, status
- DraftMission → Mission translation preserves tasks, constraints, capabilities
- 31 tests covering generation, schema, traceability, determinism, CLI, pipeline dogfood
- 780 total tests passing

## Mission Recommendation → Planner Integration v1.0 ✅ COMPLETE

- Approval workflow for generated draft missions
- DraftMission extended with approve()/reject() state transitions
- DRAFT → APPROVED and DRAFT → REJECTED only (no reset without explicit policy)
- Duplicate approval is idempotent-safe (rejected)
- `hermes-recommend approve/reject/status` CLI commands with persistence
- MissionPlanner.validate_recommendation() rejects DRAFT and REJECTED recommendation artifacts
- APPROVED DraftMission translated to Mission via draft_mission_translator
- Traceability preserved through full pipeline: RI → EI → Gov → Rec → Plan
- `hermes-recommend generate → approve → hermes-plan build` validated end-to-end
- All missions remain DRAFT by default — never auto-approved or auto-enqueued
- 44 tests covering approve, reject, status, idempotency, planner rejection, traceability, CLI, backward compat
- 824 total tests passing

## Validation & Benchmark Program v1.1 ✅ COMPLETE

- Benchmark engine for measuring pipeline performance
- 7 golden repositories (requests, click, flask, fastapi, django, numpy, pandas)
- `hermes-benchmark` CLI: run, compare, summary, trend, report, confidence
- Snapshot persistence for longitudinal analysis
- Evidence-based engineering confidence scoring
- Drift detection between snapshots
- Determinism verification across multiple runs
- Hermes self-benchmarking validated
- `BENCHMARKING.md` and `VALIDATION_GUIDE.md` documentation
- 32 tests covering calculations, comparison, trend, golden validation, determinism, CLI, confidence, persistence
- 856 total tests passing

## Beta Readiness Sprint v1.1.1 ✅ COMPLETE

- Fixed files_scanned=0 bug in repo scanner
- Fixed governance confidence: unique recommendations per finding
- Governance approval rate improved from 0.19% to 62%
- 7 golden repositories benchmarked successfully
- Confidence: RI=100%, EI=100%, Overall=72.75%
- False positive analysis completed
- Performance profile generated
- 24 beta readiness tests added
- 880 total tests passing
- Beta decision: READY WITH KNOWN LIMITATIONS