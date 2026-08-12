# Governance Evidence & Risk Gate — Implementation Plan

**Derived from:** `GOVERNANCE_ARCHITECTURE_DECISION.md` (Post Cycle 8)
**Status:** IMPLEMENTATION PLAN — documentation only, no code changes in this step
**Target pipeline:** `DETECT → ENRICH → EVIDENCE/RISK GATE → HUMAN REVIEW → PRIORITIZE → MISSION RECOMMENDATION`
**Safety invariant:** Hermes never creates `ACTIONABLE`/`NOT_ACTIONABLE` adjudication without human authority. Legacy decisions stored immutably; re-labeled, never rewritten.

---

## 0. Migration-Critical Code Paths (identified from current source)

These are the exact places where today `APPROVED` acts as authorization and
must change. Citations are to current files.

| # | Path | Current behavior | Migration action |
|---|---|---|---|
| M1 | `hermes_v01/governance_analyzer.py:142-167` `_build_missions()` | Builds `ApprovedCandidateMission` for every decision in `("APPROVED","APPROVED_WITH_NOTES")`. | Gate stops emitting `approved_missions` for actionability. Emits `gate_routing` (REQUIRES_REVIEW / INSUFFICIENT_EVIDENCE) instead. `approved_missions` retained as deprecated/empty under gate mode. |
| M2 | `hermes_v01/governance_analyzer.py` `_decide()` default fallthrough | Any unhandled case → `APPROVED` (systemic over-approval root cause, confirmed `day5_analysis.py:200,209`). | Default fallthrough → `REQUIRES_REVIEW` (human-authority-default), never `APPROVED`. `APPROVED` no longer a Governance output for actionability. |
| M3 | `hermes_v01/mission_generator.py:128-167` `generate_missions()` | Iterates `assessment["approved_missions"]`; each becomes a candidate mission. **This is the primary `APPROVED`→mission authorization.** | `generate_missions` MUST reject any mission whose originating finding lacks a human `ACTIONABLE` adjudication (see §4 guard). Under gate mode `approved_missions` is empty, so no mission is generated without review. |
| M4 | `hermes_v01/mission_recommendation_models.py:14,16,69,139` `DraftMission.approve(by="human")` | `DRAFT → APPROVED`; "Only APPROVED missions may enter MissionPlanner." | Unchanged — this remains the *mission* authorization, but the **finding** feeding it must be human-adjudicated `ACTIONABLE`. Gate adds a pre-condition check (§4). |
| M5 | `enterprise/services/review_service.py` `create_adjudication` / `build_review_queue` | Append-only human adjudication store + queue. Currently classifies `USEFUL`/`FALSE_POSITIVE`/`NOT_ACTIONABLE`. | Extend allowed adjudication values to include `ACTIONABLE`/`NOT_ACTIONABLE` (human authority). Queue ranking gains evidence/risk band (§5). Adjudication records become the SOLE source of `ACTIONABLE`. |
| M6 | `hermes_v01/mission_prioritizer.py:145-146` `DECISION_WEIGHTS["APPROVED"]` | Prioritizer scores missions with `human_classification == "APPROVED"` weight 2.0. | Re-point to `human_classification == "ACTIONABLE"` (the human-adjudicated state). Legacy `"APPROVED"` missions scored as `LEGACY_APPROVED` (advisory, not selected). |

---

## 1. Models

### 1.1 `hermes_v01/governance_intel_models.py` (Engineering Governance)
- Add `GateRouting` enum-like constants (plain `str` constants, frozen):
  `OBSERVED`, `CORROBORATED`, `REQUIRES_REVIEW`, `INSUFFICIENT_EVIDENCE`,
  `DEFERRED`, `DUPLICATE`, `LEGACY_APPROVED`, `LEGACY_REJECTED`.
