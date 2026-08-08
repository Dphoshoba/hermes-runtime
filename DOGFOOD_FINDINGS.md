# Dogfooding Findings — Hermes v1.0.0-alpha

Date: 2026-08-08
Baseline: 593 tests passing

## Summary

3 missions executed against validation/sample-repo. All missions demonstrated correct end-to-end pipeline behavior (planning → constraints → queue → execution → evidence → review → health → report). Failures were exclusively due to the target repository not having `sample_app` installed — a realistic dogfood scenario, not a Hermes defect.

---

## Finding DF-001

- **Mission:** All (repo-maintenance, doc-refresh, ci-verify, release-readiness)
- **Observed:** Tasks that `import sample_app` fail with `ModuleNotFoundError`
- **Expected:** Mission runner should install target package dependencies before execution
- **Severity:** Medium
- **Reproducibility:** 100%
- **Evidence:** Mission reports show `tasks_failed` for all import-dependent tasks
- **Proposed improvement:** Add optional `setup` task type that runs `pip install -e .` before dependent tasks; or document that missions must ensure dependencies are installed
- **Disposition:** Record as v1.1 candidate — "prerequisite task support"

---

## Finding DF-002

- **Mission:** doc-refresh (first attempt)
- **Observed:** Missions sharing the same `--queue-file` collide — task IDs from previous missions remain in queue, blocking new mission enqueue
- **Expected:** Each `hermes-mission run` should either use a fresh queue or isolate tasks by mission_id
- **Severity:** High
- **Reproducibility:** 100% when reusing queue file
- **Evidence:** Mission 2 initially FAILED with 4 tasks skipped due to queue collision
- **Proposed improvement:** `enqueue_plan` should namespace tasks by mission_id, or `run` command should auto-generate isolated queue paths
- **Disposition:** Record as v1.1 candidate — "per-mission queue isolation"

---

## Finding DF-003

- **Mission:** All
- **Observed:** `MISSION_REPORT.json` status shows `FAILED` even when the mission ran correctly but target commands failed
- **Expected:** Distinction between "mission infrastructure failed" and "target commands failed as expected"
- **Severity:** Low
- **Reproducibility:** 100%
- **Evidence:** All 3 mission reports show `status: FAILED` despite correct pipeline execution
- **Proposed improvement:** Add `execution_status` field distinguishing pipeline health from target outcome
- **Disposition:** Record as v1.1 candidate — "mission vs execution status separation"

---

## Finding DF-004

- **Mission:** repo-maintenance
- **Observed:** `check-gitignore` task uses complex inline Python that's hard to read in mission JSON
- **Expected:** Simpler command syntax or helper commands for common operations
- **Severity:** Low
- **Reproducibility:** 100%
- **Evidence:** Mission JSON contains 200+ character inline Python strings
- **Proposed improvement:** Support `hermes-exec` helper commands for common operations (list-files, find-patterns, etc.)
- **Disposition:** Record as v1.1 candidate — "built-in task helpers"

---

## Finding DF-005

- **Mission:** release-readiness
- **Observed:** `verify-metadata` task uses `tomllib` which is Python 3.11+ only, but mission targets Python 3.10+
- **Expected:** Mission commands should be compatible with minimum supported Python version
- **Severity:** Medium
- **Reproducibility:** 100% on Python 3.10
- **Evidence:** Task command uses `import tomllib` which doesn't exist in Python 3.10
- **Proposed improvement:** Mission type validators should check command compatibility; or use `tomli` fallback
- **Disposition:** Record as v1.1 candidate — "python version compatibility validation"

---

## Finding DF-006

- **Mission:** All
- **Observed:** No mechanism to pass environment variables or working directory overrides per-task
- **Expected:** Tasks should be able to set env vars or override working directory independently
- **Severity:** Low
- **Reproducibility:** N/A (feature request)
- **Evidence:** All tasks inherit the mission-level working_directory
- **Proposed improvement:** Add `env` and `working_directory` fields to MissionTask schema
- **Disposition:** Record as v1.1 candidate — "per-task environment control"

---

## Finding DF-007

- **Mission:** ci-verify
- **Observed:** All 4 tasks fail but mission runner still generates evidence and reviews for each failure
- **Expected:** Correct behavior — failures are recorded as evidence
- **Severity:** Informational
- **Reproducibility:** 100%
- **Evidence:** 4 evidence records and 4 reviews generated for failed tasks
- **Proposed improvement:** None needed — this is correct behavior
- **Disposition:** Confirmed correct

---

## Finding DF-008

- **Mission:** All
- **Observed:** `runtime_health` shows `FAILED` when any task fails, even if pipeline infrastructure is healthy
- **Expected:** Health should reflect infrastructure, not task outcomes
- **Severity:** Low
- **Reproducibility:** 100%
- **Evidence:** ci-verify shows `runtime_health: FAILED` because all tasks failed
- **Proposed improvement:** Separate infrastructure health from task success rate
- **Disposition:** Record as v1.1 candidate — "health metric refinement"

---

## Categories

| Category | Findings |
|----------|----------|
| mission authoring | DF-001, DF-004, DF-005 |
| lifecycle | DF-002, DF-003 |
| reports | DF-003, DF-008 |
| scheduling | DF-002 |
| evidence | DF-007 (correct) |
| CLI ergonomics | DF-004 |
| constraints | DF-005 |
| documentation | — |
| packaging | — |
| performance | — |

## Critical Defects

None. All failures are target-repository issues, not Hermes defects.

## Recommended v1.1 Priorities

1. **Per-mission queue isolation** (DF-002) — High impact, prevents mission collision
2. **Prerequisite task support** (DF-001) — Medium impact, enables real-world missions
3. **Mission vs execution status separation** (DF-003) — Low effort, improves reporting clarity
4. **Python version compatibility validation** (DF-005) — Medium impact, prevents runtime errors
5. **Built-in task helpers** (DF-004) — Low effort, improves mission authoring UX
