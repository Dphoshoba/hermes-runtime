# Day 4 — Human Operator Classification & Governance Agreement

**Trial ID:** `fa292ba5-321c-4d3f-a370-a33b0cce29c1`
**Completed:** 2026-08-10
**EVOSIA Version:** 1.3.0

---

## Executive Summary

Day 4 achieved two milestone objectives: (1) **integrity verification** of the 30-item review sample against persisted database records — confirmed as **PASS** with zero contamination, zero duplicates, and all counts matching — and (2) **human operator classification** of all 30 items across 5 labels, all persisted with journal events and traceability fields.

**Key findings:**
- **Actionable Finding Yield:** 13.3% (4/30 USEFUL)
- **Needs More Evidence Rate:** 53.3% (16/30) — dominant classification
- **False Positive Rate:** 0.0%
- **Governance Over-Approval Rate:** 83.3% (25/30 approved by governance but classified NOT_ACTIONABLE or NEEDS_MORE_EVIDENCE by human)
- **Human/Governance Exact Agreement:** 13.3% (4/30)

**Day 4 Recommendation:** ✅ PROCEED to Day 5

---

## 1. Integrity Verification (PASS)

| Check | Result |
|-------|--------|
| Original Queue Valid | ✅ PASS |
| All 30 items uniquely identify persisted findings | ✅ PASS |
| No duplicate DB IDs | ✅ PASS |
| No duplicate review items | ✅ PASS |
| Day 2R contamination | ✅ NONE |
| All claimed counts matched | ✅ PASS |
| Unique scan IDs in sample | 3 (hermes-runtime: 22, flask: 6, express: 2) |
| Regression tests added | 11 (all passing) |

**Evidence:** `/tmp/day4_sample.json` (preserved, untouched)

---

## 2. Classification Totals

| Classification | Count | % |
|----------------|-------|---|
| USEFUL | 4 | 13.3% |
| FALSE_POSITIVE | 0 | 0.0% |
| NOT_ACTIONABLE | 9 | 30.0% |
| NEEDS_MORE_EVIDENCE | 16 | 53.3% |
| DUPLICATE | 1 | 3.3% |
| UNKNOWN | 0 | 0.0% |
| **TOTAL** | **30** | **100%** |

---

## 3. Quality Metrics

| Metric | Value | Formula |
|--------|-------|---------|
| Human Review Completion Rate | 100.0% | 30/30 |
| Actionable Finding Yield | 13.3% | USEFUL / total_reviewed |
| Not Actionable Rate | 30.0% | NOT_ACTIONABLE / total_reviewed |
| Needs More Evidence Rate | 53.3% | NEEDS_MORE_EVIDENCE / total_reviewed |
| False Positive Rate | 0.0% | FALSE_POSITIVE / total_reviewed |
| Duplicate Rate | 3.3% | DUPLICATE / total_reviewed |
| Observation Support Rate | 100.0% | (all findings have supporting evidence) |
| Mission Linkage Coverage | 0.0% | 0/30 (Core limitation) |

---

## 4. Governance Agreement Analysis

### Cross-Tabulation: Governance Decision × Human Classification

| | USEFUL | NOT_ACTIONABLE | NEEDS_MORE_EVIDENCE | DUPLICATE | FALSE_POSITIVE |
|---|---|---|---|---|---|
| **APPROVED** | 4 | 9 | 16 | 0 | 0 |
| **REJECTED** | 0 | 0 | 0 | 1 | 0 |

### Agreement Metrics

| Metric | Value |
|--------|-------|
| Governance Approval Rate | 96.7% (29/30) |
| Governance Rejection Rate | 3.3% (1/30) |
| Human/Governance Exact Agreement | 13.3% (4/30) |
| Governance Over-Approval Rate | 83.3% (25/30) |
| Governance Under-Approval Rate | 0.0% (0/30) |
| Human Uncertainty Rate | 53.3% (16/30) |

**Interpretation:** Governance approves nearly everything (96.7%), while human review finds only 13.3% actionable. The 83.3% over-approval rate means governance is systematically lenient relative to human judgment. No cases of governance rejecting what humans found useful (0% under-approval). The 53.3% human uncertainty rate indicates most findings require more evidence to classify confidently.

---

