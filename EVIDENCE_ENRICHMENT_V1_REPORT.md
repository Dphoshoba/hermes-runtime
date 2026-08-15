# Evidence Enrichment v1 — Implementation Report

**Milestone:** Evidence Enrichment v1
**Phase:** Evidence-only enrichment (NO new Governance decision policy)
**Production Governance:** UNCHANGED
**Date:** 2026-08-12

---

## 1. Implementation

Created `hermes_v01/evidence_enrichment.py` — a deterministic, read-only,
evidence-backed enrichment layer. Each finding receives an additive
`enrichment` block (key `"enrichment"`, version `"1.0.0"`). Existing EI fields
are never renamed or removed; `Finding.as_dict()` emits `enrichment` only when
present.

Signals implemented (all with `UNKNOWN`/`NOT_AVAILABLE`/`NOT_OBSERVED` fallbacks):

| Signal | Source | Notes |
|---|---|---|
| `source_magnitude` (observed/threshold/exceedance_ratio/tier) | finding evidence text + 300-line threshold | only meaningful for line-count findings |
| `file_context` | affected-path pattern | PRODUCTION/TEST/CONFIGURATION/DOCUMENTATION/FIXTURE/VENDOR/GENERATED/UNKNOWN |
| `change_history` | read-only `git log` at exact commit | commit_count, churn_classification |
| `ownership_concentration` | read-only `git shortlog` contributor emails | contributor_count, dominant_share (no org inference) |
| `structural_importance` | RI `module_graph` | inbound/outbound degree, centrality |
| `evidence_strength` | finding `evidence_references` | reference count, independent type count |
| `behavioral_evidence` | policy | explicitly `NOT_OBSERVED` — never fabricated |

### Integration point (no canonical stage added)
Wired inside `analyze_engineering()` (the EI boundary). Findings are generated,
converted to dict, enriched via `enrich_findings()`, then re-wrapped as frozen
`Finding` objects carrying the block. `SCAN_STAGES` is untouched (the module
defines no such constant; enrichment attaches within the existing EI call).

### Provenance inside enrichment
Every block carries `version`, `repository_identifier`, `commit_sha`,
`affected_path`, plus a `source`/`available` field per signal so each value is
traceable. No enrichment result without source provenance.

---

## 2. Provenance

Strict replay cohort (EXACT_RECONSTRUCTED):

- **hermes-runtime** @ `823a9d7e70a9fab8714c219ff52338ef696d3f9e`
- **faithtech-blueprint** @ `c5a792b1d6919f0c02f976ff435ec0f2859ccc06`

Exploratory cohort (excluded from strict metrics, labeled explicitly):

- **inspirevoice-backend** @ `83f1c009` — PARTIALLY_RECONSTRUCTED (frozen paths renamed)
- **cognikid_app** @ `ccd1fd51` — COMMIT_UNKNOWN (candidate commit only)

---

## 3. Strict Cohort Replay

45 strict-cohort findings replayed with frozen labels preserved:

| Class | Count |
|---|---|
| USEFUL | 10 |
| NEEDS_MORE_EVIDENCE | 29 |
| NOT_ACTIONABLE | 6 |
| **Total** | **45** |

(Faithtech + hermes-runtime strict findings; matches the frozen dataset's
10 USEFUL / 29 NME / 6 NOT_ACTIONABLE among these two repos.)

---

## 4. Exploratory Cohort

InspireVoice (6 findings) and CogniKid (5 findings) were enriched separately
with explicit `PARTIAL`/`CANDIDATE` provenance labels and are **not** included
in any discrimination or accuracy claim.

---

## 5. Signal Coverage (strict cohort, 45 eligible)

| Signal | Available | Coverage |
|---|---|---|
| change_history | 45/45 | 1.00 |
| ownership_concentration | 45/45 | 1.00 |
| file_context | 45/45 | 1.00 |
| evidence_strength | 45/45 | 1.00 |
| source_magnitude | 7/45 | 0.156 |
| structural_importance | 0/45 | 0.00 |

**Coverage defects:**
- `structural_importance` = 0% — the replay-derived findings are not nodes in
  the RI module graph (they were reconstructed from the frozen dataset, not
  re-scanned). For a live scan this signal would populate; for strict replay it
  is unavailable. **Must not be treated as a Governance input until live RI
  coverage exists.**
- `source_magnitude` = 15.6% — only line-count findings encode an observed
  magnitude. Hook/API/"no coverage" findings carry no numeric magnitude in the
  frozen evidence.

---

## 6. Signal Distributions (strict cohort)

| Signal | USEFUL | NME | NOT_ACTIONABLE |
|---|---|---|---|
| exceedance_ratio (mean) | 2.47 | 1.90 | 2.27 |
| file_context | 100% PRODUCTION | 100% PRODUCTION | 67% PRODUCTION / 33% TEST |
| change_history churn | LOW(9)/MODERATE(1) | 100% LOW | 100% LOW |
| ownership_concentration | 100% HIGH | 100% HIGH | 100% HIGH |
| structural_centrality | 100% UNKNOWN | 100% UNKNOWN | 100% UNKNOWN |
| evidence_strength | 100% WEAK | 100% WEAK | 100% WEAK |

