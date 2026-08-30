# Post-P3e Programme Reconciliation

**Date:** 2026-08-30
**Canonical Baseline:** `d1ab8e1a33daf4ee490f9d4df0c57ceb8591131c`
**Purpose:** Reconcile the original P0–P8 programme roadmap against actual P3a–P3e implementation, classify remaining work, and define the next milestone.

---

## 1. Purpose

The Productization Programme has advanced through P0–P3e. The original programme assumed P4/P5/P6 would be implemented as independent engineering milestones. P3a–P3e have substantially satisfied those objectives. This document reconciles the roadmap, preserves canonical milestone identities, and defines the path forward.

---

## 2. Canonical Starting Baseline

| Field | Value |
|-------|-------|
| P3e implementation commit | `d1ab8e1a33daf4ee490f9d4df0c57ceb8591131c` |
| HEAD | `d1ab8e1a33daf4ee490f9d4df0c57ceb8591131c` |
| origin/main | `d1ab8e1a33daf4ee490f9d4df0c57ceb8591131c` |
| Working tree | CLEAN |
| P3e status | CERTIFIED AND PUBLISHED |

---

## 3. Repository Integrity

No application code, tests, or schema were modified during this reconciliation. Only programme documentation was updated.

---

## 4. Original P0–P8 Roadmap

| ID | Canonical Name | Objective |
|----|----------------|-----------|
| P0 | Canonical Baseline & Product Surface Inventory | Inventory current product, map customer journey, define programme |
| P1 | Google AI Studio / Production UX Convergence | Visual comparison of AI Studio vs production UI |
| P2 | Connector Product Specification | Complete spec for EVOSIA Connector |
| P3 | Windows Connector Packaging | Implement Windows installer/package |
| P4 | Secure User-Friendly Computer Pairing | Replace terminal bootstrap token with user-friendly pairing |
| P5 | Native Project-Folder Authorization | Replace CLI project registration with folder picker + authorization |
| P6 | End-to-End Product Workflow | Connect all components: install→pair→authorize→review→results |
| P7 | Fresh-PC Non-Technical Usability Validation | Validate non-technical person can use EVOSIA without assistance |
| P8 | Product Certification | Formally certify EVOSIA as product ready for non-technical use |

---

## 5. P3a–P3e Expansion History

P3 was decomposed into sub-milestones during implementation:

| Sub-Milestone | Name | Status |
|---------------|------|--------|
| P3a | PyInstaller Packaging Foundation | COMPLETE / CERTIFIED / PUBLISHED |
| P3b | Inno Setup Installer Foundation | COMPLETE / CERTIFIED / PUBLISHED |
| P3c | Browser-Assisted Pairing | COMPLETE / CERTIFIED / PUBLISHED |
| P3d | Native Project Selection & Authorization | COMPLETE / CERTIFIED / PUBLISHED |
| P3e | Desktop/Tray Product Workflow | COMPLETE / CERTIFIED / PUBLISHED |

P3c implemented original P4 requirements. P3d implemented original P5 requirements. P3e implemented original P6 requirements.

---

## 6. Capability Inventory

### Implemented + Certified

- Browser-assisted pairing (P3c)
- Native folder picker (P3d)
- Browser project authorization (P3d)
- Desktop/tray application (P3e)
- Connector state machine (P3e)
- Explicit Review Project action (P3e)
- PROJECT_SCAN lifecycle polling (P3e)
- Diagnostics (P3e)
- 78 aggregate P3c+P3d+P3e tests passing
- Zero regressions
- Authority invariants preserved

### Implemented + Not Windows-Validated

- PyInstaller frozen build
- Inno Setup installer
- Console-free launch
- tkinter folder picker on Windows
- pystray tray icon on Windows
- Start Menu integration

### Deferred / Not Implemented

- Remove Project UX in tray
- Disconnect Computer UX in tray
- Single-instance guard
- Autostart configuration
- OS credential store (Credential Manager)
- Automatic updater
- Installer signing
- Code signing
- Customer-facing error messages
- Recovery UX improvements

---

## 7. Normal Customer Journey

