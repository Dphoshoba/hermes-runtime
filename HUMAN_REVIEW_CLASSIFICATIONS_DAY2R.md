# Human Review Queue — Day 2R — Operator Classifications

Trial: 001
Date: 2026-08-11
Operator: David (external human reviewer)

## Classifications

| # | Repository | Finding ID | Classification | Operator Note |
|---|---|---|---|---|
| 01 | flask | FINDING-001 | **USEFUL** | Very large production module. Strong maintainability signal; warrants deeper analysis before recommending refactor. |
| 02 | flask | FINDING-002 | **USEFUL** | Very large production module. Worth investigation, though size alone does not prove poor design. |
| 03 | flask | FINDING-003 | **DUPLICATE** | Governance already rejected it as 'Duplicate; merged.' |
| 04 | flask | FINDING-004 | **NOT_ACTIONABLE** | Large test suite is not inherently a maintainability defect. Test files need different thresholds/rules. |
| 05 | flask | FINDING-005 | **NOT_ACTIONABLE** | Same issue: line count alone is insufficient for a test-file refactor recommendation. |
| 06 | hermes-runtime | FINDING-001 | **USEFUL** | Core production module is exceptionally large; useful candidate for deeper structural analysis. |
| 07 | hermes-runtime | FINDING-002 | **USEFUL** | Large core runtime module. Worth deeper investigation. |
| 08 | hermes-runtime | FINDING-003 | **NOT_ACTIONABLE** | Test-file size alone should not trigger the same maintainability rule as production code. |
| 09 | express | FINDING-001 | **NOT_ACTIONABLE** | Test file and only modestly above generic 300-line threshold. |
| 10 | express | FINDING-002 | **NOT_ACTIONABLE** | Same: test context makes generic module-size threshold weak evidence. |
| 11 | express | FINDING-003 | **NOT_ACTIONABLE** | Size alone doesn't establish harmful complexity in a test suite. |
| 12 | express | FINDING-004 | **NOT_ACTIONABLE** | Only 30 lines over threshold and is test code. Weak operational signal. |
| 13 | express | FINDING-005 | **NOT_ACTIONABLE** | Four lines above threshold. This is threshold noise rather than convincing engineering evidence. |
| 14 | express | FINDING-006 | **NOT_ACTIONABLE** | Test module only slightly over threshold; insufficient reason for action. |
| 15 | flask | FINDING-006 | **NEEDS_MORE_EVIDENCE** | Production module, but 540 lines alone doesn't establish problematic complexity. Need functions/classes/coupling data. |
| 16 | flask | FINDING-007 | **NEEDS_MORE_EVIDENCE** | Plausible concern, but file length alone doesn't tell us whether responsibilities are poorly separated. |
| 17 | flask | FINDING-008 | **NEEDS_MORE_EVIDENCE** | Worth investigating, but requires structural evidence beyond LOC. |
| 18 | flask | FINDING-009 | **NEEDS_MORE_EVIDENCE** | Stronger size signal, but still needs complexity/responsibility evidence before action. |
| 19 | flask | FINDING-010 | **NOT_ACTIONABLE** | Generic production-code size threshold should not automatically govern tests. |
| 20 | flask | FINDING-011 | **NOT_ACTIONABLE** | Same test-context problem. |
| 21 | hermes-runtime | FINDING-004 | **NEEDS_MORE_EVIDENCE** | Must verify whether package.json is actually required for this repository. 'Missing' does not automatically mean 'missing essential configuration.' |
| 22 | hermes-runtime | FINDING-005 | **NEEDS_MORE_EVIDENCE** | Production code and potentially useful signal, but LOC alone is insufficient. |
| 23 | hermes-runtime | FINDING-006 | **NEEDS_MORE_EVIDENCE** | Need responsibility/function/class complexity before recommending change. |
| 24 | hermes-runtime | FINDING-007 | **NEEDS_MORE_EVIDENCE** | Plausible maintainability concern but not proven by size alone. |
| 25 | hermes-runtime | FINDING-008 | **NEEDS_MORE_EVIDENCE** | Need structural evidence. |
| 26 | hermes-runtime | FINDING-009 | **NEEDS_MORE_EVIDENCE** | CLI modules can legitimately contain substantial command wiring. Need additional evidence. |
| 27 | hermes-runtime | FINDING-010 | **NEEDS_MORE_EVIDENCE** | Potentially useful, but require complexity/coupling evidence. |
| 28 | hermes-runtime | FINDING-011 | **NEEDS_MORE_EVIDENCE** | Strong candidate for deeper analysis, not yet enough evidence for a refactor mission. |
| 29 | hermes-runtime | FINDING-012 | **NEEDS_MORE_EVIDENCE** | Need structural/concurrency complexity evidence, not merely LOC. |
| 30 | hermes-runtime | FINDING-013 | **NOT_YET_CLASSIFIED** | Operator note was truncated/missing in submission. |

## Metrics

- Total findings reviewed: 30
- USEFUL: 4
- FALSE_POSITIVE: 0
- NOT_ACTIONABLE: 11
- NEEDS_MORE_EVIDENCE: 13
- DUPLICATE: 1
- UNKNOWN: 0
- NOT_YET_CLASSIFIED: 1

- **Finding Precision** (USEFUL / classifiable): 4/28 = 14.3%
  - Excludes DUPLICATE (1) and NOT_YET_CLASSIFIED (1) from denominator
- **Operator Acceptance Rate** (USEFUL / decisive): 4/28 = 14.3%
  - Decisive = USEFUL + NOT_ACTIONABLE + FALSE_POSITIVE + NEEDS_MORE_EVIDENCE

## Notes

- Item 03 (FINDING-003, flask sansio/app.py) was DUPLICATE per governance REJECTED decision.
- Item 30 (FINDING-013, hermes test_concurrent_execution.py) operator note was truncated in submission; marked NOT_YET_CLASSIFIED pending clarification.
- NEEDS_MORE_EVIDENCE (13 items) means: plausible signal but insufficient evidence for action. Not a rejection.
- NOT_ACTIONABLE (12 items) means: evidence does not support an action. These are effectively false-positive-equivalent for mission generation.