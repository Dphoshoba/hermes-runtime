# EVOSIA — 7-DAY OPERATIONAL VALIDATION

## DAY 6 — BLIND HOLDOUT EVALUATION

**Trial:** Operational Validation Trial 001
**Status:** ACTIVE
**EVOSIA Version:** 1.3.0
**EVOSIA Commit:** e3583c8
**Completed:** 2026-08-11

---

## EXECUTIVE SUMMARY

Day 6 ran 9 governance variants against a blind 16-item holdout with frozen human classifications.

**Critical Finding:** Variant E (best on calibration at 66.7%) collapses to 12.5% on holdout (-54.2% delta). The holdout exposed that 7/8 PRODUCTION findings have no exceedance_ratio. Without this input, Variant E falls through to APPROVED — the same unsafe default as production governance.

**Best Generalizing Variant:** VARIANT H (file_context + exceedance_ratio + confidence) — 66.7% calibration, 56.2% holdout, -10.5% delta. But: converges with D, F, G, I on holdout due to uniform confidence=0.5.

**Root Cause:** C. unsafe default approval semantics. The current governance defaults to APPROVED when no condition matches. All 16 holdout findings hit this default. Changing default to NEEDS_MORE_EVIDENCE (Variant I) achieves 56.2% with zero over-approvals.

**Recommendation:** MORE_VALIDATION_REQUIRED. Holdout is too small (16 items), has no USEFUL findings, and no CONFIGURATION findings. Cannot validate useful-recall or config-context handling.

---

## 1. HOLDOUT COMPOSITION

| Context | Count |
|---------|-------|
| PRODUCTION | 8 |
| TEST | 8 |
| **Total** | **16** |

| Human Classification | Count |
|---------------------|-------|
| NEEDS_MORE_EVIDENCE | 9 |
| NOT_ACTIONABLE | 7 |
| USEFUL | 0 |
| DUPLICATE | 0 |

**Critical gap:** No USEFUL findings in holdout. Useful-recall is unmeasurable.

---

## 2. VARIANT METRICS (Holdout — 16 items)

| Variant | Exact | Over | Under | NME Acc | UsefulRec | FalseU | NA_Handl | APR | REJ | NME | DEF | GenDelta | Status |
|---------|-------|------|-------|---------|-----------|--------|----------|-----|-----|-----|-----|----------|--------|
| A_CONTROL | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 16 | 0.0% | 16 | 0 | 0 | 0 | -14.8% | BAD |
| B_FILECTX | 6.2% | 50.0% | 0.0% | 11.1% | 0.0% | 8 | 100.0% | 8 | 0 | 8 | 0 | -30.8% | OVERFIT |
| C_EXCEED | 12.5% | 43.8% | 0.0% | 22.2% | 0.0% | 7 | 100.0% | 7 | 0 | 9 | 0 | -35.6% | OVERFIT |
| D_CONF | 56.2% | 0.0% | 0.0% | 100.0% | 0.0% | 0 | 100.0% | 0 | 0 | 16 | 0 | +4.3% | PASS |
| E_CTX_EXCEED | 12.5% | 43.8% | 0.0% | 22.2% | 0.0% | 7 | 100.0% | 7 | 0 | 9 | 0 | -54.2% | OVERFIT |
| F_CTX_CONF | 56.2% | 0.0% | 0.0% | 100.0% | 0.0% | 0 | 100.0% | 0 | 0 | 16 | 0 | +4.3% | PASS |
| G_EXCEED_CONF | 56.2% | 0.0% | 0.0% | 100.0% | 0.0% | 0 | 100.0% | 0 | 0 | 16 | 0 | +4.3% | PASS |
| H_ALL | 56.2% | 0.0% | 0.0% | 100.0% | 0.0% | 0 | 100.0% | 0 | 0 | 16 | 0 | -10.5% | PASS |
| I_DEFAULT_NME | 56.2% | 0.0% | 0.0% | 100.0% | 0.0% | 0 | 100.0% | 0 | 0 | 16 | 0 | +4.3% | PASS |

**Key:** APR=APPROVED count, REJ=REJECTED count, NME=NEEDS_MORE_EVIDENCE count, DEF=DEFERRED count, FalseU=false USEFUL rejections, GenDelta=Holdout Exact - Calibration Exact.

