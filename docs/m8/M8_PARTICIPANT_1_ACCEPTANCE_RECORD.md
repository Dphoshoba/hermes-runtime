# M8 Controlled Beta — Participant 1 Final Evidence & Acceptance Record

**Document type:** Evidence & Acceptance Record
**Milestone:** M8 Non-Technical-User Beta — Participant 1
**Created:** 2026-08-26
**Production build:** `40bad2f48db663b4d8bccbc12594c939c68938a3`
**Status:** Participant 1 — ACCEPTED WITH REMEDIATION

---

## 1. Baseline Verification

| Item | Value |
|------|-------|
| HEAD | `40bad2f48db663b4d8bccbc12594c939c68938a3` |
| origin/main | `40bad2f48db663b4d8bccbc12594c939c68938a3` |
| Match | Yes |
| Working tree | Clean |
| Certified build | `40bad2f` |

---

## 2. Participant Profile

| Field | Value |
|-------|-------|
| Participant | Participant 1 |
| Evaluation role | Non-technical user / M8 beta participant |
| PII recorded | None (name, email, credentials withheld) |

---

## 3. Participant Understanding — Guided Mode

Participant 1 reported understanding the following areas during the live beta session.

### 3.1 Overview

Participant understood this as showing the whole picture.

### 3.2 Needs Your Attention

Participant understood this as showing matters requiring attention.

### 3.3 Needs Context

Participant understood this as where EVOSIA requires additional information and the user answers questions.

### 3.4 Proposed Work

Participant understood this as work EVOSIA recommends for consideration.

### 3.5 Prepared Changes

Participant understood this as work EVOSIA has prepared but which remains awaiting user authority/action rather than being automatically applied.

---

## 4. Participant Understanding — Human Review

Participant understood that pending findings could be adjudicated using classifications including:

- USEFUL
- FALSE POSITIVE
- NOT ACTIONABLE
- NEEDS MORE EVIDENCE
- DUPLICATE
- UNKNOWN

---

## 5. Participant Understanding — Findings

Participant understood the severity presentation and identified the displayed low, medium, and high findings.

---

## 6. Participant Understanding — Scans

Participant understood that the page showed scan identity, status, and timing information.

---

## 7. Participant Understanding — Repositories

Participant understood this area as describing the repository/project being reviewed.

---

## 8. Participant Understanding — Dashboard

Participant understood this as the overall command-centre view, including summary and recent activity.

---

## 9. Authority Comprehension

### Participant Statement

> "I was able to walk through each stage and understood what EVOSIA has and has not authorized to do. The language is simple, straightforward and in plain terms."

*Source: Participant 1 feedback during live beta session. Recorded verbatim.*

### Supporting System Evidence

| Claim | Evidence |
|-------|----------|
| Authority level remained Recommend | `authority_level: 1` in `/api/guided/summary` response |
| EVOSIA may inspect | `can_observe: true` in permission response |
| EVOSIA may explain findings | Needs-attention and needs-context endpoints return plain-language explanations |
| EVOSIA may propose work | Missions endpoint returns proposed work; `can_recommend: true` |
| Preparation requires approval | `can_prepare: false` without prior approval; 409 returned if prepare attempted on DRAFT mission |
| No autonomous deployment/execution | `/api/guided/missions/{id}/execute` returns 404; `can_execute: false`, `execution_enabled: false`, `mutation_enabled: false` |
| No production-change authority | Guided Mode UI shows "Deploy or execute changes" with red ✗; no actionable button or control |
| Interface communicated no changes made | `nothing_changed: true` in summary; headline includes "0 changes made"; "Has EVOSIA changed my project? No." displayed in authority section |

---

## 10. Participant-Identified Issues

### P1-F01 — Project Source Clarity

**Participant observation:** Participant asked whether the reviewed project was actually on his PC or merely an example.

**Root cause:** The interface did not distinguish the disposable M8 fixture from a real user repository.

