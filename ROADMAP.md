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

### v0.7.5 — Capability Plugins 🎯 CURRENT
- Pluggable task executors
- External task providers
- Capability discovery
- Extension registry

### v0.7.6 — Resilience Testing
- Chaos tests: runtime interruption, queue corruption, evidence failures, review failures, partial writes, restart recovery
- Runtime must never corrupt queue state

## Quality Standard
Every milestone must improve: Correctness, Reliability, Maintainability, Observability, Documentation, Test Coverage.