**Generalization Delta > +20% flagged as OVERFIT. Delta < -10% flagged as BAD.**

---

## 3. 16-ROW COMPARISON TABLE

| # | UUID | Repo | Module | CTX | RATIO | HUMAN | A | B | C | D | E | F | G | H | I |
|---|------|------|--------|-----|-------|-------|---|---|---|---|---|---|---|---|---|
| 1 | 0786261a | hermes-runtime | hermes_v01/metrics_cli.py | PRODUCTION | None | NEEDS_MORE_EVIDENCE | APR | APR | APR | NME | APR | NME | NME | NME | NME |
| 2 | 1ffc0671 | hermes-runtime | hermes_v01/work_queue_cli.py | PRODUCTION | None | NEEDS_MORE_EVIDENCE | APR | APR | APR | NME | APR | NME | NME | NME | NME |
| 3 | 2529875f | express | test/express.text.js | TEST | 1.89 | NOT_ACTIONABLE | APR | NME | NME | NME | NME | NME | NME | NME | NME |
| 4 | 33152366 | hermes-runtime | hermes_v01/benchmark_cli.py | PRODUCTION | None | NEEDS_MORE_EVIDENCE | APR | APR | APR | NME | APR | NME | NME | NME | NME |
| 5 | 3ca62036 | express | test/express.static.js | TEST | 2.72 | NOT_ACTIONABLE | APR | NME | NME | NME | NME | NME | NME | NME | NME |
| 6 | 406bd0f0 | express | test/app.router.js | TEST | 4.06 | NEEDS_MORE_EVIDENCE | APR | NME | NME | NME | NME | NME | NME | NME | NME |
| 7 | 44ec7870 | hermes-runtime | hermes_v01/utils.py | PRODUCTION | None | NEEDS_MORE_EVIDENCE | APR | APR | APR | NME | APR | NME | NME | NME | NME |
| 8 | 51dd146c | hermes-runtime | hermes_v01/health_cli.py | PRODUCTION | None | NEEDS_MORE_EVIDENCE | APR | APR | APR | NME | APR | NME | NME | NME | NME |
| 9 | 578e37c7 | hermes-runtime | tests/test_planner_integration.py | TEST | 1.77 | NOT_ACTIONABLE | APR | NME | NME | NME | NME | NME | NME | NME | NME |
| 10 | 758f726c | hermes-runtime | tests/test_repo_intelligence.py | TEST | 1.89 | NOT_ACTIONABLE | APR | NME | NME | NME | NME | NME | NME | NME | NME |
| 11 | 807252d7 | hermes-runtime | tests/test_mission_types.py | TEST | 1.79 | NOT_ACTIONABLE | APR | NME | NME | NME | NME | NME | NME | NME | NME |
| 12 | 87758338 | flask | tests/test_cli.py | TEST | 2.34 | NOT_ACTIONABLE | APR | NME | NME | NME | NME | NME | NME | NME | NME |
| 13 | ce9cccbf | flask | examples/celery/src/task_app/__init__.py | PRODUCTION | None | NEEDS_MORE_EVIDENCE | APR | APR | APR | NME | APR | NME | NME | NME | NME |
| 14 | d64f9c8c | hermes-runtime | hermes_v01/python_scanner.py | PRODUCTION | None | NEEDS_MORE_EVIDENCE | APR | APR | APR | NME | APR | NME | NME | NME | NME |
| 15 | dde94f1d | flask | src/flask/helpers.py | PRODUCTION | 2.27 | NEEDS_MORE_EVIDENCE | APR | APR | NME | NME | NME | NME | NME | NME | NME |
| 16 | fd49f9a0 | express | test/express.raw.js | TEST | 1.71 | NOT_ACTIONABLE | APR | NME | NME | NME | NME | NME | NME | NME | NME |

**Legend:** APR=APPROVED, NME=NEEDS_MORE_EVIDENCE

---

## 4. DECISIONS BY PRODUCTION vs TEST CONTEXT

### PRODUCTION (8 findings)

