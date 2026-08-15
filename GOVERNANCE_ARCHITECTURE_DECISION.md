# Governance Architecture Decision — Post Cycle 8

**Status:** Architecture / operating-model decision (documentation only)
**Production Governance:** UNCHANGED by this document
**Evidence Enrichment v1/v2:** COMPLETE
**Evidence conclusion:** `STATIC_EVIDENCE_INSUFFICIENT_FOR_AUTOMATED_GOVERNANCE`
**Operating mode:** CONTROLLED_BETA
**Date:** 2026-08-12
**Promotion (M-Cycle 8):** Evidence & Risk Gate promoted as the Controlled Beta governance baseline; gate mode is the default, legacy Governance is replay-only, human `ACTIONABLE` controls mission eligibility, autonomous execution/repository mutation remain disabled.

---

## 1. Executive Decision

**Primary architectural decision: `GOVERNANCE_SHOULD_BECOME_EVIDENCE_AND_RISK_GATE`**

Governance must stop attempting to *automatically classify actionability*
(USEFUL / NEEDS_MORE_EVIDENCE / NOT_ACTIONABLE). Static repository evidence —
including historical/structural enrichment (v1 + v2) — has been demonstrated,
in a frozen, label-firewalled experiment, to be unable to separate those classes
with acceptable coverage or separation.

Governance's correct role is therefore:

1. **Observe & qualify** repository engineering concerns (machine-determinable,
   uncertainty explicit).
2. **Gate on evidence sufficiency and risk** — i.e., decide whether a finding
   has *enough* evidence to warrant human attention and how risky it is, not
   whether a human *should* act.
3. **Rank and route** findings into a human review queue (evidence-based
   prioritization), deferring the actionability call to human authority.

This is a deliberate hybrid: Governance is an *evidence-and-risk gate* plus
*human-decision support*. It is **not** an automated approver and **not** a
pure pass-through.

**Recommended pipeline:**
`DETECT → ENRICH → HUMAN REVIEW (evidence-ranked) → PRIORITIZE → MISSION RECOMMENDATION`
— **not** `DETECT → AUTOMATED GOVERNANCE APPROVAL → MISSION RECOMMENDATION`.

---

## 2. Evidence Considered

| Source | Finding |
|---|---|
| Cycle 7 frozen review set (50 findings) | Human labels: 14 USEFUL, 30 NEEDS_MORE_EVIDENCE, 6 NOT_ACTIONABLE |
| Cycle 7 production-vs-Variant-I eval | **Production Governance APPROVED 41/50 (82%).** Of those, **10 were human-labeled NOT_ACTIONABLE** and **32 were human-labeled ≠ USEFUL** → systematic over-approval confirmed. |
| Evidence Enrichment v1 (strict cohort 45) | No signal meaningfully separates USEFUL vs NME/NOT_ACTIONABLE; structural_importance 0% coverage, source_magnitude 15.6% coverage; change/ownership/evidence_strength constant across classes. |
| Evidence Enrichment v2 (strict cohort 45) | All 8 new signal families (churn, co-change, centrality, test-relationship, corroboration, breadth) classified **NO_DISCRIMINATION**; label firewall verified; all signals HIGH coverage. Human actionability is not recoverable from static/history evidence. |
| MissionPrioritizer v1 (post-human-evidence) | 100% USEFUL retention, 0% NOT_ACTIONABLE leakage, 100% traceability, materially reduced operator burden — i.e., EVOSIA excels at prioritization *after* human evidence exists, not at producing that evidence. |

**Conclusion accepted as established:** `STATIC_EVIDENCE_INSUFFICIENT_FOR_AUTOMATED_GOVERNANCE`.

---

## 3. Why Automated Actionability Classification Failed

The USEFUL/NME/NOT_ACTIONABLE distinction is not a function of code structure.
The strict cohort is uniformly "large, coupled, under-tested infrastructure."
Actionability depends on evidence EVOSIA does not possess and must not infer:

- runtime behavior and actual failures
- production incidents and their linkage
- business / product importance
- real usage frequency
- *measured* test coverage (vs static reference)
- ownership and roadmap context
- accepted architectural trade-offs
- operator judgment

Every static/history signal (size, hooks, API concentration, churn, coupling,
centrality, test reference, breadth) was either constant across the three
classes or *inversely* related to usefulness (breadth, test reference). Adding
more static heuristics cannot recover information that is not in the signal
domain. This is a structural limit, not a tuning gap.

---

