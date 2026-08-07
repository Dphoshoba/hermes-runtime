# Mission Report Schema

This document describes the schema for `MISSION_REPORT.json` — the authoritative, deterministic artifact produced after each mission execution.

## Version

Schema version: `1` (current)

## Artifacts

Each mission produces two report artifacts under `reports/<mission-id>/`:

| File | Description |
|------|-------------|
| `MISSION_REPORT.json` | Authoritative JSON report (deterministic serialization) |
| `MISSION_REPORT.md` | Human-readable Markdown generated from the same model |

Both artifacts are derived from a single `MissionReport` model. The Markdown is never independently maintained.

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | `string` | Schema version (always `"1"`) |
| `mission_id` | `string` | Unique mission identifier |
| `mission_title` | `string` | Human-readable mission title |
| `mission_type` | `string` | Mission type name (e.g., `"generic"`, `"security-audit"`) |
| `status` | `string` | Overall status: `COMPLETED`, `PARTIAL`, `FAILED`, `CANCELLED`, `ABORTED` |
| `started_at` | `string` | ISO 8601 UTC timestamp when execution started |
| `finished_at` | `string` | ISO 8601 UTC timestamp when execution finished |
| `duration_seconds` | `float` | Wall-clock duration in seconds |
| `tasks_planned` | `int` | Total tasks in the plan |
| `tasks_completed` | `int` | Tasks that completed successfully |
| `tasks_failed` | `int` | Tasks that failed |
| `tasks_skipped` | `int` | Tasks that never executed |
| `evidence_records` | `string[]` | Paths to execution-record.json files |
| `independent_reviews` | `string[]` | Paths to review.json files |
| `queue_summary` | `{string: string[]}` | Map of task state → list of task IDs |
| `runtime_health` | `string` | Health status: `HEALTHY`, `WARNING`, `FAILED`, `UNKNOWN` |
| `metrics_summary` | `{string: any}` | Runtime metrics (total_executions, etc.) |
| `warnings` | `string[]` | Non-fatal warnings |
| `errors` | `string[]` | Fatal errors |
| `artifacts_produced` | `string[]` | Paths to generated artifacts |

## Optional Fields (with defaults)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mission_report_path` | `string \| null` | `null` | Path to this report file |
| `max_concurrency` | `int` | `1` | Maximum concurrent tasks allowed |
| `peak_concurrent_tasks` | `int` | `0` | Peak concurrent tasks observed |

## v0.9.6 Lifecycle Fields

These fields are included when set (non-default). They are omitted from JSON output when empty/null to maintain deterministic output.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `lifecycle_state` | `string` | `""` | Mission lifecycle state: `READY`, `RUNNING`, `PAUSED`, `COMPLETED`, `CANCELLED`, `ABORTED`, `FAILED` |
| `tasks_cancelled` | `int` | `0` | Tasks cancelled (from CANCELLED lifecycle state) |
| `tasks_aborted` | `int` | `0` | Tasks aborted (from ABORTED lifecycle state) |
| `retry_summary` | `{string: any} \| null` | `null` | Retry queue state summary |
| `scheduler_summary` | `{string: any} \| null` | `null` | Scheduler state summary |
| `concurrency_summary` | `{string: any} \| null` | `null` | Concurrency metrics |
| `capability_usage` | `{string: any} \| null` | `null` | Executor capability usage |
| `evidence_summary` | `{string: any} \| null` | `null` | Aggregate evidence statistics |
| `independent_review_summary` | `{string: any} \| null` | `null` | Aggregate review statistics |
| `health_summary` | `{string: any} \| null` | `null` | Runtime health details |
| `repository` | `string \| null` | `null` | Repository path |
| `git_revision` | `string \| null` | `null` | 40-char hex SHA of HEAD at execution time |
| `runtime_version` | `string` | `""` | Hermes Runtime version |

## Status Semantics

| Status | Meaning |
|--------|---------|
| `COMPLETED` | All tasks succeeded. Terminal. |
| `PARTIAL` | Some tasks succeeded, some failed/cancelled/aborted. |
| `FAILED` | No tasks succeeded, or plan was invalid. Terminal. |
| `CANCELLED` | Mission was cancelled by user. Terminal. |
| `ABORTED` | Mission was aborted (immediate stop). Terminal. |

**Never report `COMPLETED` when `lifecycle_state` is not terminally completed.**

## Lifecycle State Mapping

| lifecycle_state | status | tasks_cancelled | tasks_aborted |
|----------------|--------|-----------------|---------------|
| `COMPLETED` | `COMPLETED` | 0 | 0 |
| `FAILED` | `FAILED` | 0 | 0 |
| `CANCELLED` (with completions) | `PARTIAL` | remaining tasks | 0 |
| `CANCELLED` (no completions) | `FAILED` | remaining tasks | 0 |
| `ABORTED` (with completions) | `PARTIAL` | 0 | remaining tasks |
| `ABORTED` (no completions) | `FAILED` | 0 | remaining tasks |

## Artifact Relationships

```
MISSION_REPORT.json
├── evidence_records[] → exec-*/execution-record.json
├── independent_reviews[] → review-*/review.json
├── artifacts_produced[] → execution-record.json (from run dirs)
└── queue_summary → reflects WorkQueueManager state at completion

MISSION_REPORT.md
└── Generated from MISSION_REPORT.json via render_markdown()
```

## Determinism Guarantees

1. **JSON serialization**: Keys are sorted alphabetically. `sort_keys=True` in `json.dumps`.
2. **Optional fields**: Only included when non-default. This prevents volatile null fields.
3. **Evidence/review lists**: Paths are already deterministic (from queue state).
4. **Queue summary**: Deterministic from `WorkQueueManager.summary()` which sorts by `(priority, task_id)`.
5. **Timestamps**: Set once at execution boundaries, not refreshed.
6. **Same persisted outcome → same report**: The same `MissionReport` instance always produces identical JSON and Markdown.

## Versioning Expectations

- Schema version increments when field names, types, or semantics change.
- New optional fields are added with backward-compatible defaults.
- Existing required fields are never removed or renamed within a major version.
- `MISSION_REPORT.json` is the authoritative artifact; Markdown is derived.