| Variant | Exact | Over | APR | NME |
|---------|-------|------|-----|-----|
| A_CONTROL | 0/8=0.0% | 8/8=100.0% | 8 | 0 |
| B_FILECTX | 0/8=0.0% | 8/8=100.0% | 8 | 0 |
| C_EXCEED | 1/8=12.5% | 7/8=87.5% | 7 | 1 |
| D_CONF | 8/8=100.0% | 0/8=0.0% | 0 | 8 |
| E_CTX_EXCEED | 1/8=12.5% | 7/8=87.5% | 7 | 1 |
| F_CTX_CONF | 8/8=100.0% | 0/8=0.0% | 0 | 8 |
| G_EXCEED_CONF | 8/8=100.0% | 0/8=0.0% | 0 | 8 |
| H_ALL | 8/8=100.0% | 0/8=0.0% | 0 | 8 |
| I_DEFAULT_NME | 8/8=100.0% | 0/8=0.0% | 0 | 8 |

**Why C_EXCEED and E_CTX_EXCEED only get 1/8 on PRODUCTION:** Only dde94f1d (flask/helpers.py, ratio=2.27) has an exceedance_ratio. The other 7 PRODUCTION findings have no ratio. Variants C and E fall through to APPROVED for these 7 — the same unsafe default.

### TEST (8 findings)

| Variant | Exact | Over | APR | NME |
|---------|-------|------|-----|-----|
| A_CONTROL | 0/8=0.0% | 8/8=100.0% | 8 | 0 |
| B_FILECTX | 1/8=12.5% | 0/8=0.0% | 0 | 8 |
| C_EXCEED | 1/8=12.5% | 0/8=0.0% | 0 | 8 |
| D_CONF | 1/8=12.5% | 0/8=0.0% | 0 | 8 |
| E_CTX_EXCEED | 1/8=12.5% | 0/8=0.0% | 0 | 8 |
| F_CTX_CONF | 1/8=12.5% | 0/8=0.0% | 0 | 8 |
| G_EXCEED_CONF | 1/8=12.5% | 0/8=0.0% | 0 | 8 |
| H_ALL | 1/8=12.5% | 0/8=0.0% | 0 | 8 |
| I_DEFAULT_NME | 1/8=12.5% | 0/8=0.0% | 0 | 8 |

**Why all variants get 1/8 on TEST:** Only 406bd0f0 (test/app.router.js, human=NEEDS_MORE_EVIDENCE) matches the NME decision. The other 7 TEST findings are NOT_ACTIONABLE, but all variants produce NME for them. NME for NOT_ACTIONABLE is over-deferred but not over-approved — a safer mismatch.

---

## 5. DECISIONS BY THRESHOLD TIER

| Tier | Count | Best Variant | Exact |
|------|-------|--------------|-------|
| MODERATE (1.5-3.0) | 8 | All except A | 1/8=12.5% |
| HIGH (3.0-5.0) | 1 | All | 1/1=100.0% |
| EXTREME (5.0+) | 0 | N/A | N/A |
| No ratio | 7 | D, F, G, H, I | 7/7=100.0% |

**Key insight:** The 7 PRODUCTION findings without ratio are the critical test. Variants C and E APPROVE them (wrong). Variants D, F, G, H, I produce NME (correct per human judgment).

---

## 6. TOP 3 VARIANTS — DETAILED DECISION ANALYSIS

### VARIANT H (ALL) — Best Calibration Candidate

| # | UUID | CTX | RATIO | HUMAN | DECISION | MATCH | Explanation |
|---|------|-----|-------|-------|----------|-------|-------------|
| 1 | 0786261a | PROD | None | NME | NME | YES | Low evidence (conf < 0.6) |
| 2 | 1ffc0671 | PROD | None | NME | NME | YES | Low evidence (conf < 0.6) |
| 3 | 2529875f | TEST | 1.89 | NOT_ACT | NME | NO | Over-deferred (safe) |
| 4 | 33152366 | PROD | None | NME | NME | YES | Low evidence (conf < 0.6) |
| 5 | 3ca62036 | TEST | 2.72 | NOT_ACT | NME | NO | Over-deferred (safe) |
| 6 | 406bd0f0 | TEST | 4.06 | NME | NME | YES | TEST file |
| 7 | 44ec7870 | PROD | None | NME | NME | YES | Low evidence (conf < 0.6) |
| 8 | 51dd146c | PROD | None | NME | NME | YES | Low evidence (conf < 0.6) |
| 9 | 578e37c7 | TEST | 1.77 | NOT_ACT | NME | NO | Over-deferred (safe) |
| 10 | 758f726c | TEST | 1.89 | NOT_ACT | NME | NO | Over-deferred (safe) |
| 11 | 807252d7 | TEST | 1.79 | NOT_ACT | NME | NO | Over-deferred (safe) |
| 12 | 87758338 | TEST | 2.34 | NOT_ACT | NME | NO | Over-deferred (safe) |
| 13 | ce9cccbf | PROD | None | NME | NME | YES | Low evidence (conf < 0.6) |
| 14 | d64f9c8c | PROD | None | NME | NME | YES | Low evidence (conf < 0.6) |
| 15 | dde94f1d | PROD | 2.27 | NME | NME | YES | Moderate exceedance |
| 16 | fd49f9a0 | TEST | 1.71 | NOT_ACT | NME | NO | Over-deferred (safe) |

