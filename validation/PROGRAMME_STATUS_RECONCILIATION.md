# EVOSIA Programme Status Reconciliation

**Date:** 2026-08-30
**Certified HEAD:** `9e1cee00d54d81972b1597a5c7c29cd7412aa4ef`
**Purpose:** Reconcile overlapping milestone systems, clarify contradictions, and establish current programme state.

---

## 1. Programme Structure

The repository contains three parallel milestone systems. They are NOT sequential phases of a single programme. They are independent tracks with cross-references.

### Track A: Product Acceptance (M0–M13)

The primary governing programme. Defined in `validation/PRODUCT_ACCEPTANCE_REPORT.md`. Tracks product readiness from canonical baseline through execution readiness.

### Track B: Hosted Beta / Desktop Track (M0–M23)

Infrastructure and deployment milestones for hosted and desktop distribution. Defined in `validation/beta/README.md`. Tracks deployment infrastructure (GitHub App, Cloud SQL, Docker, Apple Signing). Independent of Track A except for cross-references.

### Track C: Controlled Beta Evidence Cycles (Phases 1–6)

Historical evidence collection and analysis cycles. Defined in `CONTROLLED_BETA_PHASE_*_REPORT.md`. These are completed evidence-gathering iterations, not active programme gates.

**Do not merge these numbering systems. Do not renumber milestones.**

---

## 2. Track A — Product Acceptance M0–M13

| Milestone | Status | Classification | Notes |
|-----------|--------|---------------|-------|
| M0 Canonical Backend | PASS | COMPLETE | 1419 tests, invariants held |
| M1 Guided Mode E2E | PASS | COMPLETE | 8/8 tests, summary→safe end state |
| M2 First-Run Onboarding | PASS | COMPLETE | 5-step progressive walkthrough |
| M3 Context Collection | PASS | COMPLETE | NME clustering, plain-language questions |
| M4 Disposable Repo | PASS | COMPLETE | Seeded fixture with security finding |
| M5 Prepared Change E2E | PASS | COMPLETE | Schema/API implemented, TARGET_REPOSITORY_MUTATIONS=0 |
| M6 Change Explanation | PASS | COMPLETE | Guided mission cards with What/Why/Risk |
| M7 Authority UX | PASS | COMPLETE | Visual states, safety badge |
| M8 Real User Usability | PARTIALLY SATISFIED | DEFERRED — HUMAN | 1 of 5–8 participants completed; additional deferred by programme-owner decision |
| M9 Authority Comprehension | NOT_OBSERVED | DEFERRED — HUMAN | Blocked on M8 |
| M10 Expert Mode | PASS | COMPLETE | Existing views preserved |
| M11 Install Friction | PASS (documented) | COMPLETE | Gaps documented |
| M12 Safety Regression | PASS | COMPLETE | 1419 passed, invariants verified |
| M13 Execution Readiness | NOT_READY | BLOCKED — HUMAN | Technical blocker SATISFIED; human-validation dependency DEFERRED |
| C3 Production Verification | COMPLETE | COMPLETE | Production deployment, migration adoption, build provenance, readiness verified |

### M5 / M13 Clarification

M5 and M13 are NOT contradictory:

- **M5 gate:** PASS — for its own historical scope (schema/API implementation, TARGET_REPOSITORY_MUTATIONS=0)
- **M13 additional E2E requirement:** historically unresolved, now SATISFIED by subsequent evidence (`validation/M13_PREPARED_CHANGE_E2E_RECONCILIATION.md`)

M5 passing its own gate does not mean M13's stronger E2E requirement was met at the same time. M13 required exercised evidence that M5's schema-level guarantee did not provide.

### M8 / M9 Clarification

M8 and M9 use the same protocol:

- M8-P0 Facilitator Package (`validation/usability/M8P0_FACILITATOR_PACKAGE.md` line 7): "It reuses the certified M8 protocol (`M9_REAL_USER_TEST_PROTOCOL.md`) and acceptance criteria."
- M8 = the usability beta activity (task completion, authority comprehension)
- M9 = the acceptance gate derived from M8 results (EXECUTION_AUTHORITY_COMPREHENSION = 100%)
- M9 is NOT a separate human session — it is the evaluation of M8 results against authority-comprehension thresholds

---

## 3. Track B — Hosted Beta / Desktop Track