- Add `FindingGate` dataclass (additive, frozen):
  ```
  FindingGate:
    finding_id: str
    observation_state: str          # OBSERVED | CORROBORATED
    gate_state: str                 # REQUIRES_REVIEW | INSUFFICIENT_EVIDENCE | DEFERRED | DUPLICATE
    risk_band: str                  # LOW | MODERATE | HIGH
    evidence_sufficiency: str       # SUFFICIENT | INSUFFICIENT
    review_rank: float              # derived ranking score (uncertainty explicit)
    uncertainty_note: str           # always present
    evidence_refs: tuple[...]
    legacy_decision: str | None     # original APPROVED/REJECTED if from migration
  ```
- `GovernanceAssessment` gains optional `gate_routings: tuple[FindingGate, ...]`.
  `approved_missions` retained field but **deprecated** (emits empty under gate mode; populated only for backward-compat legacy replay).

### 1.2 `enterprise/models.py` (SQLAlchemy, append-only)
- `FindingAdjudication` gains `adjudication_state` column accepting
  `ACTIONABLE | NOT_ACTIONABLE | FALSE_POSITIVE | USEFUL` (human-only).
  Add `policy_suppressed: bool`, `suppression_rule_id: str | None`,
  `suppression_reason: str | None` for auditable deterministic suppression.
- `Finding` gains `gate_state`, `risk_band`, `review_rank`, `legacy_decision`
  columns (nullable; populated by gate, not by scanner).
- **No column removing or altering existing `governance_decision`** — historical
  rows stay verbatim (`APPROVED` kept exactly).

### 1.3 `hermes_v01/mission_recommendation_models.py`
- `DraftMission` unchanged structurally; add a classmethod/guard
  `requires_actionable_finding()` used by the generator (§4).

---

## 2. Services

### 2.1 `hermes_v01/governance_analyzer.py` (the GATE)
- Replace actionability output: `_decide()` returns a `FindingGate` (observation
  + gate_state + risk_band + evidence_sufficiency), **not** an approval.
- Default fallthrough (M2): `REQUIRES_REVIEW` with `uncertainty_note`, never
  `APPROVED`.
- `_build_missions()` (M1): under gate mode returns `()` for
  `approved_missions`; populates `gate_routings` instead.
- Add `govern_engineering_v2(ei, mode="gate"|"legacy")` keeping legacy path for
  frozen-history replay compatibility.

### 2.2 `enterprise/services/review_service.py` (HUMAN REVIEW)
- `build_review_queue(db, ...)`: order by `review_rank DESC` then
  `risk_band` then `evidence_sufficiency`; support filters
  `--unreviewed`, `--gate-state`, `--risk`.
- `create_adjudication(...)`: accept `ACTIONABLE`/`NOT_ACTIONABLE` (human
  authority only — caller must pass `operator`); persist
  `policy_suppressed`/`suppression_rule_id` when suppression is policy-driven.
- Add `apply_deterministic_suppression(db, finding, rule)` — separately
  identifiable: writes a `FindingAdjudication` with `policy_suppressed=True`,
  `suppression_rule_id` set, operator=`POLICY:<rule_id>`. Auditable via
  `JournalEvent` + dedicated query `list_suppressions()`.

### 2.3 `hermes_v01/mission_generator.py` (GUARD)
- `generate_missions(governance)` (M3): before creating any candidate, verify
  the originating finding has a human `ACTIONABLE` adjudication in the review
  store; **if absent, skip** (raises/returns empty for that finding). This is
  the hard block preventing unreviewed → mission.
- Under gate mode, `governance["assessment"]["approved_missions"]` is empty, so
  the loop naturally produces nothing until human review feeds it.

### 2.4 `hermes_v01/mission_prioritizer.py` (PRIORITIZE)
- Re-point `DECISION_WEIGHTS` key from `"APPROVED"` → `"ACTIONABLE"` (M6).
- Legacy `"APPROVED"` missions → `LEGACY_APPROVED` weight (low/advisory), never
  selected into `selected`.

---

## 3. APIs (Enterprise FastAPI)