**9/16 exact. 7 mismatches are all NME-on-NOT_ACTIONABLE (over-deferred, not over-approved).**

### VARIANT D (CONF) — Simplest Generalizing

Identical decisions to H on all 16 items. The confidence threshold (0.5 < 0.6) fires for every finding regardless of file_context or exceedance_ratio.

### VARIANT I (DEFAULT NME) — Simplest Fix

Identical decisions to H and D on all 16 items. The default → NME catches everything the other conditions miss.

**All three converge because:** confidence=0.5 is uniform across all findings, and no findings trigger the duplicate or risk conditions. The different input paths (file_context, exceedance_ratio, confidence) all produce the same output when the inputs are uniform.

---

## 7. VARIANT E — OVERFITTING ANALYSIS

| Metric | Calibration | Holdout | Delta |
|--------|------------|---------|-------|
| Exact Agreement | 66.7% | 12.5% | -54.2% |

**7 PRODUCTION over-approvals:** All 7 PRODUCTION findings without exceedance_ratio are APPROVED by Variant E. Human classified all 7 as NEEDS_MORE_EVIDENCE. The file_context check does not apply to PRODUCTION files. The exceedance_ratio check does not apply (no ratio). Default → APPROVED fires.

**Why this is overfitting:** Variant E performed well on calibration because calibration findings had exceedance_ratio values available. The holdout PRODUCTION findings lack this input. Variant E's rules are insufficient without the ratio — it degrades to the same unsafe default as Control A.

---

## 8. VARIANT I SPECIAL ANALYSIS

### Control A Default → Approved

| Metric | Value |
|--------|-------|
| Findings hitting DEFAULT | 16/16 |
| Human: NEEDS_MORE_EVIDENCE | 9 |
| Human: NOT_ACTIONABLE | 7 |
| Human: USEFUL | 0 |

**Every finding in the holdout hits the default path.** No conditions fire because:
- confidence=0.5 >= 0.4 (never triggers)
- risk_level="none" (never triggers)
- completeness="insufficient" (never triggers)

### Variant I Improvement

| Metric | Control A | Variant I | Delta |
|--------|-----------|-----------|-------|
| Exact Agreement | 0.0% | 56.2% | +56.2% |
| Over-Approval | 100.0% | 0.0% | -100.0% |
| USEFUL Rejections | 0 | 0 | 0 |

**Variant I eliminates all over-approvals without rejecting any findings.** It defers everything to human review (NME). This is safe: NME means "needs more evidence," not "reject."

**Limitation:** Variant I cannot distinguish NOT_ACTIONABLE from NEEDS_MORE_EVIDENCE. All 7 NOT_ACTIONABLE findings are deferred to NME. This is over-deferment (not over-approval) — a safer failure mode.

---

## 9. ROOT CAUSE ANALYSIS

**Primary defect: C. unsafe default approval semantics**

The current governance defaults to APPROVED when no condition matches. With confidence=0.5, risk_level="none", and completeness="insufficient", no conditions ever fire. Every finding hits the default. This produces 100% over-approval.

**Contributing factor: A. missing contextual inputs**

7/8 PRODUCTION findings lack exceedance_ratio. Without this input, threshold-based variants (C, E) cannot apply their rules and fall through to the default. This compounds the unsafe default.

**NOT the primary defect: B. poor thresholds**

The confidence threshold (0.4) is unreachable because confidence=0.5 is hardcoded. Even if lowered, it would only affect the eq_level="low" path. The real issue is the default, not the threshold value.