| Milestone | Status | Classification |
|-----------|--------|---------------|
| M0 Baseline | PASS | COMPLETE |
| M1 Threat Model | DONE | COMPLETE |
| M2 Tenant Isolation | IN PROGRESS | ENGINEERING WORK REMAINING |
| M3 Invite-Only Auth | IN PROGRESS | ENGINEERING WORK REMAINING |
| M4 GitHub App | OPERATOR ACTION REQUIRED | BLOCKED — EXTERNAL OPERATOR |
| M5 Demo Project | IN PROGRESS | ENGINEERING WORK REMAINING |
| M6 Ephemeral Repo | DOCUMENTED | COMPLETE |
| M7 PostgreSQL | SUPPORTED | COMPLETE |
| M8 Secrets | DOCUMENTED | COMPLETE |
| M9 Dockerfile | DONE | COMPLETE |
| M10–M16 Hosted Deployment | OPERATOR ACTION REQUIRED | BLOCKED — EXTERNAL OPERATOR |
| M17–M23 Desktop Track | OPERATOR ACTION REQUIRED | BLOCKED — EXTERNAL OPERATOR |

**Relationship to Track A:** Track B is an independent infrastructure track. Its milestones do not gate Track A's product acceptance, and vice versa. However, Track B's deployment milestones must be completed before a hosted production deployment can occur.

**Railway deployment note:** EVOSIA is currently deployed on Railway. Some historical hosted-beta documents may be stale because they reference GCP/Cloud Run. The current Railway deployment supersedes some of these requirements.

---

## 4. Track C — Controlled Beta Evidence Cycles

| Phase | Status | Outcome |
|-------|--------|---------|
| Phase 1: Promotion | COMPLETE | EVIDENCE_RISK_GATE frozen as baseline |
| Phase 2: Acceptance + Expansion | COMPLETE | 100 findings reviewed, 13 ACTIONABLE |
| Phase 3: Evidence Resolution | COMPLETE | 62 NME gap taxonomy, 33.9% resolution |
| Phase 4: Evidence Refinement | COMPLETE | 40/62 NME resolved (64.5%) |
| Phase 5: Decision Evidence | COMPLETE | bugfix=0, uniformly WEAK/ISOLATED |
| Phase 6: Call-Graph Mining | COMPLETE | REPOSITORY_LOCAL_EVIDENCE_EXHAUSTED |

All phases are completed. No active evidence cycles remain.

---

## 5. Track D — Local Agent Programme (LA0–LA6)

| Milestone | Status | Classification | Notes |
|-----------|--------|---------------|-------|
| LA0 Architecture / trust boundaries | PASS | COMPLETE | Outbound HTTPS, no inbound ports, control/work plane separation |
| LA1 Device trust domain | PASS | COMPLETE | Device identity, bootstrap, credential, revocation, heartbeat |
| LA2 Local Agent runtime | PASS | COMPLETE | evosia_agent runtime, local credential storage, retry/backoff |
| LA3 Explicit project authorization | PASS | COMPLETE | Human authorization, REVIEW_ONLY, symlink escape protection |
| LA4 Governed read-only PROJECT_SCAN | PASS | COMPLETE | Bounded scanner, shell=False, LIVE_EVOSIA_EVIDENCE provenance |
| LA5 Computers / Project Review UX | PASS | COMPLETE | Computers page, review history, accessibility, no execution controls |
| LA6 Real second-computer validation | PASS | COMPLETE | Acer 1 (Windows), evosia-local-agent, full lifecycle verified |

**Programme disposition:** COMPLETE — All milestones LA0–LA6 technically complete and production-validated.

**Certification document:** `validation/LOCAL_AGENT_PRODUCTION_CERTIFICATION.md`

**Do not conflate Local Agent programme completion with human beta milestones (M8/M9/M13).**

---

## 6. Participant Evidence (M8/M9)

| Participant | Status | Evidence |
|-------------|--------|----------|
| Participant 1 | ACCEPTED WITH REMEDIATION | `docs/m8/M8_PARTICIPANT_1_ACCEPTANCE_RECORD.md` |
| Participants 2–5+ | DEFERRED/SUSPENDED | No evidence (by programme-owner decision) |

**M8 participant count:** Original target 5–8 (USABILITY_BETA_PROTOCOL.md:17, M9 protocol:21). Participant 1 completed. Additional participants deferred by programme-owner decision. M8 remains open/partially satisfied.

---

## 7. Documentation Contradictions Resolved

### A. M8 Participant Count

- Original wording: "Minimum recommended: 5 users" (USABILITY_BETA_PROTOCOL.md:17)
- M9 protocol wording: "Target: 5–8 participants" (M9_REAL_USER_TEST_PROTOCOL.md:21)
- **Resolution:** Original target remains 5–8. Participant 1 completed. Additional participants deferred. M8 remains open/partially satisfied. Not called PASS.

