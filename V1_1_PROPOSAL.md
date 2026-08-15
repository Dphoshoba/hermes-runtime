# V1.1 Architecture Proposal

**Date:** 2026-08-08
**Author:** Engineering Council
**Baseline:** v1.0.0-alpha (c928d76 → ea7583f)
**Evidence:** 3 dogfood missions, 8 findings, 593 tests passing

---

## Executive Summary

EVOSIA v1.0.0-alpha proved its architecture against real software engineering work. Three end-to-end missions executed correctly through the full pipeline. No EVOSIA defects were found — all failures were target-repository issues (uninstalled dependencies). However, eight friction findings reveal genuine architectural gaps that limit real-world utility.

This proposal analyses each finding, identifies root causes, and recommends a phased improvement plan. Three improvements are approved for v1.1: per-mission queue isolation, per-task environment control, and mission report status separation. The remaining findings are deferred to v1.2 or rejected.

**Key decision:** EVOSIA should remain a *mission execution runtime*, not become a *dependency manager* or *test runner*. Improvements should enhance mission authoring and reporting fidelity without expanding the runtime's scope.

---

## Architecture Review

### Current Architecture Strengths (Validated by Dogfooding)

| Principle | Evidence |
|-----------|----------|
| Atomic persistence | All state files survived 3 missions without corruption |
| Evidence immutability | 12 evidence records generated, all integrity-valid |
| Independent review | 12 reviews completed, all deterministic |
| Deterministic reports | Same mission produces identical report structure |
| Lifecycle state machine | Pause/resume/cancel/abort all functioned correctly |
| Dependency-aware dispatch | Tasks with dependencies executed in correct order |
| Failure isolation | Failed tasks did not block independent siblings |

### Current Architecture Limitations (Exposed by Dogfooding)

| Limitation | Finding | Root Cause |
|------------|---------|------------|
| No task prerequisites | DF-001 | MissionTask has `command` but no `setup` phase |
| Global queue namespace | DF-002 | Task IDs are globally unique within a single queue file |
| Binary mission status | DF-003 | `MissionReport.status` conflates infrastructure and outcome |
| No command helpers | DF-004 | Commands are raw `list[str]`, no abstraction layer |
| No version validation | DF-005 | Constraint engine doesn't inspect command contents |
| No per-task environment | DF-006 | `MissionTask` has `working_directory` but not `env` |
| Health conflates outcomes | DF-008 | `build_health_report` treats non-zero exit codes as failures |

---

## Dogfood Analysis

### Finding DF-001: Prerequisite Task Support

**Architectural Root Cause:**
`MissionTask.command` is the only executable content. The runner calls `subprocess.run(task.command)` directly. There is no concept of "setup" or "teardown" phases within a task. The `working_directory` field exists but only controls `cwd`, not environment setup.

When a mission targets a Python package that isn't installed, tasks that `import` it fail. The mission author must either:
1. Add a manual `pip install -e .` task with dependencies on all downstream tasks, or
2. Ensure the environment is pre-configured outside EVOSIA.

Neither is ergonomic or reliable.

**Classification:** architecture

**Implementation Effort:** Medium (2-3 days)

**Changes Required:**
- Add optional `setup: list[list[str]]` field to `MissionTask` — commands to run before `command`
- Runner executes setup commands sequentially; if any fails, task fails immediately
- Setup commands share the same evidence/review pipeline as main commands
- Backward compatible: `setup` defaults to empty

**Engineering Impact:** High. Enables real-world missions against unconfigured environments.

**Dependencies:** None

**Risk:** Low. Additive schema change. No existing behavior altered.

**Recommendation:** v1.1

---

### Finding DF-002: Per-Mission Queue Isolation

**Architectural Root Cause:**
`enqueue_plan()` in `mission.py:388` adds tasks directly to a shared `WorkQueueManager`. Task IDs are globally unique within the queue file. When two missions share a `--queue-file`, their tasks coexist — which is correct for multi-mission orchestration but wrong for independent mission runs.

