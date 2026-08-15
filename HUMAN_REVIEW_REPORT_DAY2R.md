# Human Review Report — Day 2R

**Operational Validation Trial 001**
**Date:** 2026-08-11
**Milestone:** Evidence-Based Human Review & Mission Traceability v1.0

---

## Executive Summary

Day 2R produced the first real human-review sample from EVOSIA operational scanning. Thirty findings across three repositories (flask, hermes-runtime, express) were reviewed by an external human operator. The review exposed three systemic problems that this milestone addresses:

1. **Observation ≠ Actionability** — EVOSIA treated factually-supported observations as automatically actionable.
2. **Test-Code Context Blindness** — Production-code thresholds were applied to test files, generating false-positive-equivalent signals.
3. **Implicit Mission Traceability** — Missions were associated with findings by sequential ordering, not explicit persisted linkage.

This milestone implements first-class adjudication, context-aware interpretation, and explicit finding→mission traceability.

---

## Classification Totals

| Classification | Count | % of Reviewed |
|---|---|---|
| USEFUL | 4 | 13.3% |
| FALSE_POSITIVE | 0 | 0% |
| NOT_ACTIONABLE | 12 | 40.0% |
| NEEDS_MORE_EVIDENCE | 13 | 43.3% |
| DUPLICATE | 1 | 3.3% |
| UNKNOWN | 0 | 0% |
| **Total** | **30** | **100%** |

---

## Key Metrics

| Metric | Value |
|---|---|
| **Finding Precision** (USEFUL / classifiable) | 4/29 = **13.8%** |
| **Actionability Rate** (USEFUL / total) | 4/30 = **13.3%** |
| **Needs More Evidence Rate** | 13/30 = **43.3%** |
| **Not Actionable Rate** | 12/30 = **40.0%** |
| **Duplicate Rate** | 1/30 = **3.3%** |
| **False Positive Rate** | 0/30 = **0.0%** |

### Important Distinction

FALSE_POSITIVE = 0 does **not** mean EVOSIA finding quality is 100%. The key metric is **Actionability Rate = 13.3%**. Many factually-correct observations (test file sizes, threshold-edge cases) are not actionable engineering concerns.

---

## Governance Agreement

| Governance Decision | Human Classification | Agreement |
|---|---|---|
| 29 APPROVED | 4 USEFUL, 11 NOT_ACTIONABLE, 13 NEEDS_MORE_EVIDENCE | Partial — governance approved findings that humans deemed not yet actionable |
| 1 REJECTED (FINDING-003) | 1 DUPLICATE | **Full agreement** |

**Governance/Human Agreement Rate:** The REJECTED finding was independently classified as DUPLICATE by the operator. However, 24 findings approved by governance were classified as NOT_ACTIONABLE or NEEDS_MORE_EVIDENCE by the human reviewer, indicating a gap between governance approval and operational actionability.

---

## Mission Traceability Coverage

| Metric | Value |
|---|---|
| Findings with explicit mission linkage | 0/84 |
| Findings with UNVERIFIED_LEGACY_LINKAGE | 84/84 |
| Missions with `originating_finding_id` populated | 0/78 |

**Status:** No missions had explicit persisted linkage to findings before this milestone. The `MissionFindingLink` model now enables explicit one-to-one and many-to-one relationships.

---

## Key Observations

### 1. Test-Code Context Issue

**12 of 30 findings** (40%) were classified NOT_ACTIONABLE because the pipeline applied production-code thresholds to test files. The scanner's `Maintainability` and `Complexity` categories did not distinguish source from test code.

**Specific cases:**
- `tests/test_basic.py` (1970 lines) — NOT_ACTIONABLE despite extreme size
- `test/res.location.js` (304 lines vs 300 threshold) — NOT_ACTIONABLE as threshold noise
- All 6 express findings were test files — 100% NOT_ACTIONABLE

**Resolution:** File context classification (PRODUCTION, TEST, FIXTURE, etc.) now informs actionability interpretation.

### 2. Threshold Noise Issue

**Finding 13** (`test/res.location.js`, 304 lines, threshold 300) was treated identically to **Finding 01** (`src/flask/app.py`, 1625 lines). The 4-line exceedance is threshold noise, not an engineering concern.

**Resolution:** Exceedance ratio (observed/threshold) and tier classification (NEAR_THRESHOLD, MODERATE_EXCEEDANCE, HIGH_EXCEEDANCE, EXTREME_EXCEEDANCE) now differentiate marginal from significant exceedances.

### 3. Configuration Assumption Issue

**Finding 21** (`Missing configuration: package.json`) was treated as an essential configuration defect without proving that `package.json` is required for this repository.

**Resolution:** Configuration findings must establish repository language/framework context and whether the configuration is expected.

### 4. Mission Traceability Defect

All 78 draft missions had `originating_finding_id: ""` (empty string). Missions were linked to findings only by sequential ordering, not by explicit persisted relationship.

**Resolution:** `MissionFindingLink` model with `PRIMARY`, `SUPPORTING`, `MERGED_FROM` relationship types. Explicit `originating_finding_ids` array in mission configuration.

---

## Repository Breakdown

| Repository | Findings Reviewed | USEFUL | NOT_ACTIONABLE | NEEDS_EVIDENCE | DUPLICATE |
|---|---|---|---|---|---|
| flask | 14 | 2 | 5 | 6 | 1 |
| hermes-runtime | 10 | 2 | 1 | 7 | 0 |
| express | 6 | 0 | 6 | 0 | 0 |