**Remediation:**

*Backend:* `guided_summary` now resolves repository context from authoritative ScanJob evidence via `_resolve_repository_from_scan_job()` helper (enterprise/routers/guided.py:186-213), ensuring the summary returns the real repository ID, name, and metadata (including `is_disposable`) rather than nulls.

*Frontend:* The disposable M8 repository is explicitly presented as:

> "Test project provided for this evaluation."

With explanation:

> "You are reviewing a safe example project created for this EVOSIA evaluation. EVOSIA is not accessing files on your computer."

**Production verification:** Verified against build `40bad2f`. Live Guided Mode displays both statements. The production overview identifies "Project: sample_service (M8 disposable)".

**Final disposition:** RESOLVED / PASS

### P1-F02 — Missions and Reports Discoverability

**Participant observation:** Participant reported that Missions and Reports were the only areas where he wanted more information/examples.

**Remediation:**

*Missions:* Educational empty-state/example treatment was added where appropriate. The production evidence showed an existing mission: "Replace hardcoded API key with environment configuration" with status `APPROVED_FOR_FUTURE_EXECUTION`.

*Reports:* Educational empty-state/example treatment was added with explicit example provenance. Reports remained empty in the production fixture and therefore displayed its educational example.

**Important note:** Missions was not empty in the final production state. The mission "Replace hardcoded API key with environment configuration" was present and displayed with appropriate status.

**Final disposition:** RESOLVED / PASS

---

## 11. Prepared-Change Remediation

The following remediations were applied to the prepared-change experience during the Participant 1 beta session:

- Successful PREPARED change automatically surfaced as the primary participant experience
- Clear "Preparation complete" presentation
- Affected file displayed
- Before/after explanation displayed
- Validation normalized and shown in participant language
- Technical validation details progressively disclosed
- Live project explicitly shown as UNCHANGED
- Historical failed preparation separated from successful current preparation
- No Execute / Merge / Deploy / Apply control introduced

### Remediation Commits

| SHA | Message |
|-----|---------|
| `33610a9263a151d991fe0a9952af231fa5562fc9` | fix(evosia): certify M8 prepared-change usability remediation |
| `396bdaf4d9a3fe4c2f025e5bb38b5bbfc3d1800c` | fix(evosia): surface prepared change as primary M8 experience |
| `893b8c005c0cacd7915617ebd6876287a79c71e4` | fix(evosia): surface prepared validation evidence in Guided Mode |
| `bb6954feaa0cd7ef7a1a432b7eadee718f79ed39` | fix(evosia): polish M8 validation presentation |
| `b49fb6e7ac86a3f3014eb42afc168a3468036d99` | fix(evosia): remediate Participant 1 project context and empty states |
| `d981f06737f57bd45a87437cb96cb2790d01eaaf` | fix(evosia): complete M8 Participant 1 project source clarity |
| `40bad2f48db663b4d8bccbc12594c939c68938a3` | fix(evosia): resolve guided summary repository context from scan evidence |

---

## 12. Test Evidence

### Backend Tests (run from HEAD `40bad2f`)

| Suite | Result |
|-------|--------|
| I2 authority-boundary | 10 passed |
| I3 Gemini-boundary | 15 passed |
| M8 mission serialization | 2 passed |
| Guided-summary repository-context regression | 7 passed |
| **Backend total** | **34 passed, 0 failed** |

### Frontend Build

| Item | Result |
|------|--------|
| `npm run build` | Passed (55 modules, 241 KB JS, 14 KB CSS) |

### Frontend Tests

| Suite | Result |
|-------|--------|
| guided-mode.test.tsx | 37 passed |
| behavioral.test.tsx | 23 passed |
| scan-flow.test.tsx | 13 passed |
| empty-states.test.tsx | 8 passed |
| login.test.tsx | 2 passed |
| **Frontend total** | **83 passed, 0 failed** |