**Verdict: D. combination of A and C** — but C is the dominant factor. Fixing C alone (Variant I) achieves 56.2% on holdout. Fixing C + A (Variant H) achieves 66.7% on calibration but 56.2% on holdout (no marginal gain on holdout due to uniform inputs).

---

## 10. GENERALIZATION ASSESSMENT

| Variant | Calibration | Holdout | Delta | Verdict |
|---------|------------|---------|-------|---------|
| D_CONF | 51.9% | 56.2% | +4.3% | PASS |
| F_CTX_CONF | 51.9% | 56.2% | +4.3% | PASS |
| G_EXCEED_CONF | 51.9% | 56.2% | +4.3% | PASS |
| H_ALL | 66.7% | 56.2% | -10.5% | PASS |
| I_DEFAULT_NME | 51.9% | 56.2% | +4.3% | PASS |
| E_CTX_EXCEED | 66.7% | 12.5% | -54.2% | OVERFIT |
| C_EXCEED | 48.1% | 12.5% | -35.6% | OVERFIT |
| B_FILECTX | 37.0% | 6.2% | -30.8% | OVERFIT |
| A_CONTROL | 14.8% | 0.0% | -14.8% | BAD |

**5 variants generalize. 3 overfit. 1 is the baseline.**

---

## 11. PROMOTION CRITERIA ASSESSMENT

| Criterion | H_ALL | D_CONF | I_DEFAULT_NME |
|-----------|-------|--------|---------------|
| Generalizes to blind holdout | PASS | PASS | PASS |
| Low over-approval | PASS (0%) | PASS (0%) | PASS (0%) |
| Low under-approval | PASS (0%) | PASS (0%) | PASS (0%) |
| Does not reject everything | PASS (0 REJ) | PASS (0 REJ) | PASS (0 REJ) |
| Preserves useful findings | UNMEASURABLE | UNMEASURABLE | UNMEASURABLE |
| Explainable | PASS | PASS | PASS |
| Minimal complexity | PASS (9 rules) | PASS (1 rule) | PASS (1 rule) |
| No repository-specific rules | PASS | PASS | PASS |
| No rules fitted to holdout | PASS | PASS | PASS |

**UNMEASURABLE:** No USEFUL findings in holdout. Cannot validate useful-recall.

---

## 12. RECOMMENDATION

### MORE_VALIDATION_REQUIRED

**Rationale:**

1. **Holdout too small:** 16 items with only 2 contexts (PRODUCTION, TEST). No CONFIGURATION findings. Cannot validate config-context handling.

2. **No USEFUL findings:** Useful-recall is unmeasurable. Promoting without this validation risks rejecting genuinely useful findings.

3. **Convergence problem:** All generalizing variants (D, F, G, H, I) produce identical holdout results (56.2%) due to uniform confidence=0.5. The holdout cannot differentiate between them.

4. **Variant E overfitting confirmed:** -54.2% delta. The calibration-best variant is disqualified.

5. **Remaining candidates are conservative:** All generalizing variants defer everything to NME. This is safe but may be too conservative for production use. Need a holdout with USEFUL findings to measure the tradeoff.

**Day 7 Focus Areas:**
- Expand holdout to include CONFIGURATION and USEFUL findings
- Test against full 84-finding set to measure useful-recall
- Validate that NME deferral rate is acceptable for production
- Do NOT promote to production without explicit operator decision

---

## 13. SAFETY

| Check | Status |
|-------|--------|
| Source modification | NONE |
| Branch creation | NONE |
| Commit | NONE |
| Push | NONE |
| PR | NONE |
| Merge | NONE |
| Workflow changes | NONE |
| GitHub settings | NONE |
| Mission execution | NONE |
| Production Governance changed | NO |
| Historical findings mutated | NO |
| Previous snapshots altered | NO |

**Status:** PASS

---

## 14. FRICTION

1. Holdout too small (16 items)
2. No USEFUL findings in holdout
3. No CONFIGURATION findings in holdout
4. 7/8 PRODUCTION findings lack exceedance_ratio
5. Variant E overfitting confirmed (-54.2% delta)
6. All generalizing variants converge to same holdout result (56.2%)
7. Cannot differentiate D, F, G, H, I on holdout

---

*Day 6 blind holdout evaluation complete. No production changes. All evidence preserved.*