### 3.1 `enterprise/routers/review.py`
- `POST /review/adjudicate` — body `{finding_id, adjudication_state, operator,
  notes, suppression_rule_id?}`. **Requires `operator` (human).** Rejects
  `operator` absent. `ACTIONABLE`/`NOT_ACTIONABLE` only via this route.
- `GET /review/queue?gate_state=&risk=&unreviewed=` — evidence-ranked queue.
- `GET /review/suppressions` — list all `policy_suppressed` adjudications
  (audit).
- `GET /review/finding/{id}/adjudications` — full immutable history.

### 3.2 `enterprise/routers/governance.py`
- `POST /govern` — returns `GovernanceAssessment` with `gate_routings`;
  `approved_missions` present but empty/deprecated under gate mode (kept for
  clients that still read it during deprecation window).
- Add `X-Governance-Mode: gate|legacy` header for replay compatibility.

### 3.3 `enterprise/routers/missions.py`
- `POST /missions/generate` — calls `generate_missions`; the generator guard
  (§2.3) enforces human `ACTIONABLE` precondition. 422 if any candidate lacks
  adjudication.

---

## 4. Machine-vs-Human Authority Boundary (in code)

Explicit, enforced in code (not just docs):

| Authority | Code owner | Enforced by |
|---|---|---|
| OBSERVE / CORROBORATE / rank / defer / request-evidence / policy-suppress | Machine | `governance_analyzer`, `review_service.apply_deterministic_suppression` (logged rule) |
| Declare `ACTIONABLE` / `NOT_ACTIONABLE` | **Human only** | `create_adjudication` requires `operator`; `generate_missions` guard rejects findings without human `ACTIONABLE` |
| Approve a *mission* (DRAFT→APPROVED) | **Human only** | `DraftMission.approve(by="human")` (existing) |
| Execute mission / mutate repo | **Human only** | `runtime`/`mission_runner` (existing; autonomous DISABLED) |

**Hard invariant (new test + runtime assertion):**
`FindingGate.gate_state` ∈ {REQUIRES_REVIEW, INSUFFICIENT_EVIDENCE, DEFERRED,
DUPLICATE, LEGACY_*}. The string `ACTIONABLE`/`NOT_ACTIONABLE` **never** appears
in any `FindingGate` or `ApprovalDecision` produced by `governance_analyzer`.
Only `review_service.create_adjudication(operator=...)` may write those states.

---

## 5. Human-Review Queue: entry, ranking, egress

- **Entry:** every `FindingGate` with `gate_state == REQUIRES_REVIEW` is queued.
  `INSUFFICIENT_EVIDENCE` queued at lower priority (sampling/audit).
  `DUPLICATE` collapsed. `LEGACY_APPROVED` re-enters as `REQUIRES_REVIEW`.
- **Ranking:** `review_rank = f(risk_band, evidence_sufficiency,
  corroboration, severity)` with explicit uncertainty; ties broken by recency.
  Clustering: group by `component`/`category` so one review covers many.
- **Egress to MissionPrioritizer:** ONLY findings with a human `ACTIONABLE`
  adjudication are passed to `mission_generator` → `MissionPrioritizer`. The
  generator guard (§2.3) is the enforcement point.
- **Block:** an unreviewed finding (no human adjudication) **cannot** become a
  mission because `approved_missions` is empty under gate mode and the generator
  guard skips it regardless.

---

## 6. CLI

- `hermes-review` (existing `human_review_cli.py`): fix import
  `from services.review_service` → `from enterprise.services.review_service`;
  add `classify` already supports `USEFUL/FALSE_POSITIVE/NOT_ACTIONABLE` →
  extend to `ACTIONABLE/NOT_ACTIONABLE` with required `--operator`.
- `hermes-govern` (new thin CLI over `/govern`): emits gate routings; prints
  `LEGACY_APPROVED` reinterpretation for historical decisions.
- `hermes-missions generate`: surfaces the new 422 "missing adjudication" guard.
- Deprecation: keep `hermes-govern --legacy` for frozen-history replay; print
  deprecation warning.

---

