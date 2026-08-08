# Hermes Runtime

Autonomous engineering runtime for deterministic mission execution with full audit trails.

**Version: 1.0.0-beta**

## Installation

```bash
pip install -e .
```

Requires Python >= 3.10.

## CLI Commands

| Command | Description |
|---------|-------------|
| `hermes-ready` | Repository readiness assessment (pre-pipeline gate) |
| `hermes-validate` | Read-only repository inspection |
| `hermes-supervise` | Persistent execution supervisor |
| `hermes-status` | Canonical runtime state projection |
| `hermes-record` | Immutable evidence recorder |
| `hermes-review` | Independent review of execution records |
| `hermes-health` | Runtime health monitoring |
| `hermes-runtime` | Queue-driven pipeline orchestrator |
| `hermes-queue` | Work queue management |
| `hermes-metrics` | Runtime and queue metrics |
| `hermes-capabilities` | Plugin and executor management |
| `hermes-plan` | Mission planning and validation |
| `hermes-mission` | Mission execution and reporting |

## One-shot validation

```bash
python3 -m hermes_v01 --repo /path/to/repository --output-dir ./hermes-report
```

It writes `verification-report.json` and `verification-report.md`.

## Persistent supervisor

```bash
python3 -m hermes_v01.supervisor_cli \
  --repo /path/to/repository \
  --output-dir ./hermes-report \
  --interval 60
```

Useful controls:

```bash
# Run exactly three cycles
python3 -m hermes_v01.supervisor_cli \
  --repo /path/to/repository \
  --output-dir ./hermes-report \
  --interval 1 \
  --max-cycles 3

# Request a graceful stop
mkdir -p ./hermes-report && touch ./hermes-report/STOP
```

The supervisor persists `supervisor-state.json` atomically and writes each cycle beneath `hermes-report/cycles/`.

With `--work-queue`, the supervisor enqueues remediation tasks for missing or unverified artifacts.

## Safety boundary

Hermes never modifies the inspected repository, approves governance, changes lifecycle state, or infers repository facts. Reports and supervisor state are written only beneath the configured output directory.

## Canonical runtime status

Project the supervisor's persisted state into a stable Program III runtime view:

```bash
python3 -m hermes_v01.status_cli \
  --supervisor-state ./hermes-report/supervisor-state.json \
  --milestone "Runtime State Manager" \
  --write-state ./hermes-report/runtime-state.json
```

The command prints JSON and returns exit code `2` when a concrete blocker is present.

With `--work-queue`, the projected state includes the work queue summary.

## Work Queue CLI

`hermes-queue` provides a CLI for the deterministic, restart-safe Program III work queue.

```bash
# Initialize queue with tasks
python3 -c "
from hermes_v01.work_queue import WorkItem, WorkQueueManager, WorkQueueStateStore
from pathlib import Path
WorkQueueManager(
    state_store=WorkQueueStateStore(Path('/tmp/queue.json')),
    items=(WorkItem('task-1', 'Task 1', priority=10),),
)
"

# List all tasks
hermes-queue --state-file /tmp/queue.json list

# Show next READY task
hermes-queue --state-file /tmp/queue.json next

# Dispatch next READY task to RUNNING
hermes-queue --state-file /tmp/queue.json dispatch

# Observe, verify, complete
hermes-queue --state-file /tmp/queue.json observe task-1
hermes-queue --state-file /tmp/queue.json verification-pending task-1
hermes-queue --state-file /tmp/queue.json verify task-1
hermes-queue --state-file /tmp/queue.json complete task-1

# Summary by state
hermes-queue --state-file /tmp/queue.json summary
```

## Immutable execution evidence

Program III includes an Evidence Recorder that executes one command and publishes one immutable execution record. The recorder captures literal command data, UTC timestamps, the numeric process exit code, stdout and stderr files, supplied artifact paths, file digests, and the repository revision when Git metadata is available. It does not interpret a non-zero exit code as an evidence-integrity failure and never promotes independent-review state.

```bash
hermes-record \
  --evidence-dir "$HOME/.hermes/runtime/evidence" \
  --cwd /path/to/workspace \
  --repository /path/to/repository \
  --artifact /path/to/generated/artifact.json \
  -- python3 -m pytest -q
```

With `--task-id` and `--work-queue`, the recorder advances the task through `RUNNING` → `OBSERVED` → `VERIFICATION_PENDING`.

Each execution is stored beneath its unique execution ID:

```text
evidence/
└── exec-<UTC>-<random>/
    ├── execution-record.json
    ├── stdout.log
    └── stderr.log
```

Published evidence files are made read-only. A second publication to the same record path fails rather than overwriting the original evidence.

## Independent Reviewer

Review one immutable execution record without re-running the command or modifying its evidence:

```bash
hermes-review \
  --record "$HOME/.hermes/runtime/evidence/exec-.../execution-record.json" \
  --output-dir "$HOME/.hermes/runtime/reviews"
```

With `--task-id` and `--work-queue`, a `REVIEW_PASSED` outcome advances the task to `VERIFIED`.

The reviewer validates the evidence schema, execution ID, timestamps, numeric exit code, artifact existence, recorded sizes and SHA-256 hashes, execution-record digest, and repository revision format when present. It publishes immutable `review.json` and `review.md` artifacts. Outcomes are exactly `REVIEW_PASSED`, `REVIEW_FAILED`, or `REVIEW_INCOMPLETE`.

## Queue-driven Runtime Orchestrator

