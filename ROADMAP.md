# Hermes Runtime Roadmap

## Program III v0.6 — Integrated Runtime ✅ COMPLETE
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
  - Fields: mission_id, mission_title, status, duration, tasks_planned/completed/failed/skipped
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

## Quality Standard
Every milestone must improve: Correctness, Reliability, Maintainability, Observability, Documentation, Test Coverage.