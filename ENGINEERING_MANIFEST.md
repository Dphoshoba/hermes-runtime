# Engineering Manifest — EVOSIA Runtime

## Purpose

EVOSIA Runtime is an autonomous engineering runtime that executes missions through a pipeline of evidence collection, independent review, and health monitoring. It is designed for deterministic, restart-safe operation with full audit trails.

## Design Philosophy

- **Determinism over speed.** Same inputs always produce same outputs. JSON keys sorted, timestamps normalized, reports derived from a single canonical model.
- **Durability over convenience.** Every state mutation uses atomic writes (mkstemp → write → fsync → os.replace → fsync directory). No partial state survives a crash.
- **Immutability for evidence.** Published evidence and reviews are read-only. Second publication to the same path fails rather than overwriting.
- **Composability over monolith.** Each subsystem (evidence, review, health, queue, mission) is an independent module with a narrow interface. CLIs compose them; libraries don't depend on CLIs.
- **No hidden state.** All state is persisted to disk in JSON. In-memory state is always derivable from persisted state. Restart recovers full context.

## Architectural Principles

1. **Single responsibility per module.** `evidence.py` records. `reviewer.py` reviews. `health.py` monitors. `mission_runner.py` orchestrates. No module does another module's job.
2. **Dataclasses for all state.** Every stateful entity is a frozen or mutable dataclass with `as_dict()` for serialization. No dicts-as-structs.
3. **CLI handlers are thin.** CLI modules parse arguments, call library functions, print JSON. No business logic in CLI handlers.
4. **Shared utilities in utils.py.** Hashing, timestamps, atomic writes, file permissions. No duplicate utility functions across modules.
5. **Entry point discovery.** Mission types and capability plugins are discovered via `importlib.metadata.entry_points`. No hardcoded plugin lists.

## Public API Philosophy

- **CLI-first for users.** All functionality is accessible via `hermes-*` commands.
- **Library-first for programs.** All CLI handlers delegate to library functions that can be imported directly.
- **No stable API guarantee yet.** This is alpha. Internal interfaces may change between minor versions.
- **JSON in, JSON out.** All CLIs accept and produce JSON. No binary protocols, no custom formats.

## Persistence Guarantees

- **Atomic writes.** All state files are written atomically via `utils.atomic_write_json()`. Pattern: `mkstemp → json.dump → flush → fsync → os.replace → fsync directory`.
- **No data loss on crash.** If a write fails mid-stream, the original file remains valid. Temp files are cleaned up on error.
- **Durability on completion.** `fsync` on both file and directory ensures bytes reach stable storage before the write is considered complete.
- **State files:**
  - `queue.json` — work queue state
  - `supervisor-state.json` — supervisor state
  - `runtime-state.json` — projected runtime state
  - `mission_state.json` — lifecycle state
  - `mission_control.json` — lifecycle commands
  - `reports/<mission-id>/MISSION_REPORT.json` — mission report
  - `reports/<mission-id>/MISSION_REPORT.md` — mission report (derived)

## Concurrency Guarantees

- **Thread-safe queue.** `WorkQueueManager` uses `threading.RLock` for all state mutations. Safe for concurrent access from multiple threads.
- **Concurrent task execution.** `MissionRunner` supports `max_concurrency > 1` via `ThreadPoolExecutor`. Independent tasks execute in parallel; dependent tasks wait.
- **No race conditions.** Shared counters protected by `_queue_lock`. Futures keyed by `{task_id}:{attempts}` to prevent collision on retry.
- **Failure isolation.** Failed tasks do not block independent siblings. Dependent tasks are skipped.

## Mission Lifecycle Guarantees

- **State machine.** READY → RUNNING → COMPLETED/CANCELLED/ABORTED/FAILED. Terminal states have no outgoing transitions.
- **Cross-process control.** CLI writes `mission_control.json`; runner polls and applies. Command ID ordering prevents stale replay.
- **Mission-scoped commands.** Commands rejected if `mission_id` does not match active mission.
- **Graceful pause.** Pausing lets in-flight tasks finish. No new tasks dispatched until resumed.
- **Cancellation.** Future work stopped, running tasks finish, terminal state.
- **Abortion.** Immediate stop, pending futures cancelled, terminal state.

## Evidence Guarantees

- **Immutability.** Published evidence files are made read-only. Second publication to the same path raises `FileExistsError`.
- **Integrity.** SHA-256 digests recorded for all artifacts. Execution record includes command, exit code, stdout, stderr, timestamps.
- **No inference.** Non-zero exit codes are recorded, not interpreted as evidence-integrity failures.
- **Repository revision.** When Git metadata is available, the repository revision is recorded.