`hermes-runtime` executes the full evidence pipeline (record → review → health) for a queued work item.

```bash
# Execute specific task
hermes-runtime \
  --runtime-root "$HOME/.hermes/runtime" \
  --repository /path/to/repo \
  --cwd /path/to/workspace \
  --task-id task-1 \
  --work-queue /tmp/queue.json \
  -- python3 -m pytest -q

# Execute next READY task (respects dependencies)
hermes-runtime \
  --runtime-root "$HOME/.hermes/runtime" \
  --repository /path/to/repo \
  --cwd /path/to/workspace \
  --next \
  --work-queue /tmp/queue.json \
  -- python3 -m pytest -q
```

On success, the task advances: `RUNNING` → `OBSERVED` → `VERIFICATION_PENDING` → `VERIFIED` → `COMPLETE`.
On failure, the task stops at `VERIFIED` (review passed) or `OBSERVED` (record failed), leaving the queue recoverable.

## Concurrent Mission Execution

`hermes-mission run` supports concurrent execution of independent tasks via `--concurrency N`:

```bash
hermes-mission run mission.json \
  --runtime-root "$HOME/.hermes/runtime" \
  --repository /path/to/repo \
  --cwd /path/to/workspace \
  --queue-file /tmp/queue.json \
  --concurrency 4
```

Tasks are dispatched in dependency order. Independent tasks execute in parallel up to the concurrency limit. Failed tasks do not block independent siblings. The `MissionReport` includes `max_concurrency` and `peak_concurrent_tasks` fields.

When `--concurrency` is omitted or set to 1, tasks execute sequentially (the default).

## Health Monitoring

`hermes-health` generates a health report from the runtime state:

```bash
hermes-health \
  --runtime-root "$HOME/.hermes/runtime" \
  --output-dir "$HOME/.hermes/runtime/health"
```

## Metrics

`hermes-metrics` generates runtime and queue metrics:

```bash
hermes-metrics \
  --runtime-root "$HOME/.hermes/runtime" \
  --output-dir "$HOME/.hermes/runtime/metrics"
```

## Capabilities

`hermes-capabilities` manages executor plugins:

```bash
hermes-capabilities list
hermes-capabilities check-all
```

## Mission Planning

`hermes-plan` validates and builds mission plans:

```bash
hermes-plan validate mission.json
hermes-plan build mission.json --output plan.json
hermes-plan enqueue plan.json --queue-file /tmp/queue.json
```

## Mission Types

`hermes-mission` supports typed missions:

```bash
hermes-mission types
hermes-mission type-show repository-maintenance
hermes-mission run mission.json --mission-type security-audit
```

## Mission Constraints

Validate mission constraints before execution:

```bash
hermes-mission constraints mission.json --repository /path/to/repo
```

## Mission Lifecycle Control

Control running missions with lifecycle commands. The CLI writes commands atomically to `mission_control.json`; the running `MissionRunner` polls and applies them.

```bash
# Check current mission state
hermes-mission status --runtime-root "$HOME/.hermes/runtime"

# Pause a running mission (lets in-flight tasks finish)
hermes-mission pause --runtime-root "$HOME/.hermes/runtime" --reason "debugging"

# Resume a paused mission
hermes-mission resume --runtime-root "$HOME/.hermes/runtime"

# Cancel a mission (stop future work, preserve evidence)
hermes-mission cancel --runtime-root "$HOME/.hermes/runtime" --reason "no longer needed"

# Abort a mission (immediate stop, cancel pending futures)
hermes-mission abort --runtime-root "$HOME/.hermes/runtime" --reason "emergency"
```

### Lifecycle States

| State | Description |
|-------|-------------|
| `READY` | Plan loaded, not yet executing |
| `RUNNING` | Actively executing tasks |
| `PAUSED` | Paused: no new tasks dispatched, running tasks finish |
| `COMPLETED` | All tasks succeeded (terminal) |
| `PARTIAL` | Some tasks succeeded, some failed/cancelled |
| `FAILED` | Execution error (terminal) |
| `CANCELLED` | User cancelled: future work stopped (terminal) |
| `ABORTED` | Immediate termination requested (terminal) |

### Control Architecture

- **`mission_control.json`**: Requested lifecycle action (written by CLI)
- **`mission_state.json`**: Authoritative observed state (written by runner)
- Commands use incrementing IDs to prevent stale replay
- Commands are mission-scoped: wrong `mission_id` is rejected
- Terminal states cannot be transitioned out of

## Mission Reports

`hermes-mission` automatically generates comprehensive report artifacts after each execution:

```bash
# Reports are generated automatically during hermes-mission run
# Artifacts stored under reports/<mission-id>/

# Generate report for an existing mission
hermes-mission generate-report <mission-id> --runtime-root "$HOME/.hermes/runtime"

# Or manually regenerate with repository context
hermes-mission generate-report <mission-id> \
  --runtime-root "$HOME/.hermes/runtime" \
  --repository /path/to/repo
```

### Report Artifacts

| File | Description |
|------|-------------|
| `reports/<mission-id>/MISSION_REPORT.json` | Authoritative JSON report (deterministic) |
| `reports/<mission-id>/MISSION_REPORT.md` | Human-readable Markdown |

### Report Contents

Reports include: lifecycle state, task summary, queue summary, retry/scheduler/concurrency summaries, evidence and review aggregates, health status, capability usage, git revision, runtime version, warnings, and errors.

See [MISSION_REPORT_SCHEMA.md](MISSION_REPORT_SCHEMA.md) for the full schema documentation.