## 4. Recommended Governance Role

**`GOVERNANCE_AS_EVIDENCE_AND_RISK_GATE`** (with embedded human-decision support).

- Governance **may** decide: *Is there enough evidence to surface this? What is
  its risk band? Where does it rank for review?*
- Governance **may not** decide: *Is this actionable? Should an engineer act?*
  That is human authority.

This minimizes, per the objective:
- **false automatic approval** → eliminated (no auto-actionable)
- **suppression of useful findings** → mitigated (findings are ranked, not
  buried; only deterministic low-risk policy suppression allowed)
- **unnecessary human burden** → mitigated (evidence-ranked queue, clustering,
  duplicate detection — §9)
- **unexplained decisions** → mitigated (every gate decision carries evidence
  references and an explicit uncertainty/risk band)

---

## 5. Observation / Concern / Actionability Boundary

### A. OBSERVATION — "What does EVOSIA detect?"
Machine-determinable from static + enriched evidence:
- module exceeds repository norm (percentile)
- high hook concentration, API concentration
- missing static test relationship
- high churn, high change-coupling
- structural centrality / fan-in-out
- corroborating independent signals

→ EVOSIA **CAN** assert these with quantified confidence.

### B. ENGINEERING CONCERN — "Plausibly worth investigating?"
Uses severity, corroboration, repository context, evidence quality,
structural/history evidence. EVOSIA **MAY rank/qualify** this, but **uncertainty
must remain explicit** (no false precision).

### C. ACTIONABILITY — "Should an engineer actually do something?"
Depends on evidence outside static repository analysis (runtime, failures,
business weight, usage, measured coverage, ownership, roadmap, trade-offs,
operator judgment). EVOSIA **MUST NOT infer** these when unavailable; the call
is **human authority** during Controlled Beta.

**Documented split:** EVOSIA supports A (full) and B (ranked, uncertain). C is
out of scope for automation.

---

## 6. Proposed Decision-State Model

Separate **observation/concern states** from **approval semantics**.

### States (proposed)
| State | Meaning | Set by |
|---|---|---|
| `OBSERVED` | Signal detected, raw | Engine |
| `CORROBORATED` | ≥2 independent signals on component | Enrichment |
| `REQUIRES_REVIEW` | Evidence/risk gate says human attention warranted | Governance (gate) |
| `INSUFFICIENT_EVIDENCE` | Cannot be ranked/qualified reliably | Governance (gate) |
| `ACTIONABLE` | Human declared actionable | **Human only** |
| `NOT_ACTIONABLE` | Human declared not actionable | **Human only** |
| `DEFERRED` | Queued for later / periodic re-eval | Governance or Human |
| `SUPPRESSED` | Hidden by deterministic policy | Policy engine |
| `DUPLICATE` | Merged into another finding | Engine/Governance |
| `LEGACY_APPROVED` | Old `APPROVED` from pre-redesign Governance (non-authoritative) | Migration |

### Allowed transitions (proposed)
```
OBSERVED ──(≥2 signals)──> CORROBORATED
OBSERVED / CORROBORATED ──(gate: warrants attention)──> REQUIRES_REVIEW
OBSERVED / CORROBORATED ──(gate: insufficient)──> INSUFFICIENT_EVIDENCE
REQUIRES_REVIEW ──(human)──> ACTIONABLE | NOT_ACTIONABLE
REQUIRES_REVIEW ──(human/policy)──> DEFERRED
*_any* ──(deterministic low-risk policy)──> SUPPRESSED
*_any_ ──(merge)──> DUPLICATE
LEGACY_APPROVED ──(migration)──> REQUIRES_REVIEW (re-adjudicated)
```
**Forbidden:** any automated transition into `ACTIONABLE` or `NOT_ACTIONABLE`.
**Forbidden:** `SUPPRESSED` without a logged, deterministic policy rule.

---

## 7. Human Authority Boundary (Controlled Beta)

| Decision | EVOSIA may… | Authority |
|---|---|---|
| Declare a finding ACTIONABLE | RECOMMEND, RANK | **Human** |
| Suppress a finding | `SUPPRESS_WITH_POLICY` (deterministic, logged) | EVOSIA (policy only) / Human override |
| Mission approval | RECOMMEND | **Human** |
| Mission execution | — | **Human** (autonomous execution DISABLED) |
| Repository mutation | — | **Human** (mutation DISABLED) |
| Request more evidence | `REQUEST_EVIDENCE` | EVOSIA |
| Rank / cluster / defer | `RANK`, `DEFER` | EVOSIA |
| Generate mission *recommendation* | yes (post-human) | EVOSIA (advisory) |

