# Human Review Queue — Day 2R

Generated from `/tmp/day2r2.db` — no database modifications made.

## Mission Linkage Note

All findings show `UNVERIFIED LINKAGE` for missions. The Core's mission generator
does not populate `originating_finding_id` in persisted mission records.
The relationship between findings and missions exists only by implicit sequential
ordering within the pipeline output, not by any persisted foreign key.

## Allowed Classifications

`USEFUL` | `FALSE_POSITIVE` | `NOT_ACTIONABLE` | `NEEDS_MORE_EVIDENCE` | `DUPLICATE` | `UNKNOWN`

---

## 01. FINDING-001 — flask

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-001` |
| **Repository** | flask |
| **Severity** | high |
| **Category** | Maintainability |
| **Finding** | Large module: app.py (1625 lines) |
| **Affected Path** | `src/flask/app.py` |
| **Evidence** | `[modules] src/flask/app.py — Module has 1625 lines` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 02. FINDING-002 — flask

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-002` |
| **Repository** | flask |
| **Severity** | high |
| **Category** | Maintainability |
| **Finding** | Large module: cli.py (1127 lines) |
| **Affected Path** | `src/flask/cli.py` |
| **Evidence** | `[modules] src/flask/cli.py — Module has 1127 lines` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 03. FINDING-003 — flask

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-003` |
| **Repository** | flask |
| **Severity** | high |
| **Category** | Maintainability |
| **Finding** | Large module: app.py (1013 lines) |
| **Affected Path** | `src/flask/sansio/app.py` |
| **Evidence** | `[modules] src/flask/sansio/app.py — Module has 1013 lines` |
| **Governance Decision** | REJECTED — Duplicate; merged |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 04. FINDING-004 — flask

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-004` |
| **Repository** | flask |
| **Severity** | high |
| **Category** | Maintainability |
| **Finding** | Large module: test_basic.py (1970 lines) |
| **Affected Path** | `tests/test_basic.py` |
| **Evidence** | `[modules] tests/test_basic.py — Module has 1970 lines` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 05. FINDING-005 — flask

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-005` |
| **Repository** | flask |
| **Severity** | high |
| **Category** | Maintainability |
| **Finding** | Large module: test_blueprints.py (1118 lines) |
| **Affected Path** | `tests/test_blueprints.py` |
| **Evidence** | `[modules] tests/test_blueprints.py — Module has 1118 lines` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 06. FINDING-001 — hermes-runtime

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-001` |
| **Repository** | hermes-runtime |
| **Severity** | high |
| **Category** | Maintainability |
| **Finding** | Large module: engineering_analyzer.py (1143 lines) |
| **Affected Path** | `hermes_v01/engineering_analyzer.py` |
| **Evidence** | `[modules] hermes_v01/engineering_analyzer.py — Module has 1143 lines` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 07. FINDING-002 — hermes-runtime

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-002` |
| **Repository** | hermes-runtime |
| **Severity** | high |
| **Category** | Maintainability |
| **Finding** | Large module: mission_runner.py (1013 lines) |
| **Affected Path** | `hermes_v01/mission_runner.py` |
| **Evidence** | `[modules] hermes_v01/mission_runner.py — Module has 1013 lines` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 08. FINDING-003 — hermes-runtime

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-003` |
| **Repository** | hermes-runtime |
| **Severity** | high |
| **Category** | Maintainability |
| **Finding** | Large module: test_resilience.py (1570 lines) |
| **Affected Path** | `tests/test_resilience.py` |
| **Evidence** | `[modules] tests/test_resilience.py — Module has 1570 lines` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 09. FINDING-001 — express

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-001` |
| **Repository** | express |
| **Severity** | medium |
| **Category** | Complexity |
| **Finding** | Large Module: res.render.js |
| **Affected Path** | `test/res.render.js` |
| **Evidence** | `[complexity_signals] test/res.render.js — Module test/res.render.js is 367 lines (threshold: 300)` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 10. FINDING-002 — express

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-002` |
| **Repository** | express |
| **Severity** | medium |
| **Category** | Complexity |
| **Finding** | Large Module: app.render.js |
| **Affected Path** | `test/app.render.js` |
| **Evidence** | `[complexity_signals] test/app.render.js — Module test/app.render.js is 392 lines (threshold: 300)` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 11. FINDING-003 — express

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-003` |
| **Repository** | express |
| **Severity** | medium |
| **Category** | Complexity |
| **Finding** | Large Module: res.download.js |
| **Affected Path** | `test/res.download.js` |
| **Evidence** | `[complexity_signals] test/res.download.js — Module test/res.download.js is 487 lines (threshold: 300)` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 12. FINDING-004 — express

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-004` |
| **Repository** | express |
| **Severity** | medium |
| **Category** | Complexity |
| **Finding** | Large Module: res.jsonp.js |
| **Affected Path** | `test/res.jsonp.js` |
| **Evidence** | `[complexity_signals] test/res.jsonp.js — Module test/res.jsonp.js is 330 lines (threshold: 300)` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 13. FINDING-005 — express

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-005` |
| **Repository** | express |
| **Severity** | medium |
| **Category** | Complexity |
| **Finding** | Large Module: res.location.js |
| **Affected Path** | `test/res.location.js` |
| **Evidence** | `[complexity_signals] test/res.location.js — Module test/res.location.js is 304 lines (threshold: 300)` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 14. FINDING-006 — express

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-006` |
| **Repository** | express |
| **Severity** | medium |
| **Category** | Complexity |
| **Finding** | Large Module: app.param.js |
| **Affected Path** | `test/app.param.js` |
| **Evidence** | `[complexity_signals] test/app.param.js — Module test/app.param.js is 323 lines (threshold: 300)` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 15. FINDING-006 — flask

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-006` |
| **Repository** | flask |
| **Severity** | medium |
| **Category** | Maintainability |
| **Finding** | Large module: ctx.py (540 lines) |
| **Affected Path** | `src/flask/ctx.py` |
| **Evidence** | `[modules] src/flask/ctx.py — Module has 540 lines` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 16. FINDING-007 — flask

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-007` |
| **Repository** | flask |
| **Severity** | medium |
| **Category** | Maintainability |
| **Finding** | Large module: helpers.py (682 lines) |
| **Affected Path** | `src/flask/helpers.py` |
| **Evidence** | `[modules] src/flask/helpers.py — Module has 682 lines` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 17. FINDING-008 — flask

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-008` |
| **Repository** | flask |
| **Severity** | medium |
| **Category** | Maintainability |
| **Finding** | Large module: blueprints.py (692 lines) |
| **Affected Path** | `src/flask/sansio/blueprints.py` |
| **Evidence** | `[modules] src/flask/sansio/blueprints.py — Module has 692 lines` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 18. FINDING-009 — flask

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-009` |
| **Repository** | flask |
| **Severity** | medium |
| **Category** | Maintainability |
| **Finding** | Large module: scaffold.py (792 lines) |
| **Affected Path** | `src/flask/sansio/scaffold.py` |
| **Evidence** | `[modules] src/flask/sansio/scaffold.py — Module has 792 lines` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 19. FINDING-010 — flask

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-010` |
| **Repository** | flask |
| **Severity** | medium |
| **Category** | Maintainability |
| **Finding** | Large module: test_cli.py (703 lines) |
| **Affected Path** | `tests/test_cli.py` |
| **Evidence** | `[modules] tests/test_cli.py — Module has 703 lines` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 20. FINDING-011 — flask

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-011` |
| **Repository** | flask |
| **Severity** | medium |
| **Category** | Maintainability |
| **Finding** | Large module: test_templating.py (532 lines) |
| **Affected Path** | `tests/test_templating.py` |
| **Evidence** | `[modules] tests/test_templating.py — Module has 532 lines` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 21. FINDING-004 — hermes-runtime

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-004` |
| **Repository** | hermes-runtime |
| **Severity** | medium |
| **Category** | Configuration |
| **Finding** | Missing configuration: package.json |
| **Affected Path** | `package.json` |
| **Evidence** | `[configuration] package.json — Missing essential configuration: package.json` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 22. FINDING-005 — hermes-runtime

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-005` |
| **Repository** | hermes-runtime |
| **Severity** | medium |
| **Category** | Maintainability |
| **Finding** | Large module: benchmark_engine.py (633 lines) |
| **Affected Path** | `hermes_v01/benchmark_engine.py` |
| **Evidence** | `[modules] hermes_v01/benchmark_engine.py — Module has 633 lines` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 23. FINDING-006 — hermes-runtime

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-006` |
| **Repository** | hermes-runtime |
| **Severity** | medium |
| **Category** | Maintainability |
| **Finding** | Large module: mission.py (551 lines) |
| **Affected Path** | `hermes_v01/mission.py` |
| **Evidence** | `[modules] hermes_v01/mission.py — Module has 551 lines` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 24. FINDING-007 — hermes-runtime

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-007` |
| **Repository** | hermes-runtime |
| **Severity** | medium |
| **Category** | Maintainability |
| **Finding** | Large module: mission_constraints.py (596 lines) |
| **Affected Path** | `hermes_v01/mission_constraints.py` |
| **Evidence** | `[modules] hermes_v01/mission_constraints.py — Module has 596 lines` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 25. FINDING-008 — hermes-runtime

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-008` |
| **Repository** | hermes-runtime |
| **Severity** | medium |
| **Category** | Maintainability |
| **Finding** | Large module: mission_report.py (569 lines) |
| **Affected Path** | `hermes_v01/mission_report.py` |
| **Evidence** | `[modules] hermes_v01/mission_report.py — Module has 569 lines` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 26. FINDING-009 — hermes-runtime

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-009` |
| **Repository** | hermes-runtime |
| **Severity** | medium |
| **Category** | Maintainability |
| **Finding** | Large module: mission_runner_cli.py (530 lines) |
| **Affected Path** | `hermes_v01/mission_runner_cli.py` |
| **Evidence** | `[modules] hermes_v01/mission_runner_cli.py — Module has 530 lines` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 27. FINDING-010 — hermes-runtime

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-010` |
| **Repository** | hermes-runtime |
| **Severity** | medium |
| **Category** | Maintainability |
| **Finding** | Large module: repo_analyzer.py (599 lines) |
| **Affected Path** | `hermes_v01/repo_analyzer.py` |
| **Evidence** | `[modules] hermes_v01/repo_analyzer.py — Module has 599 lines` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 28. FINDING-011 — hermes-runtime

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-011` |
| **Repository** | hermes-runtime |
| **Severity** | medium |
| **Category** | Maintainability |
| **Finding** | Large module: repo_scanner.py (729 lines) |
| **Affected Path** | `hermes_v01/repo_scanner.py` |
| **Evidence** | `[modules] hermes_v01/repo_scanner.py — Module has 729 lines` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 29. FINDING-012 — hermes-runtime

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-012` |
| **Repository** | hermes-runtime |
| **Severity** | medium |
| **Category** | Maintainability |
| **Finding** | Large module: work_queue.py (623 lines) |
| **Affected Path** | `hermes_v01/work_queue.py` |
| **Evidence** | `[modules] hermes_v01/work_queue.py — Module has 623 lines` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

## 30. FINDING-013 — hermes-runtime

| Field | Value |
|---|---|
| **Finding ID** | `FINDING-013` |
| **Repository** | hermes-runtime |
| **Severity** | medium |
| **Category** | Maintainability |
| **Finding** | Large module: test_concurrent_execution.py (659 lines) |
| **Affected Path** | `tests/test_concurrent_execution.py` |
| **Evidence** | `[modules] tests/test_concurrent_execution.py — Module has 659 lines` |
| **Governance Decision** | APPROVED — Sufficiently evidenced and complete |
| **Draft Mission** | UNVERIFIED LINKAGE |
| **Operator Classification** | `<blank>` |

---

## Summary

- Total findings in database: 84
- Queue size: 30
- Findings with explicit mission linkage: 0/84
- Findings with UNVERIFIED linkage: 84/84
