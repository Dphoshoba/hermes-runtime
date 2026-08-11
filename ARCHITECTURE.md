# Hermes Runtime Architecture

## Overview

Hermes Runtime is an autonomous engineering runtime that executes missions through a pipeline of evidence collection, independent review, and health monitoring. It is designed for deterministic, restart-safe operation with full audit trails.

## Module Structure

```
hermes_v01/
  __init__.py          # Package version
  __main__.py          # Read-only repository inspection (hermes-validate)
  utils.py             # Shared utilities (sha256, format_utc, fsync)

  # Safety & Readiness
  readiness.py         # Repository Readiness Assessment (pre-pipeline gate)
  readiness_cli.py     # hermes-ready CLI (JSON + Markdown output)
  safety.py            # Worktree isolation, diff scope validation

  # Core Pipeline
  evidence.py          # Immutable evidence recording and integrity
  reviewer.py          # Independent review of execution records
  health.py            # Runtime health monitoring
  runtime.py           # Pipeline orchestrator (record -> review -> health)
  runtime_state.py     # Projected runtime state from supervisor

  # Mission System
  mission.py           # Mission schema, planner, plan serialization
  mission_runner.py    # Mission execution orchestration (sequential + concurrent)
  mission_types.py     # Extensible mission type registry
  mission_constraints.py # Pre-execution constraint validation
  mission_state.py     # Mission lifecycle state machine and persistence
  mission_control.py   # Cross-process lifecycle control (mission_control.json)
  mission_report.py    # Mission report generation, Markdown rendering, persistence

  # Mission Recommendation Integration
  mission_recommendation_models.py  # DraftMission, GeneratedTask, TraceabilityLink
  mission_generator.py             # ApprovedCandidateMission → DraftMission
  mission_prioritizer.py           # Evidence-based priority scoring and selection (v1.0.0)
  draft_mission_translator.py      # APPROVED DraftMission → Mission translation
  mission_recommendation_cli.py    # hermes-recommend CLI (generate/approve/reject/status)
  mission_recommendation_renderer.py # JSON, Markdown, per-mission export

  # Benchmark & Validation
  benchmark_engine.py             # BenchmarkResult, snapshots, trends, confidence
  benchmark_cli.py                # hermes-benchmark CLI (run/compare/summary/trend/report/confidence)

  # Queue & Scheduling
  work_queue.py        # Deterministic, restart-safe work queue
  supervisor.py        # Autonomous execution supervisor

  # Capabilities & Metrics
  capabilities.py      # Pluggable executor system
  metrics.py           # Runtime and queue metrics

  # Multi-Language Scanning
  scanner_registry.py  # ScannerRegistry, RepositoryScanner ABC
  python_scanner.py    # Python language scanner
  js_scanner.py        # JavaScript/TypeScript language scanner
  language_detector.py # Language and framework detection

  # Repository Intelligence
  repo_scanner.py      # Static repository scanner (orchestrates language scanners)
  repo_analyzer.py     # Repository analysis engine
  repo_intel_models.py # Repository intelligence data models
  repo_renderer.py     # JSON/Markdown rendering

  # Engineering Intelligence
  engineering_analyzer.py    # Engineering analysis engine
  engineering_intel_models.py # Engineering intelligence data models
  engineering_renderer.py    # JSON/Markdown rendering

  # Engineering Governance
  governance_analyzer.py     # Recommendation validation
  governance_intel_models.py # Governance data models
  governance_renderer.py     # JSON/Markdown rendering

  # Engineering Journal
  journal_models.py          # JournalEvent canonical model
  journal_store.py           # Append-only JSONL persistence
  journal_emitter.py         # Stage-specific event emitters
  journal_summary.py         # Overnight summary generator
  journal_cli.py             # hermes-journal CLI

  # CLI Entry Points
  *_cli.py             # CLI handlers for each subsystem
```

## Data Flow

```
Mission JSON
    |
    v
MissionPlanner.validate() -> Plan
    |
    v
enqueue_plan() -> WorkQueueManager
    |
    v
MissionRunner.run()
    |
    +-- Sequential: dispatch_ready(1) -> run_pipeline() -> result -> next
    |
    +-- Concurrent: dispatch_ready(N) -> ThreadPoolExecutor -> collect results
    |
    v
MissionReport
```

## Pipeline Execution

Each task goes through `run_pipeline()`:

