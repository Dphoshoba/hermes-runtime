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

### v0.7.3 — Observability 🎯 CURRENT
- Structured JSON logs
- Runtime metrics
- Queue metrics
- Execution latency
- Throughput
- Failure classification
- Runtime dashboard/metrics export

### v0.7.4 — Queue Maintenance
- Queue compaction
- Archiving completed work
- Pruning old evidence
- State integrity verification
- Automatic repair of corrupted queue state

### v0.7.5 — Capability Plugins
- Pluggable task executors
- External task providers
- Capability discovery
- Extension registry

### v0.7.6 — Resilience Testing
- Chaos tests: runtime interruption, queue corruption, evidence failures, review failures, partial writes, restart recovery
- Runtime must never corrupt queue state

## Quality Standard
Every milestone must improve: Correctness, Reliability, Maintainability, Observability, Documentation, Test Coverage.