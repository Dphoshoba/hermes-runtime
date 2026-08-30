# EVOSIA Local Agent Production Certification — LA0–LA6

**Date:** 2026-08-30
**Certification HEAD:** `9e1cee00d54d81972b1597a5c7c29cd7412aa4ef`
**EVOSIA Version:** 1.3.0
**Purpose:** Formally close the EVOSIA Local Agent LA0–LA6 production-validation programme using the certified implementation and real-world evidence now obtained.

---

## 1. Programme Summary

The Local Agent programme defines a layered trust architecture for read-only governed review of projects on separate computers. Each milestone adds capability while preserving all previously established authority boundaries. LA0–LA6 is now complete and production-validated.

---

## 2. Milestone Record

### LA0 — Architecture / Trust-Boundary Definition

**Status: PASS**

| Field | Value |
|-------|-------|
| Outbound HTTPS agent architecture | IMPLEMENTED |
| No inbound ports | ENFORCED |
| Cloud control plane / device work plane separation | ENFORCED |
| One-time device bootstrap | IMPLEMENTED |
| No email/password agent authentication | ENFORCED |
| Explicit authority boundaries | DEFINED |

### LA1 — Device Trust Domain

**Status: PASS**

| Field | Value |
|-------|-------|
| Device identity (UUID) | IMPLEMENTED |
| Bootstrap token (single-use, short-lived) | IMPLEMENTED |
| Device credential (JWT, device-scoped) | IMPLEMENTED |
| Revocation | IMPLEMENTED |
| Heartbeat | IMPLEMENTED |
| Cross-user isolation | ENFORCED |
| No secrets in audit metadata | ENFORCED |

### LA2 — Local Agent Runtime

**Status: PASS**

| Field | Value |
|-------|-------|
| evosia_agent runtime | IMPLEMENTED |
| Local credential storage | IMPLEMENTED |
| Heartbeat | IMPLEMENTED |
| Retry/backoff (5s → 10s → 30s → 60s max) | IMPLEMENTED |
| Revocation/expiry fail closed | ENFORCED |
| No project access granted implicitly | ENFORCED |

### LA3 — Explicit Project Authorization

**Status: PASS**

| Field | Value |
|-------|-------|
| Explicit human authorization | IMPLEMENTED |
| Canonical local root | IMPLEMENTED |
| Fingerprint (SHA-256 of canonical path) | IMPLEMENTED |
| Raw path remains local | ENFORCED |
| REVIEW_ONLY authority | ENFORCED |
| Symlink escape protection | IMPLEMENTED |
| Sensitive-file classification | IMPLEMENTED |
| No broad filesystem discovery | ENFORCED |

### LA4 — Governed Read-Only PROJECT_SCAN

**Status: PASS**

| Field | Value |
|-------|-------|
| Human-created scan jobs | ENFORCED |
| Agent cannot manufacture work | ENFORCED |
| Only PROJECT_SCAN operation type | ENFORCED |
| Bounded scanner | ENFORCED |
| Sensitive contents excluded | ENFORCED |
| Hardcoded git metadata allowlist | ENFORCED |
| shell=False | ENFORCED |
| No generic subprocess runner | ENFORCED |
| LIVE_EVOSIA_EVIDENCE provenance | ENFORCED |
| Project-tree immutability checking | ENFORCED |

**Scanner limits:**

| Limit | Value |
|-------|-------|
| Max file size | 1 MB |
| Max total read | 10 MB |
| Max files | 5,000 |
| Timeout | 120 seconds |

```
ALLOWED_OPERATION_TYPES = frozenset({"PROJECT_SCAN"})
```

### LA5 — Computers / Project Review UX

**Status: PASS**

| Field | Value |
|-------|-------|
| Computers page | IMPLEMENTED |
| Online/offline/revoked device state | IMPLEMENTED |
| Project authorization | IMPLEMENTED |
| Review Project button | IMPLEMENTED |
| Review history | IMPLEMENTED |
| Provenance display | IMPLEMENTED |
| Truncation disclosure | IMPLEMENTED |
| Accessibility (ARIA roles, keyboard) | IMPLEMENTED |
| No execution/merge/deploy controls | ENFORCED |

### LA6 — Real Second-Computer Production Validation

**Status: PASS**

Production-validated on a real second computer with a real governed PROJECT_SCAN lifecycle.

See sections 3–10 for full evidence record.

---

## 3. Production Device Evidence

| Field | Value |
|-------|-------|
| Device display name | Acer 1 |
| Platform | Windows |
| Agent version | evosia-agent/0.1.0 |
| Device status | ONLINE |

---

## 4. Production Project Evidence

| Field | Value |
|-------|-------|
| Project name | evosia-local-agent |
| Authority | REVIEW_ONLY |
| Operation type | PROJECT_SCAN |

---

## 5. Real Production Lifecycle

The following lifecycle was visually verified in the production UI:

```
Human clicks Review project
    ↓
Review queued
    ↓
Review in progress
    ↓
Review complete
    ↓
Project unchanged
```

After completion, the "Review project" button returned to its normal available state.

---

## 6. Source-Tree Immutability Evidence

Direct verification was performed on the Acer after real PROJECT_SCAN runs:

```
git status --short
```

Result: no output

Recorded: **source-tree mutation = VERIFIED NO**

Be precise: This verifies the Git working tree remained clean for the authorized repository at the verification point. Do not overstate this as proof about files outside the authorized project.

Production UI evidence: **"✓ Project unchanged"**

---

## 7. Scanner Limitation Disclosure

Production UI correctly displayed:

> "Review completed with limits. EVOSIA reached its review limits, so some files may not have been examined."

Recorded: **bounded-scan disclosure = VERIFIED**

