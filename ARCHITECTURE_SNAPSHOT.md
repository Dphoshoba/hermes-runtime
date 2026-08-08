# Architecture Snapshot — Hermes Runtime v1.0.0-beta

Date: 2026-08-08

## Module Map

```
hermes_v01/
├── __init__.py              # Package version (1.0.0a0)
├── __main__.py              # Read-only repository inspection (hermes-validate)
├── utils.py                 # Shared utilities (sha256, utc_now_str, format_utc,
│                            #   make_read_only, fsync_directory, atomic_write_json)
│
├── evidence.py              # Immutable evidence recording and integrity
├── reviewer.py              # Independent review of execution records
├── health.py                # Runtime health monitoring
├── runtime.py               # Pipeline orchestrator (record → review → health)
├── runtime_state.py         # Projected runtime state from supervisor
│
├── mission.py               # Mission schema, planner, plan serialization
├── mission_runner.py        # Mission execution (sequential + concurrent)
├── mission_types.py         # Extensible mission type registry (7 built-in)
├── mission_constraints.py   # Pre-execution constraint validation (7 built-in)
├── mission_state.py         # Mission lifecycle state machine
├── mission_control.py       # Cross-process lifecycle control
├── mission_report.py        # Report generation, Markdown rendering, persistence
│
├── work_queue.py            # Deterministic, restart-safe work queue
├── supervisor.py            # Autonomous execution supervisor
│
├── capabilities.py          # Pluggable executor system
├── metrics.py               # Runtime and queue metrics
│
└── *_cli.py                 # CLI handlers (12 entry points)
```

## Data Flow

```
Mission JSON
    │
    ▼
MissionPlanner.validate() → Plan
    │
    ▼
enqueue_plan() → WorkQueueManager
    │
    ▼
MissionRunner.run()
    │
    ├── Sequential: dispatch_ready(1) → run_pipeline() → result → next
    │
    ├── Concurrent: dispatch_ready(N) → ThreadPoolExecutor → collect results
    │
    ▼
MissionReport (JSON + Markdown)
```

## Pipeline Per Task

```
RUNNING
  → hermes-record (evidence)     → OBSERVED
  → hermes-review (review)       → VERIFICATION_PENDING → VERIFIED
  → hermes-health (health check)
  → COMPLETE (success) or FAILED (error)
```

## Concurrency Model

| Mode | Behavior |
|------|----------|
| `max_concurrency=1` | Sequential execution (default) |
| `max_concurrency>1` | ThreadPoolExecutor with dependency-aware dispatch |

- `WorkQueueManager` uses `threading.RLock` for safe concurrent state mutations
- Failed tasks do not block independent siblings
- Futures keyed by `{task_id}:{attempts}` to prevent collision on retry

## Lifecycle State Machine

```
READY → RUNNING → COMPLETED
                 → FAILED
                 → PAUSED → RUNNING (resume)
                         → CANCELLED (terminal)
                         → ABORTED (terminal)
                 → CANCELLED (terminal)
                 → ABORTED (terminal)
```

Terminal states have no outgoing transitions.

## Cross-Process Control

- `mission_control.json` — CLI writes lifecycle commands atomically
- `mission_state.json` — Runner writes authoritative observed state
- Command ID ordering prevents stale replay
- Mission-scoped: wrong `mission_id` is rejected

## Persistence Pattern

All state files use atomic writes:
```
mkstemp → write → flush → fsync → os.replace → fsync directory
```

State files:
- `queue.json` — work queue
- `supervisor-state.json` — supervisor state
- `runtime-state.json` — projected runtime state
- `mission_state.json` — lifecycle state
- `mission_control.json` — lifecycle commands
- `reports/<mission-id>/MISSION_REPORT.json` — mission report

## Key Design Decisions

1. **Frozen dataclasses** for immutable state (MissionReport, HealthReport, etc.)
2. **Deterministic JSON** with `sort_keys=True` for reproducible outputs
3. **Single canonical model** — JSON and Markdown derived from same dataclass
4. **Decoupled modules** — reviewer imports from utils, not evidence
5. **Entry point discovery** for mission types and capability plugins