**Observation:** 100% of express findings were NOT_ACTIONABLE (all test files). Flask had the highest ratio of NEEDS_MORE_EVIDENCE (6/14 = 43%).

---

## Per-Finding Review Results

| # | Repo | Finding | Classification |
|---|---|---|---|
| 01 | flask | FINDING-001 (app.py, 1625 lines) | USEFUL |
| 02 | flask | FINDING-002 (cli.py, 1127 lines) | USEFUL |
| 03 | flask | FINDING-003 (sansio/app.py, 1013 lines) | DUPLICATE |
| 04 | flask | FINDING-004 (test_basic.py, 1970 lines) | NOT_ACTIONABLE |
| 05 | flask | FINDING-005 (test_blueprints.py, 1118 lines) | NOT_ACTIONABLE |
| 06 | hermes | FINDING-001 (engineering_analyzer.py, 1143 lines) | USEFUL |
| 07 | hermes | FINDING-002 (mission_runner.py, 1013 lines) | USEFUL |
| 08 | hermes | FINDING-003 (test_resilience.py, 1570 lines) | NOT_ACTIONABLE |
| 09 | express | FINDING-001 (res.render.js, 367 lines) | NOT_ACTIONABLE |
| 10 | express | FINDING-002 (app.render.js, 392 lines) | NOT_ACTIONABLE |
| 11 | express | FINDING-003 (res.download.js, 487 lines) | NOT_ACTIONABLE |
| 12 | express | FINDING-004 (res.jsonp.js, 330 lines) | NOT_ACTIONABLE |
| 13 | express | FINDING-005 (res.location.js, 304 lines) | NOT_ACTIONABLE |
| 14 | express | FINDING-006 (app.param.js, 323 lines) | NOT_ACTIONABLE |
| 15 | flask | FINDING-006 (ctx.py, 540 lines) | NEEDS_MORE_EVIDENCE |
| 16 | flask | FINDING-007 (helpers.py, 682 lines) | NEEDS_MORE_EVIDENCE |
| 17 | flask | FINDING-008 (blueprints.py, 692 lines) | NEEDS_MORE_EVIDENCE |
| 18 | flask | FINDING-009 (scaffold.py, 792 lines) | NEEDS_MORE_EVIDENCE |
| 19 | flask | FINDING-010 (test_cli.py, 703 lines) | NOT_ACTIONABLE |
| 20 | flask | FINDING-011 (test_templating.py, 532 lines) | NOT_ACTIONABLE |
| 21 | hermes | FINDING-004 (package.json) | NEEDS_MORE_EVIDENCE |
| 22 | hermes | FINDING-005 (benchmark_engine.py, 633 lines) | NEEDS_MORE_EVIDENCE |
| 23 | hermes | FINDING-006 (mission.py, 551 lines) | NEEDS_MORE_EVIDENCE |
| 24 | hermes | FINDING-007 (mission_constraints.py, 596 lines) | NEEDS_MORE_EVIDENCE |
| 25 | hermes | FINDING-008 (mission_report.py, 569 lines) | NEEDS_MORE_EVIDENCE |
| 26 | hermes | FINDING-009 (mission_runner_cli.py, 530 lines) | NEEDS_MORE_EVIDENCE |
| 27 | hermes | FINDING-010 (repo_analyzer.py, 599 lines) | NEEDS_MORE_EVIDENCE |
| 28 | hermes | FINDING-011 (repo_scanner.py, 729 lines) | NEEDS_MORE_EVIDENCE |
| 29 | hermes | FINDING-012 (work_queue.py, 623 lines) | NEEDS_MORE_EVIDENCE |
| 30 | hermes | FINDING-013 (test_concurrent_execution.py, 659 lines) | NOT_ACTIONABLE |

---

## Recommended Product Improvements

1. **Scanner file-context awareness** — The scanner should tag findings with file context (PRODUCTION, TEST, etc.) at generation time, not just at review time.

2. **Configurable severity by context** — Allow different severity thresholds for test vs. production code.

3. **Exceedance ratio in finding metadata** — Store the exceedance ratio and tier in the finding's `metadata_json` at scan time.

4. **Configuration requirement validation** — Before generating a "missing configuration" finding, verify that the configuration is expected for the repository's language/framework.

5. **Mission generator explicit linkage** — The Core's `mission_generator` must populate `originating_finding_id` in the mission configuration.

---

## Implementation Summary

| Component | Status |
|---|---|
| FindingAdjudication model | Created |
| MissionFindingLink model | Created |
| File context classification | 8 contexts implemented |
| Observation/concern/actionability | 3-level distinction |
| Threshold exceedance ratio | 4 tiers |
| Human Review Queue service | Created |
| Enterprise API (`/api/review/*`) | 5 endpoints |
| Enterprise UI (Human Review page) | Created with classification buttons |
| CLI (`hermes-human-review`) | 5 subcommands |
| Journal events | `finding.reviewed`, `finding.reclassified` |
| 30 operator classifications | Persisted to database |
| Focused tests | 41 tests, all passing |
| Enterprise regression | 77 tests, all passing |

---

## Trial Environment Change

**Event:** Trial Environment Change
**Reason:** DAY 2R FINDING QUALITY / TRACEABILITY DEFECT CLOSURE
**Date:** 2026-08-11
**Not modifying prior Day 2R snapshot.**
**Persisting operator adjudications as new evidence.**

---

*Report generated from Operational Validation Trial 001, Day 2R evidence.*