| Step | Status |
|------|--------|
| Download | SPECIFIED |
| Install | IMPLEMENTED + NOT WINDOWS-VALIDATED |
| Launch | IMPLEMENTED + NOT WINDOWS-VALIDATED |
| Pair | IMPLEMENTED + CERTIFIED |
| Add Project | IMPLEMENTED + CERTIFIED |
| Authorize | IMPLEMENTED + CERTIFIED |
| Review | IMPLEMENTED + CERTIFIED |
| View Result | IMPLEMENTED |
| Close | IMPLEMENTED |
| Relaunch | IMPLEMENTED |
| Remove Project | DEFERRED |
| Disconnect Computer | DEFERRED |
| Update | DEFERRED |
| Uninstall | IMPLEMENTED + NOT WINDOWS-VALIDATED |

Terminal required in intended customer journey: **NO**

---

## 8. Windows Validation Debt

20 items require real Windows execution evidence:

PyInstaller build, Inno Setup build, clean installation, no-admin installation, Start Menu launch, console-free launch, tray icon/runtime, tkinter folder picker, browser pairing, browser project authorization, project persistence, PROJECT_SCAN, review polling, offline/recovery, junction/reparse containment, Windows Defender, SmartScreen, uninstall, reinstall, multiple launches.

---

## 9. Release-Blocking Work

| Blocker | Reason |
|---------|--------|
| Real Windows core-flow validation | Cannot certify without evidence |
| Installer signing strategy | Required for public distribution |
| Production versioned schema rollout | Required before deployment |

---

## 10. Important Pre-Beta Work

| Item | Classification |
|------|---------------|
| Single-instance guard | Evidence-driven (WV1 may determine if blocking) |
| Remove Project UX | Evidence-driven |
| Disconnect Computer UX | Evidence-driven |
| Autostart | Evidence-driven |
| Customer-facing error messages | Evidence-driven |

Prefer observe→document→remediate over speculative implementation.

---

## 11. Post-Beta / Future Items

- Windows Credential Manager migration
- Automatic updater
- Network-drive support
- Removable-drive support
- Diagnostics export/support bundle
- Broader AI Studio UX convergence
- macOS packaging
- Linux packaging
- Organization/multi-device features

---

## 12. Production Schema Readiness

**Tables requiring versioned migration:**
- `pairing_requests`
- `project_authorization_requests`

**Current mechanism:** SQLAlchemy `create_all()`

**Classification:** NEEDS VERSIONED MIGRATION BEFORE PRODUCTION DEPLOYMENT

**Deployment blocker:** YES

**WV1 execution blocker:** NO (can validate locally without migration)

---

## 13. Security Debt

| Severity | Count | Items |
|----------|-------|-------|
| Critical | 0 | — |
| High | 0 | — |
| Medium | 2 | Junction/reparse behavior, installer signing |
| Low | 4 | OS credential store, system folder selection, single-instance, diagnostics export |

---

## 14. Human Validation Debt

| Item | Status |
|------|--------|
| M8 participants | 1 of 5–8 completed (remaining deferred by programme-owner decision) |
| M9 authority comprehension | BLOCKED on M8 |
| P7 usability validation | NOT STARTED |

---

## 15. P3f Decision

**P3f WILL NOT BE CREATED.**

Reason: P3a–P3e already substantially implement the engineering capabilities originally assigned across P3/P4/P5/P6. Remaining work is primarily validation, evidence-backed remediation, human usability validation, and release engineering — not speculative feature development.

---

## 16. P4 Reconciliation

**Canonical:** P4 — Secure User-Friendly Computer Pairing
**Status:** SATISFIED

Satisfied by:
- P3c browser-assisted pairing (backend + Connector logic)
- P3e desktop/tray integration (Connect action)

All P4 acceptance gates met:
- Non-technical user can pair without terminal
- Device appears in Cloud UI after pairing
- Connection status reflected in tray
- Re-pairing after revocation works

Do NOT rename P4. Do NOT reuse P4 for Windows validation.

---

## 17. P5 Reconciliation

**Canonical:** P5 — Native Project-Folder Authorization
**Status:** SATISFIED

Satisfied by:
- P3d native project authorization (folder picker + browser auth)
- P3e desktop/tray integration (Add Project action)

All P5 acceptance gates met:
- Non-technical user can authorize project without CLI
- Authorization tokens flow securely
- "Review only" explanation displayed
- Project appears in Computers UI