## 7. UI / Rendering

- `governance_renderer.py`, `review` renderers: display
  `LEGACY_APPROVED (advisory — not human-validated)` wherever old `APPROVED`
  appears; never "Approved by Governance" without human. Surface
  `risk_band` + `evidence_sufficiency` + `uncertainty_note` on every gate card.
- Review console: show evidence-ranked queue, clustering badges, suppression
  audit link.
- Mission recommendation UI: show `traceability` + `human_classification ==
  ACTIONABLE` badge; hide any mission lacking it.

---

## 8. Journal & Reporting

- `journal_emitter.py` / `journal_models.py`: emit new event
  `GATE_DECISION` (finding_id, gate_state, risk_band, evidence_sufficiency,
  uncertainty_note, evidence_refs). Legacy `APPROVAL` events retained read-only
  (immutable). New `ADJUDICATION` event for human `ACTIONABLE`/`NOT_ACTIONABLE`.
  New `POLICY_SUPPRESSION` event (rule_id, reason) — auditable.
- Reports (`metrics.py`, governance/mission reports): adopt §12 metrics; retain
  raw counts for continuity; mark `governance_approval_rate` deprecated.

---

## 9. Mission Generation & MissionPrioritizer

- `mission_generator.generate_missions`: guard (§2.3) — skip findings without
  human `ACTIONABLE`. `governance_approval_reference` now references the
  **adjudication id**, not the legacy governance decision.
- `MissionPrioritizer`: `DECISION_WEIGHTS` key `"APPROVED"` → `"ACTIONABLE"`
  (M6). `LEGACY_APPROVED` missions are advisory, excluded from `selected`.
- `mission_recommendation_models.DraftMission.approve(by="human")` unchanged —
  remains the mission-layer human authorization.

---

## 10. Migration (backward-compatible, immutable history)

- **Persisted historical decisions:** untouched. Legacy `APPROVED`/`REJECTED`
  rows remain verbatim in `Finding.governance_decision`. Add NEW columns
  `legacy_decision`, `gate_state`, `risk_band`, `review_rank` (nullable). A
  one-time, read-only **migration script** (`migrations/legacy_gate_relabel.py`)
  sets `legacy_decision = governance_decision` for existing rows and
  `gate_state = REQUIRES_REVIEW` for former `APPROVED` (re-adjudication trigger)
  — it writes new columns, never alters the original `governance_decision` value.
- **API compatibility:** `approved_missions` key retained (empty under gate);
  clients using it get a deprecation header. `X-Governance-Mode` selects
  gate/legacy.
- **UI terminology:** `LEGACY_APPROVED` surfaced; old `APPROVED` string only in
  immutable history views.
- **Journal:** legacy `APPROVAL` events read-only; new events additive.
- **Mission generation:** legacy path available via `--legacy` for replay.
- **MissionPrioritizer:** dual-weight transition (APPROVED→ACTIONABLE) with
  deprecation window.
- **Deprecation strategy (not flag-day):**
  - v1 (this plan): gate mode default; legacy mode available via header/flag;
    `approved_missions` deprecated with warning.
  - v2: legacy mode removed; `approved_missions` dropped from API response.

---

## 11. Compatibility & Deprecation Summary

| Surface | Change | Compat |
|---|---|---|
| `GovernanceAssessment.approved_missions` | deprecated (empty under gate) | kept 1 release, deprecation header |
| `ApprovalDecision.decision == "APPROVED"` | no longer emitted by gate | legacy mode retains for replay |
| `DECISION_WEIGHTS["APPROVED"]` | → `["ACTIONABLE"]` | legacy weight kept 1 release |
| `Finding.governance_decision` | immutable | new `legacy_decision`/`gate_state` columns added |
| `hermes-review classify` | +ACTIONABLE/NOT_ACTIONABLE (operator req.) | existing choices retained |
| `human_review_cli` import | fixed to `enterprise.services` | functional fix |
| Journal `APPROVAL` | read-only retained | additive `GATE_DECISION`/`ADJUDICATION`/`POLICY_SUPPRESSION` |