EVOSIA operates as **RECOMMEND / RANK / DEFER / REQUEST_EVIDENCE /
SUPPRESS_WITH_POLICY** within a governed boundary; it does **not** hold authority
over actionability, mission approval, execution, or mutation.

---

## 8. Recommended Pipeline Architecture

```
DETECT  (Repository Intelligence)
  → ENRICH  (v1 + v2 additive, label-free)
  → GOVERNANCE AS EVIDENCE+RISK GATE
       - attach OBSERVED/CORROBORATED/REQUIRES_REVIEW/INSUFFICIENT_EVIDENCE
       - compute risk band + evidence-sufficiency
       - rank for review (uncertainty explicit)
  → HUMAN REVIEW  (evidence-ranked queue; clustering + dedup + pattern reuse)
  → PRIORITIZE  (MissionPrioritizer v1, post-human evidence)
  → MISSION RECOMMENDATION  (advisory; human approves/executes)
```

This explicitly replaces the abandoned
`DETECT → AUTOMATED GOVERNANCE APPROVAL → MISSION RECOMMENDATION` path.

---

## 9. Human-Review Burden Strategy

Review must not become "review everything forever." Mechanisms (no new
classifier; ranking only):

- **Evidence-based queue ranking** — sort `REQUIRES_REVIEW` by risk band × evidence
  sufficiency × corroboration.
- **Finding clustering** — group by component / root cause so one review covers many.
- **Duplicate detection** — collapse `DUPLICATE` findings (already in state model).
- **Category grouping** — batch similar concern types.
- **Review sampling** — statistically sample `INSUFFICIENT_EVIDENCE` for audit.
- **Previously adjudicated pattern reuse** — store human decisions as reusable
  patterns (immutable history) to pre-rank similar future findings.
- **Operator-defined policies** — deterministic `SUPPRESS_WITH_POLICY` for agreed
  low-risk cases.
- **Low-risk deterministic suppression** — only explicit, logged rules.

**Critical distinction:** `AUTOMATED REVIEW PRIORITIZATION` (allowed, evidence-
based ranking) ≠ `AUTOMATED ACTIONABILITY JUDGMENT` (forbidden). EVOSIA ranks;
humans judge.

---

## 10. MissionPrioritizer Integration

MissionPrioritizer v1 already proves EVOSIA can prioritize *after* human
evidence exists (100% USEFUL retention, 0% NOT_ACTIONABLE leakage, 100%
traceability, reduced burden). The architecture therefore places PRIORITIZE
**after HUMAN REVIEW**, not after automated governance. Governance's job is to
feed the human review queue well; MissionPrioritizer's job is to rank the
*post-review* actionable set. The two are complementary and must not be
conflated with an actionability classifier.

---

## 11. Behavioral Evidence Roadmap

Future evidence that could *legitimately* reopen automated Governance research:

| Source | Gov. value | Feasibility | Privacy/Security | Complexity | Required for CB? | Core or Enterprise |
|---|---|---|---|---|---|---|
| Runtime telemetry | High | Medium | High (PII/perf data) | High | No | Enterprise |
| Measured test coverage | High | Medium | Low | Medium | No | Enterprise |
| Production failure history | High | Medium | Medium | Medium | No | Enterprise |
| Incident linkage | High | Low–Med | Medium | Medium | No | Enterprise |
| Component usage frequency | Med | Medium | Medium | Medium | No | Enterprise |
| Performance hotspots | Med | Medium | Medium | Medium | No | Enterprise |
| Ownership information | Med | High (org data) | High | Low | No | Enterprise |
| Change-risk history | Med | Medium | Low | Medium | No | Enterprise |

None are required for Controlled Beta. All belong in **Enterprise** (not EVOSIA
Core), collected only with explicit authorization, and must never be inferred
when absent. Research reopens only when ≥1 high-value source is available with
acceptable privacy posture.

---

## 12. Legacy Governance Handling

Current production Governance defaults to `APPROVED` (systematic over-approval:
82% approved, 10/50 human NOT_ACTIONABLE, 32/50 human ≠ USEFUL). This default
must **not** be treated as human-equivalent approval.

**Decision:** reinterpret legacy `APPROVED` as **`LEGACY_APPROVED`** — a
non-authoritative, advisory state for the Controlled Beta period. It routes into
`REQUIRES_REVIEW` during migration and is never used as evidence that a finding
was validated by a human. `REJECTED` legacy decisions are preserved as
`SUPPRESSED`/deferred per policy.