```
RUNNING -> hermes-record (evidence) -> OBSERVED
       -> hermes-review (review) -> VERIFICATION_PENDING -> VERIFIED
       -> hermes-health (health check)
       -> COMPLETE (success) or FAILED (error)
```

## Concurrency Model

- `max_concurrency=1`: Sequential execution (default)
- `max_concurrency>1`: ThreadPoolExecutor with dependency-aware dispatch
- `WorkQueueManager.dispatch_ready(max_concurrent)`: Atomically dispatches up to N READY tasks
- `WorkQueueManager` uses `threading.RLock` for safe concurrent state mutations
- Failed tasks do not block independent siblings
- Each future is keyed by `{task_id}:{attempts}` to prevent collision on retry

## Persistence

All state is persisted atomically via `AtomicJsonStateStore` pattern:
- `mkstemp` -> write -> flush -> fsync -> `os.replace`
- State files: queue.json, supervisor-state.json, runtime-state.json, mission_state.json, mission_control.json

## Mission Lifecycle

Missions follow a state machine with persistent state:

```
READY → RUNNING → COMPLETED
                 → FAILED
                 → PAUSED → RUNNING (resume)
                         → CANCELLED (terminal)
                         → ABORTED (terminal)
                 → CANCELLED (terminal)
                 → ABORTED (terminal)
```

### State Machine Rules
- **Terminal states** (COMPLETED, CANCELLED, ABORTED, FAILED): no outgoing transitions
- **PAUSE**: stops dispatch, lets running tasks finish, resumes on `resume()`
- **CANCEL**: permanent stop of future dispatch, running tasks finish, terminal state
- **ABORT**: immediate stop, cancel pending futures, terminal state

### Cross-Process Control
- `mission_control.json`: CLI writes lifecycle commands atomically
- `mission_state.json`: Runner writes authoritative observed state
- Command ID ordering prevents stale replay: `command_id > last_control_command_id`
- Mission-scoped: commands rejected if `mission_id` does not match
- Runner polls control file each iteration (configurable interval)

### Persistence Files
- `mission_state.json`: Authoritative lifecycle state (state, counts, timestamps)
- `mission_control.json`: Requested lifecycle action (action, reason, command_id)

## Mission Reports

Reports are first-class, durable artifacts generated from a single canonical model:

```
MissionReport (dataclass)
├── as_dict() → deterministic JSON
├── render_markdown() → human-readable Markdown
└── save_report_atomically() → write + fsync + os.replace
```

### Report Generation
- `MissionReportGenerator` builds comprehensive reports from base report + MissionState
- Consumes existing health, evidence, and review systems (no parallel calculations)
- Reports include: lifecycle state, task counts, evidence/review summaries, health, concurrency, capability usage

### Persistence
- Reports stored under `reports/<mission-id>/MISSION_REPORT.json` and `.md`
- JSON is authoritative; Markdown is derived from the same model
- Atomic writes prevent corruption
- Reports are not overwritten unless regenerated with logical equivalence

### Determinism
- JSON keys sorted alphabetically (`sort_keys=True`)
- Optional fields only included when non-default
- Same persisted outcome → same logical report

## Mission Recommendation Integration

### Approval Boundary

Generated missions are inert until explicitly approved by a human operator.

```
Governance-approved recommendations
    |
    v
hermes-recommend generate → DraftMission (state=DRAFT)
    |
    v
Human reviews mission
    |
    +-- hermes-recommend approve → state=APPROVED (persisted)
    |                              → DraftMission → Mission translation
    |                              → MissionPlanner.validate_recommendation()
    |                              → MissionPlanner.build() → Plan
    |
    +-- hermes-recommend reject  → state=REJECTED (persisted)
                                   → Mission cannot enter planner
```

### State Transitions

- DRAFT → APPROVED: `approve(by=operator)`
- DRAFT → REJECTED: `reject(reason=string)`
- No transition from APPROVED or REJECTED (state is terminal)
- Duplicate approval/rejection is rejected with error

### Traceability Preservation

Every approved mission retains references to its origin:
- `traceability.governance_finding_id` — governance decision reference
- `traceability.engineering_finding_id` — engineering finding reference
- `traceability.repository_intelligence_source` — repository module/component
- `governance_approval_reference` — governance approval record
- `originating_finding_id` — originating engineering finding
- `originating_recommendation` — original recommendation text