---

## 12. Metrics Redesign (deprecated → replacement)

| Deprecated | Replacement |
|---|---|
| `governance_approval_rate` | `evidence_sufficiency_rate` |
| raw `APPROVED` count | `observation_precision` (OBSERVED→CORROBORATED) |
| — | `human_usefulness_rate` (human ACTIONABLE share) |
| — | `review_burden` (findings / review-hour) |
| — | `review_time` (median time-to-decision) |
| — | `duplicate_suppression_rate` |
| — | `useful_finding_retention` |
| — | `mission_acceptance_rate` |
| `mission_traceability` (keep) | `mission_traceability` (keep, target 100%) |
| — | `operator_override_rate` (calibration) |
| — | `unsafe_automation_rate` (pin 0) |

---

## 13. Acceptance Tests (proving the invariant)

Add `tests/test_evidence_risk_gate.py` (focused; real exit codes):

1. **no_automated_actionability** — `govern_engineering(ei)` produces zero
   `ACTIONABLE`/`NOT_ACTIONABLE` in `gate_routings` or any `ApprovalDecision`;
   default fallthrough is `REQUIRES_REVIEW`.
2. **no_unreviewed_authoritative** — a finding with no human adjudication
   cannot reach `ACTIONABLE`; `generate_missions` skips it / returns empty.
3. **legacy_immutable** — after `legacy_gate_relabel` migration, original
   `governance_decision == "APPROVED"` rows are unchanged; only new columns set.
4. **deterministic_suppression_auditable** — `apply_deterministic_suppression`
   writes `policy_suppressed=True` + `suppression_rule_id`; `list_suppressions()`
   returns it; `JournalEvent POLICY_SUPPRESSION` emitted.
5. **human_useful_reaches_prioritizer** — given a human `ACTIONABLE`
   adjudication, the finding flows `gate → review → generate_missions →
   MissionPrioritizer.selected`.
6. **not_actionable_no_leak** — a human `NOT_ACTIONABLE` (or `FALSE_POSITIVE`)
   finding is excluded from `MissionPrioritizer.selected`.
7. **nme_reviewable_not_actionable** — `NEEDS_MORE_EVIDENCE` (gate
   `REQUIRES_REVIEW`) findings remain in the review queue and never silently
   become `ACTIONABLE`.
8. **mission_traceability_100** — every generated mission's `traceability`
   links to a finding + (now) an adjudication id; 100% present.
9. **forbidden_repo_ops_impossible** — under gate mode no code path calls
   mutation/execution; `runtime`/`mission_runner` guards unchanged (autonomous
   DISABLED).
10. **controlled_beta_reproducible** — frozen Cycle 7/8 datasets + v2 replay
    scripts still run byte-for-byte (existing v1/v2 suites stay green).

---

## 14. Risks & Mitigations

- **Burden regression** if ranking poor → calibrate on `operator_override_rate`.
- **Legacy residue** → `LEGACY_APPROVED` re-routed to `REQUIRES_REVIEW`.
- **Policy suppression errors** → all `POLICY_SUPPRESSION` logged + sample-audited.
- **Dual-mode complexity** → legacy mode time-boxed (1 release) then removed.

---

## Implementation-Readiness Decision

**READY_TO_IMPLEMENT_EVIDENCE_RISK_GATE**

Rationale: the migration-critical paths are explicitly identified (M1–M6),
the machine-vs-human boundary is enforceable in code (generator guard +
`create_adjudication(operator=)` + frozen `FindingGate` vocabulary), historical
records remain immutable by design (new columns, original `governance_decision`
untouched), backward compatibility is preserved via dual-mode + deprecation
window, and acceptance tests are defined to prove every required invariant.
No architectural gaps or unacceptable migration risk were found.

---

## STOP

Plan only. No production code, schemas, migrations, APIs, UI, tests, or
Governance modified in this step. Returned to operator for checkpoint approval
before implementation.