The `hermes-mission run` CLI uses a default queue path (`~/.hermes/runtime/state/queue.json`) unless `--queue-file` is specified. This means sequential runs of different missions against the same runtime root silently collide.

**Classification:** workflow

**Implementation Effort:** Low (1 day)

**Changes Required:**
- `hermes-mission run` auto-generates isolated queue path: `~/.hermes/runtime/state/queue-<mission-id>.json`
- `enqueue_plan()` namespaces task IDs by mission_id when enqueuing
- Default `--queue-file` becomes `None` (auto-isolate) instead of shared path
- Backward compatible: explicit `--queue-file` still works for multi-mission orchestration

**Engineering Impact:** High. Prevents the most common dogfood failure mode.

**Dependencies:** None

**Risk:** Low. Changes default behavior but preserves explicit override.

**Recommendation:** v1.1

---

### Finding DF-003: Mission vs Execution Status Separation

**Architectural Root Cause:**
`MissionReport.status` is derived from task outcomes in `mission_runner.py:521-534`:
```python
if all COMPLETED → status = "COMPLETED"
elif some completed → status = "PARTIAL"
else → status = "FAILED"
```

This conflates two distinct concepts:
1. **Infrastructure status:** Did the mission runner execute correctly?
2. **Task outcome:** Did the target commands succeed?

A mission where all tasks fail because the target code has bugs should report `COMPLETED` (infrastructure worked) with `tasks_failed > 0`, not `FAILED` (which implies the runner itself broke).

**Classification:** reporting

**Implementation Effort:** Low (0.5 days)

**Changes Required:**
- Add `pipeline_status: str` field to `MissionReport` — values: `COMPLETED`, `FAILED`, `CANCELLED`, `ABORTED`
- Rename existing `status` to `outcome` — values: `SUCCESS`, `PARTIAL`, `FAILURE`
- `pipeline_status` reflects infrastructure; `outcome` reflects task results
- Backward compatible: `status` field remains as alias for `outcome`

**Engineering Impact:** Medium. Improves reporting clarity without changing behavior.

**Dependencies:** None

**Risk:** Low. Additive field. Existing `status` field preserved.

**Recommendation:** v1.1

---

### Finding DF-004: Built-in Task Helpers

**Architectural Root Cause:**
Tasks are defined as raw `command: list[str]`. Common operations (list files, check patterns, verify imports) require inline Python scripts that are 200+ characters and hard to read in mission JSON.

EVOSIA has no abstraction layer between "mission author writes command" and "subprocess executes command." Every operation is a shell command.

**Classification:** usability

**Implementation Effort:** Medium (2-3 days)

**Changes Required:**
- Add `hermes-exec` CLI entry point with subcommands: `list-files`, `check-import`, `verify-metadata`, `find-patterns`
- Each subcommand is a thin wrapper around common operations
- Tasks can reference `hermes-exec` commands instead of inline Python
- No schema changes — `hermes-exec` is just another command

**Engineering Impact:** Low. Improves mission readability but doesn't unlock new capabilities.

**Dependencies:** None

**Risk:** Very low. Purely additive CLI.

**Rejection consideration:** Could be deferred to v1.2. Missions work without it; inline Python is ugly but functional.

**Recommendation:** v1.2

---

### Finding DF-005: Python Version Compatibility Validation

**Architectural Root Cause:**
`mission_constraints.py` validates structural constraints (repository exists, working directory writable, capabilities available) but does not inspect command contents. There is no mechanism to check whether a command uses Python features unavailable in the target runtime.

The `RuntimeVersionConstraint` checks `sys.version_info` against min/max bounds but doesn't correlate this with command contents.

**Classification:** constraints

**Implementation Effort:** Medium (1-2 days)

**Changes Required:**
- Add `Python Compatibility Constraint` to `mission_constraints.py`
- Scans task commands for known incompatible imports (`tomllib` on 3.10, `match` statement usage, etc.)
- Warns (not blocks) when potential incompatibility detected
- Requires `min_python_version` context parameter