### B. M8/M9 Overlap

- M8-P0 package reuses M9 protocol (M8P0_FACILITATOR_PACKAGE.md:7)
- **Resolution:** M8 = usability beta activity. M9 = authority-comprehension acceptance gate evaluated from M8 results. Same protocol, different evaluation scope. No duplicate human sessions required.

### C. M5/M13 Apparent Contradiction

- M5: PASS (for its own gate scope)
- M13: required stronger E2E evidence (now SATISFIED)
- **Resolution:** M5 gate = PASS. M13 additional E2E requirement = SATISFIED by subsequent evidence. Not contradictory once scope is stated. See `validation/M13_PREPARED_CHANGE_E2E_RECONCILIATION.md`.

### D. Parallel Milestone Systems

- Track A (M0–M13): Product acceptance
- Track B (M0–M23): Hosted/Desktop deployment
- Track C (Phases 1–6): Evidence cycles
- **Resolution:** Three independent tracks with cross-references. Not sequential phases. Do not merge numbering.

---

## 8. Current Programme State

### Engineering Programme: COMPLETE

All engineering work required by existing active contracts that can be completed without additional human participants or external operator actions is complete.

### C3 Production Verification: COMPLETE

Production deployment verified. Migration adoption verified. Build provenance verified. Readiness verified. See `validation/C3_PRODUCTION_VERIFICATION.md`.

### Technical Acceptance: COMPLETE

All relevant tests pass. Authority boundaries verified. Safety invariants held.

### Local Agent Programme LA0–LA6: COMPLETE

All Local Agent milestones technically complete and production-validated. Second-computer governed PROJECT_SCAN lifecycle verified on Acer 1 (Windows). See `validation/LOCAL_AGENT_PRODUCTION_CERTIFICATION.md`.

### Participant 1: ACCEPTED WITH REMEDIATION

Sealed at `22a38ce`. Evidence at `docs/m8/M8_PARTICIPANT_1_ACCEPTANCE_RECORD.md`.

### Multi-Participant Human Validation: DEFERRED

Additional M8 participants deferred by programme-owner decision. Original target 5–8. Current: 1.

### M9 Human Authority Validation: DEFERRED/BLOCKED

Blocked on M8 completion.

### M13 Execution Readiness: NOT READY / DEFERRED ON HUMAN EVIDENCE

Technical blocker SATISFIED. Human-validation dependency DEFERRED.

### Execution Authority: NOT GRANTED

No execution authority has been introduced. All invariants hold.

---

## 9. Known Limitations

1. M8 human-usability evidence is limited to 1 participant (target: 5–8)
2. M9 authority comprehension not independently verified with multiple participants
3. Hosted deployment milestones (M2, M3, M4, M5 in Track B) have engineering work remaining
4. External operator actions required for GitHub App registration, cloud deployment, Apple signing
5. Railway deployment supersedes some historical hosted-beta documentation
6. `rollback_representation` is schema/representation evidence, not execution evidence

---

## 10. Source Documents

| Document | Path |
|----------|------|
| Product Acceptance Report | `validation/PRODUCT_ACCEPTANCE_REPORT.md` |
| Execution Readiness Assessment | `validation/EXECUTION_READINESS_ASSESSMENT.md` |
| M13 E2E Reconciliation | `validation/M13_PREPARED_CHANGE_E2E_RECONCILIATION.md` |
| M8 Usability Protocol | `validation/usability/USABILITY_BETA_PROTOCOL.md` |
| M8-P0 Facilitator Package | `validation/usability/M8P0_FACILITATOR_PACKAGE.md` |
| M9 Real User Test Protocol | `validation/usability/M9_REAL_USER_TEST_PROTOCOL.md` |
| Beta Deployment README | `validation/beta/README.md` |
| Participant 1 Acceptance Record | `docs/m8/M8_PARTICIPANT_1_ACCEPTANCE_RECORD.md` |
| Controlled Beta Phase Reports | `CONTROLLED_BETA_PHASE_*_REPORT.md` |
| C3 Production Verification Record | `validation/C3_PRODUCTION_VERIFICATION.md` |
| Final Engineering Certification | `validation/FINAL_ENGINEERING_CERTIFICATION.md` |
| Local Agent Production Certification | `validation/LOCAL_AGENT_PRODUCTION_CERTIFICATION.md` |

---

*This document reconciles overlapping milestone systems without rewriting history. It establishes the current programme state based on repository evidence.*