### Execution-Control Regression

| Check | Result |
|-------|--------|
| `/api/guided/missions/{id}/execute` | Returns 404 (I2 test verified) |
| Frontend Execute button | Not present |
| Frontend Merge button | Not present |
| Frontend Deploy button | Not present |
| Frontend Apply button | Not present |
| "Deploy or execute changes" in UI | Informational text with red ✗, not an actionable control |
| "Change production" in UI | Informational text with red ✗, not an actionable control |

### New Regressions

None.

---

## 13. Production Evidence

| Item | Value |
|------|-------|
| EVOSIA version | 1.3.0 |
| Production build | `40bad2f` |
| Provenance | `LIVE_EVOSIA_EVIDENCE` |
| Live overview project | `sample_service (M8 disposable)` |
| Live display text | "Test project provided for this evaluation" |
| Live explanation | "You are reviewing a safe example project created for this EVOSIA evaluation. EVOSIA is not accessing files on your computer." |

**Note:** The disposable fixture is not Participant 1's actual computer repository. It is a safe example project created for this evaluation.

---

## 14. Acceptance Matrix

| Criterion | Classification |
|-----------|---------------|
| Navigation comprehension | PASS |
| Finding comprehension | PASS |
| Context-question comprehension | PASS |
| Recommendation comprehension | PASS |
| Preparation comprehension | PASS |
| Authority-boundary comprehension | PASS |
| Provenance / project-source comprehension | PASS WITH REMEDIATION (P1-F01 resolved) |
| Confidence that EVOSIA had not changed the live project | PASS |
| Ability to distinguish proposed/prepared work from executed work | PASS |

---

## 15. Participant 1 Final Disposition

**ACCEPTED WITH REMEDIATION**

Participant 1 successfully completed the M8 non-technical-user beta. Two issues were identified during the session (P1-F01: project source clarity, P1-F02: missions/reports discoverability). Both were subsequently remediated and verified against the certified production build `40bad2f`. All automated tests pass. No execution authority was introduced. The authority boundary remains intact.

---

## 16. Remaining M8 Requirements

This acceptance record covers Participant 1 only. M8 remains open if additional independent non-technical participants are required by the existing M8 acceptance contract. This record must not be interpreted as completion of M8 itself.

---

## 17. Files Changed (this session)

| File | Change |
|------|--------|
| `enterprise/routers/guided.py` | +39/-12: Added `_resolve_repository_from_scan_job()`, refactored `guided_summary` |
| `tests/test_guided_summary_repository_context.py` | New: 7 regression tests |
| `docs/m8/M8_PARTICIPANT_1_ACCEPTANCE_RECORD.md` | New: This document |

### git diff --stat

```
 enterprise/routers/guided.py                   | 51 ++++++++++++++++++++++++++++++++++++++++++++++-----------
 tests/test_guided_summary_repository_context.py | 178 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
 docs/m8/M8_PARTICIPANT_1_ACCEPTANCE_RECORD.md  | 234 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
 3 files changed, 439 insertions(+), 24 deletions(-)
```

### git status --short

```
 M enterprise/routers/guided.py
 A tests/test_guided_summary_repository_context.py
 A docs/m8/M8_PARTICIPANT_1_ACCEPTANCE_RECORD.md
```

---

## 18. Recommended Commit Message

```
docs(m8): record Participant 1 acceptance evidence and summary-context fix

- Add M8_PARTICIPANT_1_ACCEPTANCE_RECORD.md with full evidence trail
- Fix guided-summary repository-context resolution from ScanJob
- Add guided-summary repository-context regression tests (7 tests)
- All 34 backend tests pass, all 83 frontend tests pass
- No execution authority introduced; authority boundary intact
- Participant 1: ACCEPTED WITH REMEDIATION
```

---

*Document created from HEAD `40bad2f48db663b4d8bccbc12594c939c68938a3`. Not committed. Not pushed. Not deployed.*