**Engineering Impact:** Low. Prevents a specific class of runtime errors.

**Dependencies:** None

**Risk:** Low. Warning-only, not blocking.

**Rejection consideration:** Could be deferred to v1.2. The constraint is useful but not critical.

**Recommendation:** v1.2

---

### Finding DF-006: Per-Task Environment Control

**Architectural Root Cause:**
`MissionTask` has `working_directory: str | None` which controls `cwd` for subprocess execution. There is no `env` field. All tasks inherit the process environment.

When missions need to set environment variables (e.g., `PYTHONPATH`, `PYTHONDONTWRITEBYTECODE`, custom config), there is no mechanism within the mission definition.

**Classification:** architecture

**Implementation Effort:** Low (0.5 days)

**Changes Required:**
- Add `env: dict[str, str] | None = None` field to `MissionTask`
- Runner merges task env with `os.environ` when executing subprocess
- `working_directory` already exists and works correctly
- Backward compatible: `env` defaults to None (inherit full environment)

**Engineering Impact:** Medium. Enables missions to control execution context without external setup.

**Dependencies:** None

**Risk:** Very low. Additive field. No existing behavior altered.

**Recommendation:** v1.1

---

### Finding DF-007: Evidence for Failed Tasks (Correct Behavior)

**Classification:** N/A — confirmed correct

The mission runner generates evidence and reviews for every task execution, regardless of exit code. This is by design: evidence records what happened, not whether it succeeded. Non-zero exit codes are recorded, not interpreted.

**No action required.**

---

### Finding DF-008: Health Metric Refinement

**Architectural Root Cause:**
`build_health_report()` in `health.py:103-118` treats non-zero exit codes as health failures:
```python
if last_execution_exit_code not in (None, 0):
    failures.append(f"latest execution exit code: {last_execution_exit_code}")
```

This conflates "the runtime executed a task that returned non-zero" with "the runtime itself is unhealthy." When a mission intentionally tests error handling (expected non-zero exit), health reports `FAILED`.

**Classification:** reporting

**Implementation Effort:** Low (0.5 days)

**Changes Required:**
- Add `infrastructure_health` field to `HealthReport` — reflects runtime operational status
- Keep `overall_health` as-is for backward compatibility
- `infrastructure_health` checks: state files readable, evidence dir writable, no corruption
- `overall_health` remains derived from latest execution/review/supervisor

**Engineering Impact:** Low. Improves health reporting fidelity.

**Dependencies:** None

**Risk:** Low. Additive field.

**Recommendation:** v1.2

---

## Candidate Improvements

### v1.1 (Approved)

| ID | Finding | Change | Effort | Impact |
|----|---------|--------|--------|--------|
| IMP-001 | DF-002 | Per-mission queue isolation | 1 day | High |
| IMP-002 | DF-006 | Per-task `env` field | 0.5 days | Medium |
| IMP-003 | DF-003 | Mission report `pipeline_status` + `outcome` | 0.5 days | Medium |
| IMP-004 | DF-001 | Task `setup` commands | 2-3 days | High |

**Total v1.1 effort:** 4-5 days

### v1.2 (Deferred)

| ID | Finding | Change | Effort | Impact |
|----|---------|--------|--------|--------|
| IMP-005 | DF-004 | `hermes-exec` task helpers | 2-3 days | Low |
| IMP-006 | DF-005 | Python version compatibility constraint | 1-2 days | Low |
| IMP-007 | DF-008 | Health `infrastructure_health` field | 0.5 days | Low |

**Total v1.2 effort:** 3.5-5.5 days

### Rejected

None. All findings represent genuine architectural gaps. None should be rejected outright — they are deferred based on impact-to-effort ratio.

---

## Implementation Order