### Planner Validation

`MissionPlanner.validate_recommendation()` checks:
- Mission must have `recommendation_generated` metadata
- Mission must have `traceability` in metadata
- Mission must have `governance_approval_reference`
- Mission state must not be DRAFT or REJECTED

### What the System Does NOT Do

- Never auto-approves missions
- Never auto-enqueues missions
- Never auto-executes missions
- Never bypasses human approval
- Never allows REJECTED missions to be re-approved (without explicit policy)

## Benchmark & Validation

### Benchmark Engine

The benchmark engine measures Hermes pipeline performance against real-world repositories:

```
hermes-benchmark run → BenchmarkResult
                    → Snapshot (persisted)
                    → TrendEntry (longitudinal)
                    → EngineeringConfidence (evidence-based)
```

### Metrics Collected

- **Timing**: per-stage pipeline duration
- **Memory**: peak RSS during execution
- **Repository**: files, modules, functions, classes discovered
- **Pipeline**: findings, recommendations, approvals, missions generated

### Confidence Scoring

Confidence derives from measurable evidence:
- Module-to-file coverage ratio (Repo Intel)
- Findings per module density (Eng Intel)
- Governance approval rate
- Mission generation rate
- Determinism coefficient of variation

### Snapshot Storage

Snapshots stored in `validation/snapshots/` as JSON. Supports:
- Longitudinal trend analysis
- Regression detection
- Drift detection between repository versions

## Evidence Integrity

- Evidence records are immutable (read-only after publication)
- SHA-256 digests verify content integrity
- `fsync` ensures durability on write
- `os.link` prevents partial writes (atomic rename)

## Engineering Journal

The Engineering Journal is an append-only event log that provides complete observability across all pipeline stages without modifying existing behavior.

### Architecture

```
Pipeline Stages
      │
      ▼
┌─────────────────┐
│ JournalEmitter   │  26 stage-specific emit helpers
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ JournalStore     │  Append-only JSONL + in-memory index
│ (fcntl.flock)    │  Concurrent-safe, content-addressed
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Daily JSONL      │  YYYY-MM-DD.jsonl (one line per event)
│ Files            │  Atomic writes via mkstemp → fsync → os.replace
└─────────────────┘
```

### Event Model

```python
@dataclass(frozen=True)
class JournalEvent:
    event_id: str           # SHA-256(content)[:16]
    timestamp: str          # ISO 8601 UTC
    event_type: str         # e.g. "readiness.assessed"
    stage: str              # Derived from event_type
    repository: str | None  # Repository identifier
    actor: str              # "system", "cli", or user identity
    payload: dict           # Stage-specific data
    payload_sha256: str     # Content hash for integrity
    metadata: dict          # Optional trace/correlation IDs
```

### Event Types (26)

| Stage | Event Types |
|-------|-------------|
| readiness | `readiness.assessed`, `readiness.blocked` |
| repository_intelligence | `repo.scanned`, `repo.analyzed` |
| engineering_intelligence | `engineering.analyzed` |
| governance | `governance.decided` |
| mission_recommendation | `recommendation.generated`, `recommendation.approved`, `recommendation.rejected` |
| mission_planning | `mission.created`, `mission.planned` |
| mission_execution | `mission.started`, `mission.completed`, `mission.failed`, `mission.cancelled`, `mission.aborted`, `mission.paused`, `mission.resumed` |
| evidence | `evidence.recorded` |
| review | `review.completed` |
| health | `health.checked` |
| github | `github.metadata_fetched`, `github.branches_listed`, `github.pr_listed`, `github.actions_checked`, `github.materialized` |

### Guarantees

- **Append-only:** Events are never modified or deleted after write
- **Immutable:** Written JSONL files are not rewritten; new events go to the end
- **Content-addressed:** Each event carries a SHA-256 hash of its payload
- **Deterministic ordering:** Events are ordered by timestamp within daily files
- **Concurrent-safe:** File locking via `fcntl.flock` prevents corruption
- **No pipeline modification:** Journal is purely observational; existing behavior unchanged

## Engineering Command Center