Successful review completion means the governed bounded scan completed, not that exhaustive repository analysis is guaranteed.

---

## 8. Double-Click Remediation

### Defect Discovered

During LA6 production validation, a production UX defect was observed:

- Same-tick double-click on "Review project" could issue two POST attempts
- First POST created the scan successfully (201 Created)
- Backend active-job guard rejected the second with HTTP 409 Conflict
- Second request error could clear/overwrite the successful "Review queued" acknowledgement

### Safety Result

Even before remediation:

- Backend prevented duplicate active PROJECT_SCAN creation
- No duplicate authority was granted
- No duplicate execution occurred
- No source corruption occurred

### Remediation Applied

- Synchronous `useRef` request guard: `requestingScanRef`
- `revokeRef` for revoke action
- `authRef` for authorization action
- React state retained for visual UI state
- Backend 409 guard retained as defense in depth

### Final Production Verification

| State | Visible |
|-------|---------|
| Review queued | YES |
| Review in progress | YES |
| Review complete | YES |
| Project unchanged | YES |

Remediation commit: `9e1cee00d54d81972b1597a5c7c29cd7412aa4ef`

---

## 9. Active-Job Backend Guard

New PROJECT_SCAN is rejected when the same DeviceProject already has:

| Status | Blocks new scan |
|--------|----------------|
| PENDING | YES |
| STARTED | YES |
| COMPLETED | NO |
| FAILED | NO |

Response: `HTTP 409 Conflict` — "A review is already in progress for this project"

Guard is scoped to the same DeviceProject. Different authorized DeviceProjects remain independent.

---

## 10. Authority Invariants

### Certified Authority State

| Invariant | Status |
|-----------|--------|
| DeviceProject authority | REVIEW_ONLY |
| ALLOWED_OPERATION_TYPES | `frosenset({"PROJECT_SCAN"})` |
| Execution authority | NOT GRANTED |
| Merge authority | NOT GRANTED |
| Deployment authority | NOT GRANTED |
| Autonomous job creation | NOT GRANTED |
| Arbitrary shell capability | NOT GRANTED |
| Filesystem scope expansion | NOT GRANTED |

### Local Agent DOES NOT Possess Authority To

- Execute arbitrary commands
- Edit project files
- Merge code
- Deploy changes
- Prepare changes
- Autonomously create PROJECT_SCAN work
- Expand filesystem scope without authorization

Cloud/user authority remains responsible for creating governed work. Device agent performs only allowed assigned work.

---

## 11. Security / Privacy Boundaries

| Property | Status |
|----------|--------|
| No inbound port required | ENFORCED |
| Outbound HTTPS model | ENFORCED |
| Device credential scoped to device | ENFORCED |
| Revocation supported | ENFORCED |
| Project authorization explicit | ENFORCED |
| Authorization tokens single-use / bounded | ENFORCED |
| Raw absolute project paths remain local | ENFORCED |
| Sensitive file contents excluded | ENFORCED |
| No arbitrary shell runner | ENFORCED |
| Git commands hardcoded and bounded | ENFORCED |
| Project root containment enforced | ENFORCED |
| Symlink escape fails closed | ENFORCED |

---

## 12. Production Baseline

| Field | Value |
|-------|-------|
| Production commit | `9e1cee00d54d81972b1597a5c7c29cd7412aa4ef` |
| /api/version | 1.3.0 |
| /api/health | ok |
| /api/ready | ok, database connected |
| Production bundle | `index-D2qF3j3k.js` |

---

## 13. Programme Reconciliation

| Field | Status |
|-------|--------|
| Local Agent Programme LA0–LA6 | COMPLETE |
| Technical implementation | COMPLETE |
| Second-computer validation | COMPLETE |
| Production validation | COMPLETE |
| Cross-PC governed PROJECT_SCAN | VERIFIED |
| Source-tree immutability | VERIFIED |
| Authority boundary | PRESERVED |
| Execution authority | NOT GRANTED |
| Autonomous execution | NOT GRANTED |

### Relationship to Human Beta Milestones

The Local Agent production validation does NOT automatically satisfy additional non-technical-user beta requirements. M8, M9, and M13 remain at their previously established status as recorded in `validation/PROGRAMME_STATUS_RECONCILIATION.md`.

---

## 14. Final Acceptance Statement

EVOSIA Local Agent LA0–LA6 is technically complete and production-validated.

A human-authorized REVIEW_ONLY project on a separate Windows computer was successfully connected to EVOSIA Cloud and processed through a governed PROJECT_SCAN lifecycle.

The production lifecycle was visibly verified from human request through queued, active, and completed states.

The authorized project remained unchanged.

The agent received no execution, merge, deployment, preparation, or autonomous-work authority.

The Local Agent programme is therefore accepted for its defined read-only governed-review scope.

---

## 15. Test / Change Scope

| Field | Status |
|-------|--------|
| Application code changed | NO |
| Frontend code changed | NO |
| Backend code changed | NO |
| Agent code changed | NO |
| Migration | NO |
| Production DB mutation | NO |

This document is documentation-only.

---

## 16. Certification Record

| Field | Value |
|-------|-------|
| Document | LOCAL_AGENT_PRODUCTION_CERTIFICATION.md |
| Date | 2026-08-30 |
| Certification HEAD | `9e1cee00d54d81972b1597a5c7c29cd7412aa4ef` |
| EVOSIA version | 1.3.0 |
| LA0 | PASS |
| LA1 | PASS |
| LA2 | PASS |
| LA3 | PASS |
| LA4 | PASS |
| LA5 | PASS |
| LA6 | PASS |
| Programme disposition | COMPLETE |

---

**STOP. No production mutations performed. No execution authority granted. No new programme started.**