---

## 13. Migration Strategy (backward-compatible)

- **Persisted historical decisions:** immutable. Legacy `APPROVED`/`REJECTED`
  are re-labeled `LEGACY_APPROVED` / `LEGACY_REJECTED` in a *new* column/field;
  original values archived verbatim.
- **API compatibility:** new `enrichment_v2` and gate states are additive;
  existing `enrichment` (v1) and EI fields unchanged; consumers ignoring new
  fields keep working.
- **UI terminology:** show `LEGACY_APPROVED (advisory)`; never "Approved by
  Governance" without human; surface risk band + evidence-sufficiency.
- **Journal events:** emit `GATE_DECISION` events with evidence refs; legacy
  `APPROVAL` events retained read-only.
- **Mission generation:** unchanged interface; inputs now come from
  post-human prioritized set.
- **MissionPrioritizer:** unchanged; consumes post-review actionable set.
- **Human review:** new queue service (evidence-ranked); no change to
  PRIORITIZE internals.
- **Reports/metrics:** adopt §14 metrics; retain raw counts for continuity.

---

## 14. Metrics Redesign

Stop optimizing around raw "Governance approval rate." Recommend:

- **Observation precision** — share of OBSERVED that become CORROBORATED.
- **Human usefulness rate** — share of human-ACTIONABLE findings.
- **Review burden** — findings per human review hour.
- **Review time** — median time-to-decision.
- **Evidence sufficiency rate** — share reaching REQUIRES_REVIEW with adequate
  evidence.
- **Duplicate/suppression rate** — volume removed by clustering/policy.
- **Useful-finding retention** — share of human-USEFUL retained through pipeline.
- **Mission acceptance rate** — human acceptances of recommendations.
- **Mission traceability** — % of missions traceable to a finding + evidence.
- **Operator override rate** — human overrides of gate ranking (calibration
  signal).
- **Unsafe automation rate** — MUST stay 0 (no auto-actionable; no auto-mission).

---

## 15. Risks

- **Burden regression:** if ranking is poor, humans still review everything.
  Mitigation: iterate ranking on operator-override signal (§14).
- **Policy suppression errors:** deterministic rules may hide real issues.
  Mitigation: all `SUPPRESS_WITH_POLICY` logged + sample-audited.
- **Legacy over-approval residue:** old `APPROVED` still influences downstream.
  Mitigation: `LEGACY_APPROVED` re-routing (§12).
- **Premature reopening of auto-governance:** temptation to add behavioral
  heuristics without authorization. Mitigation: §11 gate — requires ≥1
  high-value source with acceptable privacy.
- **Human fatigue from false urgency:** risk-band inflation. Mitigation:
  uncertainty explicit; ranking validated by override rate.

---

## 16. Controlled Beta Operating Implications

- Autonomous mission execution: **DISABLED**.
- Repository mutation: **DISABLED**.
- Production Governance: **UNCHANGED** (this document is advisory until
  implemented in a later, separately-authorized milestone).
- All `APPROVED` outputs treated as `LEGACY_APPROVED` / advisory.
- Actionability remains a human authority.
- EVOSIA may RANK / RECOMMEND / DEFER / REQUEST_EVIDENCE / SUPPRESS_WITH_POLICY
  only.

---

## 17. Future Criteria for Reopening Automated Governance Research

Automated actionability classification research may be reconsidered only when
**all** of:

1. ≥1 high-governance-value behavioral evidence source (§11) is available with
   explicit authorization and an acceptable privacy/security posture;
2. That source demonstrably adds separation beyond static evidence in a frozen,
   label-firewalled replay (replicating the v2 methodology);
3. A coverage gate (repository identity + scan + commit + finding persisted)
   is enforced so results are reproducible;
4. No new classifier is promoted without independent validation against
   human labels with explicit uncertainty reporting.

Until then, Governance remains an **evidence-and-risk gate + human-decision
support** system.

---

## Decision

`GOVERNANCE_SHOULD_BECOME_EVIDENCE_AND_RISK_GATE`

(With explicit human-decision-support bias for the actionability call; automated
approval discontinued.)

---

## STOP

Documentation/architecture decision only. Production Governance not modified.
Target repositories not modified. No missions executed. MissionPrioritizer not
changed. No behavioral telemetry implemented. Recommendation returned to
operator before any implementation.