## 5. Context Analysis

### By File Context

| Context | Total | USEFUL | NOT_ACTIONABLE | NEEDS_MORE_EVIDENCE | DUPLICATE |
|---------|-------|--------|----------------|---------------------|-----------|
| PRODUCTION | 15 | 4 (26.7%) | 0 | 10 (66.7%) | 1 (6.7%) |
| TEST | 13 | 0 | 9 (69.2%) | 4 (30.8%) | 0 |
| CONFIGURATION | 2 | 0 | 0 | 2 (100%) | 0 |

**Interpretation:** All USEFUL findings are in PRODUCTION code. TEST files dominate NOT_ACTIONABLE (9/13 = 69.2%). CONFIGURATION findings uniformly need more evidence.

---

## 6. Threshold Tier Analysis

| Tier | Total | USEFUL | NOT_ACTIONABLE | NEEDS_MORE_EVIDENCE | DUPLICATE |
|------|-------|--------|----------------|---------------------|-----------|
| NEAR_THRESHOLD | 1 | 0 | 1 | 0 | 0 |
| MODERATE_EXCEEDANCE | 7 | 0 | 2 | 5 | 0 |
| HIGH_EXCEEDANCE | 17 | 3 | 6 | 7 | 1 |
| EXTREME_EXCEEDANCE | 3 | 1 | 0 | 2 | 0 |
| NO_THRESHOLD | 2 | 0 | 0 | 2 | 0 |

**Interpretation:** HIGH_EXCEEDANCE is the most populated tier (17/30), with mixed outcomes. EXTREME_EXCEEDANCE yielded 1 USEFUL and 2 NEEDS_MORE_EVIDENCE (no auto-classification). MODERATE_EXCEEDANCE is dominated by NEEDS_MORE_EVIDENCE (5/7).

---

## 7. Journal Event Verification

- **Total `finding.reviewed` events:** 30
- **All events have:** finding_id, classification, operator, trial_id, adjudication_id
- **All events have:** payload_sha256 present
- **All events stage:** `human_review`
- **All events trial_id:** matches `fa292ba5-321c-4d3f-a370-a33b0cce29c1`

---

## 8. Snapshot

| Field | Value |
|-------|-------|
| Snapshot ID | `d4b3669a-a0ba-46ee-9eb7-053c94211b3c` |
| Content Hash | `537796dd3d124699...` |
| Status | ACTIVE |
| Date | 2026-08-10 |
| Label | Day 4 — Human Classification & Governance Agreement |

---

## 9. Safety

| Check | Status |
|-------|--------|
| Safety Violations | 0 |
| Friction Records | 0 |
| Status | PASS |

---

## 10. Regression Test Coverage

| Test Suite | Tests | Status |
|------------|-------|--------|
| Human Review (`tests/test_human_review.py`) | 52 | ✅ PASS |
| Enterprise (`tests/test_enterprise.py`) | 77 | ✅ PASS |
| Frontend (`enterprise-ui/src/`) | 36 | ✅ PASS |
| **Total** | **165** | ✅ ALL PASS |

---

## 11. Known Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| Mission Linkage Coverage = 0% | Core doesn't populate `originating_finding_id` | Acknowledged; no mitigation available in this trial |
| Governance over-approval = 83.3% | Governance decisions too lenient for operational use | Day 5 should investigate governance threshold tuning |
| Human uncertainty = 53.3% | Most findings lack sufficient evidence for confident classification | Consider evidence enrichment in Day 5-6 |

---

## Day 4 Recommendation

✅ **PROCEED to Day 5**

**Rationale:**
1. Integrity verification passed with zero issues
2. All 30 classifications persisted with full audit trail
3. Zero false positives — the pipeline produces no garbage findings
4. 83.3% governance over-approval is a known, quantified calibration gap (not a failure)
5. 53.3% NEEDS_MORE_EVIDENCE rate suggests evidence enrichment should be a Day 5-6 priority
6. 165/165 tests passing — no regressions

**Day 5 Focus Areas:**
- Investigate governance threshold calibration (why 83.3% over-approval?)
- Begin evidence enrichment for NEEDS_MORE_EVIDENCE items
- Add additional repositories to broaden validation
- Track whether governance agreement improves with human baseline data