---

## 7. Discrimination Analysis

**No enriched signal meaningfully separates USEFUL from NME/NOT_ACTIONABLE
with acceptable coverage in the strict cohort.**

- `exceedance_ratio`: USEFUL mean (2.47) is modestly higher than NME (1.90) and
  NOT_ACTIONABLE (2.27), but the ranges overlap heavily and only 7/45 findings
  have a magnitude. **WEAK_DISCRIMINATOR.**
- `file_context`: ALL strict-cohort findings are PRODUCTION. The one signal
  that could help (TEST context for NOT_ACTIONABLE) appears only in the
  exploratory cohort. **WEAK / NO_DISCRIMINATION** in strict cohort.
- `change_history`, `ownership_concentration`, `evidence_strength`: identical
  across all three classes (every finding = LOW churn, HIGH ownership, WEAK
  evidence). **NO_DISCRIMINATION.**
- `structural_importance`: 0% coverage. **INSUFFICIENT_DATA.**

---

## 8. Missing-Data Analysis

- `structural_importance` (0%) and `source_magnitude` (15.6%) have insufficient
  coverage to act as Governance inputs. Per the enrichment contract, signals
  with poor coverage are explicitly flagged and must not drive decisions.
- Behavioral evidence is structurally `NOT_OBSERVED` for every finding — EVOSIA
  possesses no runtime/incident/usage data, so no such signal exists to enrich.

---

## 9. Safety

| Check | Result |
|---|---|
| source modification | NONE |
| branch creation | NONE |
| commit to target repo | NONE |
| push | NONE |
| PR | NONE |
| merge | NONE |
| workflow modification | NONE |
| GitHub settings modification | NONE |
| mission execution | NONE |
| target repositories mutated | NONE (read-only git; input dicts immutable) |

Git history is read via `git log` / `git shortlog` only — no checkout, no write.

---

## 10. Tests

Focused suite: `tests/test_evidence_enrichment.py` — **32 passed** (real exit
code 0). Covers determinism, exact-commit provenance, file-context
classification, exceedance + tiers, git change-history, contributor/ownership,
dependency centrality, evidence strength, missing-data semantics, additive
compatibility, Governance-receives-but-unchanged, canonical-stage-unchanged,
and target-repo-immutability.

Ad-hoc verification (disposable `hermes-verify-*` script, real exit code 0)
confirmed: classification ordering, enrichment immutability/determinism,
Governance emits+receives enrichment while `_decide()` ignores it (decisions
578/158/4 unchanged), and the focused suite itself passes.

---

## 11. Defects

| Defect | Impact |
|---|---|
| `structural_importance` 0% coverage in strict replay | Cannot evaluate centrality as a discriminator until live RI is used |
| `source_magnitude` 15.6% coverage | Only line-count findings carry magnitude; hook/API/coverage findings do not |
| Exploratory cohort excluded from strict metrics | InspireVoice/CogniKid cannot contribute to accuracy claims (provenance) |
| Behavioral evidence absent by design | No runtime signal exists to enrich; governance cannot use what EVOSIA lacks |

---

## 12. Recommendation

Implementing a Governance candidate is **not yet justified** by the evidence.
Enrichment v1 is built, wired, and safe, but the enriched signals do not
separate USEFUL from NME/NOT_ACTIONABLE with acceptable coverage in the strict
cohort. The strongest candidate signal (`exceedance_ratio`) is weak and
sparsely covered; the rest are either constant across classes or unavailable.

**Recommended next steps before any Governance candidate:**
1. Run enrichment against **live** Cycle-7 scans (not frozen-reconstructed
   findings) so `structural_importance` and full `source_magnitude` populate.
2. Broaden `source_magnitude` to hook-count / API-count / coverage-gap findings
   (currently only line-count findings encode a magnitude).
3. Acquire the missing evidence classes identified in the earlier
   Post-Cycle-7 analysis (churn history, dependency fan-in/out, runtime
   criticality) — these remain unavailable and are the most likely
   discriminators.
4. Re-run discrimination on a larger holdout (Cycle 8, 60–100 findings) before
   designing a decision policy.

---

## 13. Decision

`MORE_EVIDENCE_ENRICHMENT_REQUIRED`

No enriched signal meaningfully separates USEFUL from NME/NOT_ACTIONABLE with
acceptable coverage. Enrichment v1 is complete and safe; it is not yet
sufficient to support a Governance candidate. Do **not** implement a Governance
candidate or modify production Governance at this time.

---

## STOP

No Governance candidate implemented. Production Governance unchanged. No
candidate promotion testing begun. Report returned to operator.