The first web application for Hermes Enterprise — a self-hosted observability platform.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  React + TypeScript Frontend (enterprise-ui/)                       │
│  ├── Dashboard    (stats + activity)                                │
│  ├── Repositories (registry + health)                               │
│  ├── Journal      (event log)                                       │
│  ├── Findings     (severity/category)                               │
│  ├── Missions     (queue status)                                    │
│  └── Reports      (execution results)                               │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ REST API
┌───────────────────────────────▼─────────────────────────────────────┐
│  FastAPI Backend (enterprise/)                                       │
│  ├── Auth (JWT + bcrypt)                                            │
│  ├── Repository Registry                                            │
│  ├── Dashboard (aggregated stats)                                   │
│  ├── Journal (event queries)                                        │
│  ├── Findings (engineering findings)                                │
│  ├── Missions (queue management)                                    │
│  └── Reports (execution reports)                                    │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│  SQLAlchemy ORM + SQLite (dev) / PostgreSQL (prod)                  │
│  ├── users, repositories, journal_events, findings                  │
│  ├── missions, reports                                              │
│  └── Alembic migrations                                             │
└─────────────────────────────────────────────────────────────────────┘
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/auth/register` | POST | Register user |
| `/api/auth/login` | POST | Login (returns JWT) |
| `/api/auth/me` | GET | Current user |
| `/api/repositories` | GET/POST | List/create repositories |
| `/api/repositories/{id}` | GET/PATCH/DELETE | Repository CRUD |
| `/api/repositories/{id}/sync` | POST | Sync GitHub metadata |
| `/api/scans` | GET/POST | List/create scan jobs |
| `/api/scans/{id}` | GET | Get scan status + timings |
| `/api/scans/{id}/start` | POST | Start a pending scan |
| `/api/scans/{id}/cancel` | POST | Cancel a queued/running scan |
| `/api/scans/{id}/retry` | POST | Retry a failed/cancelled scan |
| `/api/scans/{id}/history` | GET | Get scan stage history |
| `/api/dashboard/stats` | GET | Aggregated statistics |
| `/api/dashboard/activity` | GET | Recent journal activity |
| `/api/dashboard/activity-v2` | GET | Operational activity metrics |
| `/api/dashboard/overnight` | GET | Overnight summary |
| `/api/journal` | GET | Query journal events |
| `/api/journal/{event_id}` | GET | Get single event |
| `/api/findings` | GET | Query findings |
| `/api/findings/{id}` | GET | Get single finding |
| `/api/missions` | GET | Query missions |
| `/api/missions/{id}` | GET | Get single mission |
| `/api/reports` | GET | Query reports |
| `/api/reports/{id}` | GET | Get single report |

### Scan Lifecycle

Scans progress through these states: `pending` → `queued` → `running` → `completed` / `failed` / `cancelled`.

**Stages:** metadata → repository_analysis → engineering_analysis → governance_analysis → journal_sync → finding_generation

**Cancellation:** Idempotent. Cancelling a completed scan returns it unchanged. Cancelling a running scan sets `cancelled_at` and emits `scan.cancelled`.

**Retry:** Creates a new ScanJob linked to the previous attempt via `previous_scan_id`. The `attempt` field increments. Only `failed` and `cancelled` scans are retryable.

**Timing:** Each stage records `started_at`, `completed_at`, `duration_seconds` in `stage_timings`. Total duration stored in `duration_seconds`.

### Database Schema

- **users** — id, email, name, hashed_password, is_active, is_admin
- **repositories** — id, name, url, default_branch, language, status, provider, identifier, commit_sha, visibility, last_scanned_at, last_synced_at, health_score, findings_count
- **journal_events** — id, event_id, timestamp, event_type, stage, repository_id, actor, payload, payload_sha256
- **findings** — id, repository_id, finding_type, severity, category, title, description, module, priority_score, effort, status
- **missions** — id, mission_id, repository_id, title, description, mission_type, status, priority
- **reports** — id, mission_id, repository_id, title, status, summary, report_data, duration_seconds, tasks_*
- **scan_jobs** — id, repository_id, status, scan_type, branch, commit_sha, started_at, completed_at, duration_seconds, error_message, stages_completed, current_stage, findings_count, attempt, previous_scan_id, requested_by, cancellation_requested_at, cancelled_at, failure_classification, stage_timings
- **scan_history** — id, scan_job_id, stage, status, message, duration_seconds, created_at

### Running

```bash
# Backend
cd enterprise
uvicorn enterprise.app:app --reload

# Frontend
cd enterprise-ui
npm install
npm run dev
```
