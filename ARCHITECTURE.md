# Hermes Runtime Architecture

## Overview

Hermes Runtime is an autonomous engineering runtime that executes missions through a pipeline of evidence collection, independent review, and health monitoring. It is designed for deterministic, restart-safe operation with full audit trails.

## Module Structure

```
hermes_v01/
  __init__.py          # Package version
  __main__.py          # Read-only repository inspection (hermes-validate)
  utils.py             # Shared utilities (sha256, format_utc, fsync)

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

  # Queue & Scheduling
  work_queue.py        # Deterministic, restart-safe work queue
  supervisor.py        # Autonomous execution supervisor

  # Capabilities & Metrics
  capabilities.py      # Pluggable executor system
  metrics.py           # Runtime and queue metrics

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
- State files: queue.json, supervisor-state.json, runtime-state.json

## Evidence Integrity

- Evidence records are immutable (read-only after publication)
- SHA-256 digests verify content integrity
- `fsync` ensures durability on write
- `os.link` prevents partial writes (atomic rename)
