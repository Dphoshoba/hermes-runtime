# Hermes Runtime Roadmap

## Program III v0.6 — Integrated Runtime ✅ COMPLETE
- Work Queue CLI (`hermes-queue`)
- Supervisor → Queue integration (remediation tasks)
- Evidence → Queue integration (`--task-id --work-queue`)
- Reviewer → Queue integration (`--task-id --work-queue`)
- Runtime State projection includes queue summary
- Runtime Orchestrator (`hermes-runtime --task-id/--next --work-queue`)
- End-to-end validation: full queue lifecycle verified

## Program III v0.7 — Autonomous Runtime 🔄 IN PROGRESS

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

## Quality Standard
Every milestone must improve: Correctness, Reliability, Maintainability, Observability, Documentation, Test Coverage.