```
v1.1.0-alpha (current)
    │
    ├── IMP-001: Per-mission queue isolation (DF-002)
    │   └── No dependencies. Implement first.
    │
    ├── IMP-002: Per-task env field (DF-006)
    │   └── No dependencies. Can parallel with IMP-001.
    │
    ├── IMP-003: Mission report status separation (DF-003)
    │   └── No dependencies. Can parallel with IMP-001/002.
    │
    └── IMP-004: Task setup commands (DF-001)
        └── Depends on IMP-002 (env field) for setup environment.
            Implement last.
    │
    ▼
v1.1.0-beta
    │
    ├── IMP-005: hermes-exec task helpers (DF-004)
    ├── IMP-006: Python version constraint (DF-005)
    └── IMP-007: Infrastructure health field (DF-008)
    │
    ▼
v1.2.0-alpha
```

---

## Migration Strategy

### Schema Changes

All schema changes are **additive only**:

| Change | Backward Compatible | Migration Required |
|--------|--------------------|--------------------|
| `MissionTask.setup` (optional) | Yes — defaults to `[]` | No |
| `MissionTask.env` (optional) | Yes — defaults to `None` | No |
| `MissionReport.pipeline_status` (new) | Yes — new field | No |
| `MissionReport.outcome` (alias) | Yes — `status` field preserved | No |
| Queue auto-isolation | Yes — explicit `--queue-file` still works | No |

### Existing Missions

All existing mission JSON files continue to work without modification. New fields are optional with sensible defaults.

### Existing Queue State

Queue files from v1.0.0-alpha load without migration. Auto-isolation creates new queue files; existing shared queues continue to work.

---

## Compatibility Assessment

| Dimension | Assessment |
|-----------|------------|
| Mission JSON schema | Backward compatible — new optional fields |
| MissionReport JSON | Backward compatible — new fields added |
| CLI interfaces | Backward compatible — new defaults, explicit overrides preserved |
| Queue state | Backward compatible — existing files load |
| Evidence format | Unchanged |
| Review format | Unchanged |
| Health report | Backward compatible — new field added |
| Python version | Remains >= 3.10 |
| Test baseline | Remains 593+ tests |

**No breaking changes in v1.1.**

---

## Engineering Risk Matrix

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Queue auto-isolation breaks multi-mission orchestration | Low | Medium | Explicit `--queue-file` preserves old behavior |
| Task `setup` adds execution overhead | Low | Low | Setup is optional; only runs when present |
| `env` field leaks sensitive variables | Low | High | Document that `env` supplements, not replaces, environment |
| `pipeline_status` confuses existing consumers | Low | Low | `status` field preserved as alias |
| New fields increase JSON payload size | Very Low | Very Low | Optional fields omitted when None |

**Overall risk: Low.** All changes are additive, backward compatible, and optional.

---

## Release Recommendation

### v1.1.0-alpha

**Scope:** IMP-001, IMP-002, IMP-003, IMP-004

**Criteria for release:**
- All 4 improvements implemented
- 593+ tests passing (existing) + new tests for each improvement
- Package builds and installs
- Dogfood missions re-executed successfully with improved ergonomics
- Documentation updated
- No breaking changes

**Estimated timeline:** 4-5 days of focused engineering

### v1.1.0-beta

**Scope:** IMP-005, IMP-006, IMP-007

**Criteria for release:**
- All 3 deferred improvements implemented
- Full regression suite passes
- Dogfood validation complete

**Estimated timeline:** 3-5 days after v1.1.0-alpha

---

## Appendix: Finding Disposition Summary

| Finding | Classification | Version | Rationale |
|---------|---------------|---------|-----------|
| DF-001 | architecture | v1.1 | High impact, enables real-world missions |
| DF-002 | workflow | v1.1 | High impact, prevents most common failure mode |
| DF-003 | reporting | v1.1 | Low effort, improves clarity |
| DF-004 | usability | v1.2 | Low impact, missions work without it |
| DF-005 | constraints | v1.2 | Low impact, specific class of errors |
| DF-006 | architecture | v1.1 | Medium effort, enables env control |
| DF-007 | correct | — | No action |
| DF-008 | reporting | v1.2 | Low impact, health is informational |
