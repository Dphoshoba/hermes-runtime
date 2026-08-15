# Evidence Enrichment v2 — Discriminative Signal Discovery Report

**Milestone:** Evidence Enrichment v2 — Discriminative Signal Discovery
**Phase:** Signal-discovery experiment (NO Governance decision rule)
**Evidence Enrichment v1:** PRESERVED, unchanged
**Production Governance:** UNCHANGED
**Date:** 2026-08-12

---

## 1. Objective

Determine whether EVOSIA can collect NEW evidence that meaningfully
distinguishes USEFUL / NEEDS_MORE_EVIDENCE / NOT_ACTIONABLE, beyond what v1
captured. Explicitly NOT tuning thresholds against frozen labels; NOT
implementing a Governance rule.

---

## 2. What was built (additive, v1 preserved)

`hermes_v01/evidence_enrichment_v2.py` — a SEPARATE experimental enrichment
layer. v1 (`evidence_enrichment.py`) is untouched. v2 attaches a new optional
`enrichment_v2` block to findings; ordinary EI execution (no v2 context) is
byte-identical to pre-v2 behavior.

New signal families discovered (all read-only, label-free):

| Family | Signals | Source |
|---|---|---|
| A. Change / churn | commits_touching_file, churn_score, change_frequency_rel_repo | `git log --numstat` @ exact commit |
| B. Co-change / coupling | cochange_partner_count, strongest_cochange_ratio, change_coupling_classification | shared-commit analysis |
| C. Structural centrality | inbound/outbound dependency, normalized centrality, fan-in/fan-out | intra-cohort import graph (git archive) |
| D. Test relationship | STATIC_TEST_RELATIONSHIP vs runtime_coverage (=NOT_AVAILABLE) | static test index |
| E. Corroboration | findings_on_same_component, corroborating_signal_count, strength | cohort + parsed breadth |
| F. Responsibility breadth | exported_symbol_count, route/hook counts, domains, breadth_score (EXPERIMENTAL) | static parse |
| + Repo-normalized percentiles | percentile_rank() helper | harness over cohort |

**Label-free extraction invariant:** `extract_v2(finding, history, graph)`
never reads any human classification. The label is joined only AFTER extraction
is frozen (see §5).

---

## 3. Strict Validation Cohort (provenance-qualified)

Only findings satisfying `VALIDATION_EVIDENCE_REPRODUCIBLE` were used:

- **hermes-runtime** @ `823a9d7e70a9fab8714c219ff52338ef696d3f9e` (EXACT_RECONSTRUCTED)
- **faithtech-blueprint** @ `c5a792b1d6919f0c02f976ff435ec0f2859ccc06` (EXACT_RECONSTRUCTED)

Excluded (kept separate, not in strict metrics):
- inspirevoice-backend (PARTIALLY_RECONSTRUCTED)
- cognikid_app (COMMIT_UNKNOWN / candidate only)

**Strict cohort size: 45 findings**
- USEFUL: 9
- NEEDS_MORE_EVIDENCE: 26
- NOT_ACTIONABLE: 10

---

## 4. Extraction Methodology (frozen)

1. For each strict repo, `build_repo_context()` ran ONCE at the exact commit
   (read-only `git archive` / `git log`): per-file commit history, co-change
   pairs, static test index, and an intra-cohort import graph.
2. `extract_v2()` ran per finding with NO human label passed.
3. Extraction hashes (sha256) computed and frozen.
4. **Only then** were Cycle-7 human labels joined.

No checkout into working trees; no mutation of target repositories.

---

## 5. Label Firewall Verification

**Requirement G — proven:**
> same finding + same repo context + different human label input
> → identical enrichment_v2 output

The harness extracted the same base finding twice with `human_classification`
set to USEFUL and NOT_ACTIONABLE respectively. Outputs were byte-identical
(`json.dumps(..., sort_keys=True)` equal). `label_firewall_verified: True` is
persisted in `cycle8_enrichment_v2.json`.

---

## 6. Coverage Gate

All six v2 signal groups achieved HIGH_COVERAGE in the strict cohort (45/45
eligible), including structural_centrality (via the intra-cohort import
graph). No signal was discarded for sparsity.

| Signal | Available | Eligible | Coverage | Band |
|---|---|---|---|---|
| churn | 45 | 45 | 1.00 | HIGH |
| cochange | 45 | 45 | 1.00 | HIGH |
| structural_centrality | 45 | 45 | 1.00 | HIGH |
| test_relationship | 45 | 45 | 1.00 | HIGH |
| corroboration | 45 | 45 | 1.00 | HIGH |
| responsibility_breadth | 45 | 45 | 1.00 | HIGH |

---

## 7. Signal Distributions (strict cohort)

| Signal | USEFUL (mean) | NME (mean) | NOT_ACTIONABLE (mean) |
|---|---|---|---|
| commits_touching_file | 1.33 | 1.15 | 1.10 |
| churn_score (lines/commit) | 339.5 | 219.9 | 296.4 |
| cochange_partner_count | 8.44 | 7.19 | 7.00 |
| centrality_inbound | 0.44 | 0.12 | 0.00 |
| breadth_score | 8.6 | 10.9 | 18.9 |

Categorical:
- change_coupling_classification: USEFUL 78% HIGH / NME 85% HIGH / NOT_ACTIONABLE 80% HIGH
- test_relationship: USEFUL 22% referenced / NME 38% / NOT_ACTIONABLE 30% (inverse)
- corroboration_strength: all three dominated by WEAK (USEFUL 89% / NME 92% / NOT_ACTIONABLE 80%)