Minor project-list-management UX in tray may remain as future remediation. Does not reopen canonical P5 authority contract.

---

## 18. P6 Reconciliation

**Canonical:** P6 — End-to-End Product Workflow
**Status:** SUBSTANTIALLY SATISFIED

Implemented:
- Launch → Pair → Add Project → Authorize → Explicit Review → Review Lifecycle → Cloud Handoff

Outstanding:
- Real Windows execution evidence required
- Customer-facing recovery/error UX where evidence shows need

Do not mark P6 fully satisfied until Windows evidence supports that conclusion.

---

## 19. P7 Status

**Canonical:** P7 — Fresh-PC Non-Technical Usability Validation
**Status:** NOT STARTED

P7 requires WV1 exit evidence first. P7 remains the human usability-validation milestone.

---

## 20. P8 Status

**Canonical:** P8 — Product Certification
**Status:** NOT STARTED

P8 remains downstream of: Windows validation, P7, required human evidence, release blockers, authority verification.

---

## 21. Reconciled Roadmap

```
P3e — CERTIFIED AND PUBLISHED
    ↓
WV1 — Windows Validation & Beta Readiness
    ↓
P7 — Fresh-PC Non-Technical Usability Validation
    ↓
Controlled Beta
    ↓
P8 — Product Certification
```

P4 = SATISFIED (through P3c/P3e)
P5 = SATISFIED (through P3d/P3e)
P6 = SUBSTANTIALLY SATISFIED (through P3e)
P3f = NOT REQUIRED

---

## 22. WV1 Definition

| Field | Value |
|-------|-------|
| **ID/Name** | WV1 — Windows Validation & Beta Readiness |
| **Classification** | VALIDATION / REMEDIATION |
| **Mission** | Validate the certified EVOSIA Connector product workflow on a real Windows environment, remediate only evidence-backed failures, and establish readiness for P7 non-technical usability validation |
| **Starting Baseline** | `d1ab8e1a33daf4ee490f9d4df0c57ceb8591131c` |
| **Scope** | Windows build, installer test, tray validation, lifecycle gaps, signing strategy, error messages |
| **Non-Goals** | New features, backend changes, frontend redesign, production deployment, human validation |
| **Dependencies** | Windows machine (physical or clean VM) |
| **Code Changes Expected** | MAYBE (remediation findings only) |
| **Production Deployment Allowed** | NO |
| **Exit Criteria** | Core flow validated on Windows, all release-blocking findings resolved, ready for P7 |

WV1 does not supersede P4/P5/P6. It is an evidence bridge between P3e/reconciled P6 and P7.

---

## 23. Authority Boundary

| Invariant | Value |
|-----------|-------|
| DeviceProject.authority | REVIEW_ONLY |
| ALLOWED_OPERATION_TYPES | `frozenset({"PROJECT_SCAN"})` |
| Prepare | NOT AUTHORIZED |
| Execute | NOT AUTHORIZED |
| Merge | NOT AUTHORIZED |
| Deploy | NOT AUTHORIZED |
| Arbitrary shell | NOT AUTHORIZED |
| Autonomous project selection | NOT AUTHORIZED |
| Autonomous project authorization | NOT AUTHORIZED |
| Autonomous review | NOT AUTHORIZED |
| Automatic review | NOT AUTHORIZED |
| Authority manufacture | NOT AUTHORIZED |

WV1 validation/remediation must preserve these invariants.

---

## 24. Programme Governance Decision

This reconciliation is published under programme-owner authorization. It:

- Preserves all canonical milestone identities (P0–P8)
- Records P3f as NOT REQUIRED
- Reconciles P4/P5/P6 as SATISFIED/SUBSTANTIALLY SATISFIED through P3c–P3e
- Defines WV1 as the next milestone
- Preserves all authority invariants
- Does not authorize WV1 implementation (requires separate approval)

---

## 25. Final Disposition

**POST-P3e ROADMAP RECONCILIATION: PUBLISHED**

No application code was changed. No tests were changed. No schema was changed. No deployment was performed. No production mutation occurred.

---

*This document records the Post-P3e programme reconciliation. It is governance documentation, not implementation authority.*