## Independent Review Guarantees

- **No re-execution.** Reviewers examine evidence without re-running commands.
- **Schema validation.** Evidence schema, execution ID format, timestamps, exit codes, artifact existence, file sizes, SHA-256 hashes, and digest are validated.
- **Deterministic outcomes.** Same evidence always produces same review outcome: `REVIEW_PASSED`, `REVIEW_FAILED`, or `REVIEW_INCOMPLETE`.
- **No state promotion.** Reviews never promote independent-review state. Only the queue manager advances task state.

## Compatibility Guarantees

- **Python >= 3.10.** No older versions supported.
- **No breaking changes within alpha.** CLI interfaces and JSON schemas may add fields but will not remove or rename existing fields within v1.0.0-alpha.
- **Backward-compatible queue state.** New fields added with defaults. Existing queue files load without migration.

## Determinism

- **Sorted JSON keys.** All `json.dump` calls use `sort_keys=True`.
- **Stable timestamps.** UTC with `Z` suffix. No timezone-aware/naive mixing.
- **Canonical reports.** JSON and Markdown derived from the same dataclass. Same persisted outcome → same logical report.
- **No random in outputs.** Mission IDs, execution IDs, and review IDs include random components, but all other output is deterministic given the same inputs.

## Error-Handling Philosophy

- **Fail loud.** Errors raise exceptions with descriptive messages. No silent failures.
- **No swallowing.** `except Exception: pass` is forbidden. All exceptions are either handled explicitly or propagated.
- **Graceful degradation.** Health monitoring degrades on malformed inputs rather than crashing. Missing optional data is reported as `UNKNOWN`, not an error.
- **Recoverable queues.** Failed tasks stop at a recoverable state. Manual retry or re-dispatch is always possible.

## Release Philosophy

- **Alpha.** API may change. Internal interfaces are not stable. Documentation may lag implementation.
- **Test-gated.** Every release requires 100% test pass rate on the full regression suite.
- **Single coherent commit.** Each release is one commit with all changes.
- **Changelog-driven.** Every user-visible change is documented in CHANGELOG.md.

## Evidence-Driven Evolution

EVOSIA evolves only when operational evidence demonstrates a need.

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
7. **Why Existing Capabilities Are Insufficient** — Why can't EVOSIA solve this today?
8. **Expected Benefit** — What measurable improvement is expected?
9. **Success Criteria** — How will we know the fix works?
10. **Rollback Strategy** — How do we revert if the fix causes problems?

If these sections are absent, the proposal should not be accepted.

## Coding Standards

- **Type annotations.** All public functions and CLI handlers have type annotations. `argparse.Namespace` for CLI args.
- **Docstrings.** All public classes and functions have docstrings. Internal helpers may omit them.
- **No comments.** Code should be self-documenting. Comments are for intent, not description.
- **`from __future__ import annotations`.** All modules use modern annotation syntax.
- **No mutable defaults.** Function parameters never default to `[]` or `{}`. Use `None` and initialize inside.
- **No unused imports.** Every import is used. No `import os` when `os` is not referenced.

## Testing Expectations

- **593 tests.** All must pass before any release.
- **Test isolation.** Each test creates its own temp directory. No shared state between tests.
- **Deterministic tests.** No time-dependent assertions. No random inputs. No network calls.
- **Resilience tests.** Partial writes, corrupted state, interrupted tasks, chaos scenarios.
- **CLI tests.** Every CLI command has integration tests that invoke the actual command.
- **Concurrency tests.** ThreadPoolExecutor, failure isolation, dependency-aware dispatch.

## Rules for Future Maintainers and Autonomous Agents

1. **Run the full test suite before and after every change.** `python -m pytest tests/ -q`
2. **Never change public behavior to improve typing or style.** Type annotations are additive.
3. **Never add `except Exception: pass`.** Handle explicitly or propagate.
4. **Never use mutable defaults.** Always `None` + initialize.
5. **Never hardcode user paths.** Use `Path.home()` or CLI arguments.
6. **Never overwrite immutable evidence.** If the target exists, fail.
7. **Always use `atomic_write_json()` for state files.** No inline atomic write patterns.
8. **Always import `sha256_file` from `utils`, not `evidence`.** Module dependency direction matters.
9. **Never start v1.1 work in an alpha stabilization pass.** Stay focused.
10. **One coherent commit per release.** No partial releases.