---

## 8. Discrimination Analysis

**Every v2 signal classified NO_DISCRIMINATION** (descriptive, after freeze):

- churn_commit_count: NO_DISCRIMINATION (all ~1 commit; overlapping)
- churn_score: NO_DISCRIMINATION (overlapping ranges)
- cochange_partner_count: NO_DISCRIMINATION (overlapping)
- centrality_inbound: NO_DISCRIMINATION (overlapping, weak)
- breadth_score: NO_DISCRIMINATION (USEFUL actually LOWER than NOT_ACTIONABLE)
- cochange_coupling_class: NO_DISCRIMINATION (all classes HIGH-coupled)
- test_relationship_type: NO_DISCRIMINATION (inverse direction)
- corroboration_strength: NO_DISCRIMINATION (all WEAK)

No threshold was tuned; no classifier trained.

---

## 9. Matched-Pair / USEFUL Error Analysis

9 USEFUL↔NME matched pairs (same category + file_context) were compared on
churn and co-change. For every pair the two classes differed only marginally on
co-change (which itself does not discriminate). The human USEFUL distinction is
not explained by any static/history signal captured here. The dominant signal
common to ALL classes is HIGH change-coupling + WEAK corroboration + low test
reference — i.e., the cohort is uniformly "large, coupled, under-tested"
infrastructure, and human actionability judgment cuts across that uniformly.

---

## 10. Finding-Type Analysis

The frozen dataset carries no `category` field, so per-category separation
could not be stratified from ground-truth categories. Titles suggest the cohort
is dominated by "Large Module" / "High Hook" / "API Concentration" findings —
all of which map to the same static signature (large, coupled component). No
category-specific semantics emerged that would let Governance separate classes.

---

## 11. Limitations

- Human actionability appears driven by factors NOT present in static/history
  evidence: runtime criticality, business impact, failure history, operational
  context. EVOSIA possesses none of these (behavioral evidence is structurally
  NOT_OBSERVED).
- The intra-cohort graph is cohort-local (only the 20–25 strict paths), so
  fan-in/fan-out is a lower bound, not whole-repository centrality. Whole-repo
  graph building was out of scope for this experiment.
- responsibility_breadth is EXPERIMENTAL and was excluded from strict
  discrimination claims per the milestone.
- Sample sizes are small (9 USEFUL), limiting statistical power; descriptive
  analysis only.

---

## 12. Safety

| Check | Result |
|---|---|
| source modification | NONE |
| branch creation | NONE |
| commit to target repo | NONE |
| push / PR / merge | NONE |
| checkout into working trees | NONE (git archive only) |
| workflow / GitHub settings modification | NONE |
| mission execution | NONE |
| target repository mutation | NONE (verified: 3 target repos at exact Cycle-7 SHAs) |
| Governance modification | NONE (decisions identical with/without v2: 578/158/4) |
| canonical SCAN_STAGES | UNCHANGED (no new stage introduced) |

---

## 13. Tests

Focused suite: `tests/test_evidence_enrichment_v2.py` — **17 passed** (real exit
code 0). Covers determinism, label firewall, git-history extraction, churn
normalization, co-change bounding, structural centrality (supported +
unsupported language), static test relationships, corroboration, percentiles,
missing-data semantics, provenance, no-mutation, governance-unchanged,
SCAN_STAGES-unchanged, v1 backward compatibility.

Ad-hoc verification (disposable `hermes-verify-*` script, real exit code 0)
confirmed: firewall holds, git-history extraction read-only, v1 preserved + v2
additive + governance identical, target repos untouched.

**FOCUSED_TESTS_PASS** = yes (17/17). **FULL_SUITE_PASS** = not claimed; the
canonical full suite was not run in this milestone (only focused v1 + v2
suites).

---

## 14. Artifacts

- `hermes_v01/evidence_enrichment_v2.py` (module)
- `tests/test_evidence_enrichment_v2.py` (17 tests)
- `validation/analysis/replay_v2_discovery.py` (replay harness, frozen)
- `validation/results/cycle8_enrichment_v2.json` (extraction + coverage + firewall + distributions)
- `validation/results/cycle8_signal_discrimination.json` (decision + quality)
- `EVIDENCE_ENRICHMENT_V2_REPORT.md` (this file)

---

## 15. Decision

`STATIC_EVIDENCE_INSUFFICIENT_FOR_AUTOMATED_GOVERNANCE`

No v2 signal — nor any v1 signal — separates USEFUL from
NEEDS_MORE_EVIDENCE / NOT_ACTIONABLE with acceptable separation in the
provenance-qualified strict cohort. The human actionability judgment is not
recoverable from repository static + git-history evidence available to EVOSIA.
This is a valid, conclusive result of the experiment; it does not warrant
another enrichment cycle merely to avoid the conclusion.

**Recommended next steps (if automated governance is still desired):**
1. Acquire the missing evidence classes: runtime criticality, failure/incident
   history, actual usage/coverage telemetry, business-impact metadata. Without
   at least one of these, no static/history enrichment will discriminate.
2. Reconsider whether human actionability is even a function of code properties
   — it may be an operational/judgment input that should remain human-in-the-loop.

---

## STOP

No Governance candidate implemented. Production Governance unchanged. No
promotion testing begun. No further validation cycle auto-started. Report
returned to operator.
