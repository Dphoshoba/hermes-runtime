# EVOSIA Productization Programme — P0–P8

**Date:** 2026-08-30
**Certified Baseline:** `313aaed12985a23aca494ecd41093c1e52b36612`
**P0 Status:** COMPLETE / CERTIFIED / PUBLISHED (`39e015937c8ec5f78114bcbd00a6198bb52876e4`)
**P1 Status:** COMPLETE
**P2 Status:** COMPLETE
**P3a Status:** COMPLETE
**P3b Status:** COMPLETE
**Certified Dependency:** Local Agent Programme LA0–LA6 COMPLETE
**Purpose:** Transform the technically certified EVOSIA platform into a product a non-technical person can install, connect, understand, and use on their own computer without developer assistance.

---

## Master Goal

The eventual customer must NOT need:

- PowerShell
- terminal commands
- Python
- pip
- virtual environments
- Git
- repository cloning
- environment variables
- JWT knowledge
- API knowledge
- Railway knowledge
- database knowledge
- manual credential-file handling
- registration tokens pasted into terminals
- project-authorization tokens pasted into terminals

The product should hide those implementation details behind a safe, understandable user experience.

---

## Certified Input — DO NOT RE-PROVE

LA0–LA6 is COMPLETE and production validated. The following capabilities are certified and must be treated as authoritative:

- LA0: Outbound HTTPS architecture, no inbound ports, control/work plane separation
- LA1: Device identity, bootstrap tokens, device credentials, heartbeat, revocation
- LA2: `evosia_agent` runtime, local credential storage, retry/backoff, persistent heartbeat
- LA3: Explicit human project authorization, canonical path fingerprint, containment, symlink escape protection, sensitive-file classification
- LA4: Governed PROJECT_SCAN, bounded read-only scanner, `shell=False`, hardcoded bounded git metadata commands, no generic subprocess runner, `LIVE_EVOSIA_EVIDENCE`
- LA5: Computers UI, device state, project authorization, Review project, review history, accessibility, truncation disclosure
- LA6: Production validation on a real second Windows computer, full lifecycle visually verified, source-tree immutability verified, duplicate active-job backend guard, synchronous frontend double-click protection

Do NOT repeat these engineering validations during P0.

---

## Authority Freeze

| Constraint | Value |
|------------|-------|
| DeviceProject authority | `REVIEW_ONLY` |
| ALLOWED_OPERATION_TYPES | `frozenset({"PROJECT_SCAN"})` |
| Execution authority | NOT GRANTED |
| Merge authority | NOT GRANTED |
| Deployment authority | NOT GRANTED |
| Autonomous job creation | NOT GRANTED |

Packaging existing capability does NOT constitute authority expansion.

If a future requirement appears to need additional authority:

1. DOCUMENT IT.
2. DO NOT IMPLEMENT IT.

Authority expansion requires a separate future programme.

---

## Milestone Definitions

### P0 — Canonical Baseline & Product Surface Inventory

**Status:** COMPLETE / CERTIFIED / PUBLISHED
**Certification Commit:** `39e015937c8ec5f78114bcbd00a6198bb52876e4`

**Objective:** Answer "What exactly do we have today, what does a user currently experience, and what must be productized?"

**Inputs:** LA0–LA6 certified implementation, all existing source, documentation, and production evidence.

**In Scope:**
- Inventory current EVOSIA product surface (all user-facing routes, backend APIs)
- Map actual current Windows customer journey (every human action, step-by-step)
- Inventory reusable certified contracts (device, project, work, evidence)
- Inventory local agent platform assumptions (Windows, macOS, Linux)
- Document target customer experience (16-step ideal journey)
- Google AI Studio concept inventory and comparison
- Productization gap identification
- Define P0–P8 programme structure

**Out of Scope:**
- Redesign
- Implementation
- Refactoring
- Installer development
- API modification
- UI modification

**Acceptance Gates:**
- All 12 sections of P0 evidence document complete
- Current vs target clearly separated throughout
- Authority boundary documented and preserved
- No claims stronger than existing evidence

**Evidence Required:**
- `docs/productization/P0_PRODUCT_SURFACE_INVENTORY.md`
- `docs/productization/EVOSIA_PRODUCTIZATION_PROGRAMME.md`

**Authority Invariants:** No authority expansion. Documentation only.

**Stop Condition:** All inventory sections complete, all contracts classified, all gaps identified, programme P0–P8 defined.

---

### P1 — Google AI Studio / Production UX Convergence

**Status:** COMPLETE
**Evidence:** `docs/productization/P1_UX_CONVERGENCE.md`

**Objective:** Visually compare the Google AI Studio generated application against the current production UI and the prompt specification. Identify convergence and divergence points.

**Inputs:**
- `docs/google-ai-studio/EVOSIA_GOOGLE_AI_STUDIO_BUILD_PROMPT.md`
- Current production UI source
- P0 evidence document

**In Scope:**
- Visual examination of the actual Google AI Studio generated app
- Concept-by-concept comparison against the build prompt
- Concept-by-concept comparison against production UI
- Identification of UX patterns to adopt, adapt, or reject
- Convergence/divergence report

**Out of Scope:**
- Implementation changes
- Backend modifications
- Agent modifications

**Acceptance Gates:**
- Every major concept classified: PRESENT / PARTIALLY PRESENT / ABSENT / REQUIRES ADOPTION
- Visual comparison evidence recorded
- No backend authority changes

**Evidence Required:**
- `docs/productization/P1_UX_CONVERGENCE.md`

**Authority Invariants:** No authority expansion. Visual/design analysis only.

**Stop Condition:** Complete concept comparison with visual evidence, adoption recommendations documented.

---

### P2 — EVOSIA Connector Product Specification

**Status:** COMPLETE
**Evidence:** `docs/productization/P2_CONNECTOR_PRODUCT_SPECIFICATION.md`

**Objective:** Define the complete product specification for the "EVOSIA Connector" — the packaged local agent that a non-technical user can install.

**Inputs:**
- P0 platform assumptions and gap inventory
- P1 UX convergence findings
- LA0–LA6 certified architecture

**In Scope:**
- Connector concept definition (what it is, what it does, what it is NOT)
- Installation experience specification
- Account pairing flow specification
- Project folder selection specification
- Background operation specification
- Update mechanism specification
- Uninstall/revoke specification
- Error handling and recovery specification
- Cross-platform strategy (Windows first, macOS/Linux later)

**Out of Scope:**
- Implementation
- Technology selection (deferred to P3)
- Code writing

**Acceptance Gates:**
- Complete specification document
- Every LA0–LA6 capability mapped to product experience
- Every P0 gap addressed in specification
- Authority invariants preserved in specification

**Evidence Required:**
- `docs/productization/P2_CONNECTOR_SPECIFICATION.md`

**Authority Invariants:** Packaging existing capability only. No authority expansion.

**Stop Condition:** Specification complete, all gaps addressed, ready for implementation planning.

---

### P3 — Windows Connector Packaging

**Status:** P3a COMPLETE | P3b COMPLETE | P3c COMPLETE | P3d COMPLETE

**Objective:** Implement the Windows installer/package for the EVOSIA Connector.

**Inputs:**
- P2 Connector Specification
- Current `evosia_agent` Python implementation

**In Scope:**
- Windows installer/packaging technology selection and implementation
- Python runtime bundling (or alternative)
- Agent code packaging
- Installation wizard
- Start-menu / system-tray integration
- Automatic startup configuration
- File permission handling for Windows

**Out of Scope:**
- macOS packaging
- Linux packaging
- Account pairing UI (deferred to P4/P3c)
- Project folder selection UI (deferred to P5)

**P3a — PyInstaller Packaging:**
- PyInstaller `.spec` frozen application build
- Hidden imports resolved
- Source tree excluded from package
- Test files excluded from package
- Secrets not embedded
- Evidence: `docs/productization/P3A_PYINSTALLER_PACKAGING.md`

**P3b — Inno Setup Installer:**
- Inno Setup `.iss` Windows installer
- Per-user install (no admin required)
- Python runtime bundled
- Desktop shortcut (optional, default off)
- Uninstall support
- Registry entries
- Evidence: `docs/productization/P3B_INNO_SETUP_INSTALLER.md`

**P3c — Browser-Assisted Pairing Foundation:**
- PairingRequest database model
- Pairing backend APIs (create, status, approve, deny, consume)
- Connector pairing logic (browser launch, polling, credential exchange)
- Pairing tests (20 tests, all pass)
- Evidence: `docs/productization/P3C_BROWSER_ASSISTED_PAIRING.md`

**P3d — Native Project Selection & Authorization:**
- ProjectAuthorizationRequest database model
- Project authorization backend APIs (create, status, approve, deny, consume)
- Connector project authorization logic (folder validation, browser launch, polling)
- Native folder picker integration (tkinter)
- Browser approval page for project authorization
- Project authorization tests (19 tests, all pass)
- Evidence: `docs/productization/P3D_NATIVE_PROJECT_AUTHORIZATION.md`

**Acceptance Gates:**
- P3a: PyInstaller builds frozen app without errors
- P3b: Inno Setup produces valid Windows installer
- P3c: Browser-assisted pairing protocol implemented
- P3c: No manual bootstrap token copy/paste in customer flow
- P3d: Native project folder selection implemented
- P3d: Manual project auth token copy/paste removed from customer flow

**Authority Invariants:** Packaging existing capability only. No authority expansion.

**Stop Condition:** P3d complete, ready for P5/P6 project authorization and end-to-end workflow.

---

### P4 — Secure User-Friendly Computer Pairing

**Objective:** Replace the current terminal-based bootstrap token exchange with a user-friendly pairing flow.

**Inputs:**
- P2 Connector Specification
- LA1 device trust domain (certified)
- Current bootstrap token protocol

**In Scope:**
- Pairing code display in EVOSIA Cloud UI
- Pairing code entry in Connector
- Secure device-to-account binding
- Pairing confirmation in Cloud UI
- Connection status display
- Re-pairing after revocation

**Out of Scope:**
- Project folder selection (deferred to P5)
- Scan job execution

**Acceptance Gates:**
- Non-technical user can pair a computer without terminal
- Device appears in Cloud UI after pairing
- Connection status accurately reflects agent state
- Revocation and re-pairing work

**Evidence Required:**
- Pairing flow test evidence
- Device lifecycle evidence

**Authority Invariants:** LA1 trust model preserved. Bootstrap token protocol wrapped, not replaced.

**Stop Condition:** Pairing works end-to-end for non-technical user.

---

### P5 — Native Project-Folder Authorization

**Objective:** Replace the command-line project registration with a native folder picker and authorization flow.

**Inputs:**
- P2 Connector Specification
- LA3 explicit project authorization (certified)
- Current project authorization token protocol

**In Scope:**
- Native OS folder picker integration
- Project authorization in Cloud UI
- Authorization token delivery to Connector
- Project registration without CLI
- Authorization explanation ("Review only" disclosure)
- Project list management

**Out of Scope:**
- Scan execution (uses existing LA4)
- Project removal from Cloud UI

**Acceptance Gates:**
- Non-technical user can authorize a project folder without CLI
- Authorization tokens flow securely from Cloud to Connector
- "Review only" explanation is clear and prominent
- Project appears in Computers UI after authorization

**Evidence Required:**
- Folder selection flow test evidence
- Authorization flow test evidence

**Authority Invariants:** LA3 trust model preserved. Authorization tokens wrapped, not replaced. REVIEW_ONLY enforced.

**Stop Condition:** Project authorization works end-to-end for non-technical user.

---

### P6 — End-to-End Product Workflow

**Objective:** Connect all productized components into a complete, non-technical user journey from installation through first review.

**Inputs:**
- P3 Windows Connector
- P4 Computer Pairing
- P5 Project Authorization
- LA4 governed PROJECT_SCAN (certified)
- LA5 Computers UI (certified)

**In Scope:**
- End-to-end flow integration
- Review project button in productized UI
- Review lifecycle display (queued → in progress → complete → unchanged)
- Review results/findings display
- Review history
- Truncation disclosure
- Error handling throughout

**Out of Scope:**
- Multi-platform packaging
- Multi-user validation
- Performance optimization

**Acceptance Gates:**
- Complete user journey works: install → pair → authorize → review → results
- All LA6 lifecycle states visible in UI
- Source-tree immutability maintained
- All authority boundaries preserved

**Evidence Required:**
- End-to-end test evidence
- Full lifecycle evidence

**Authority Invariants:** All LA0–LA6 authority boundaries preserved. No authority expansion.

**Stop Condition:** Complete product workflow verified on Windows.

---

### P7 — Fresh-PC Non-Technical Usability Validation

**Objective:** Validate that a non-technical person can use EVOSIA on a fresh computer without assistance.

**Inputs:**
- P6 end-to-end workflow
- M8/M9 usability protocols (existing)

**In Scope:**
- Fresh Windows PC test (no developer tools installed)
- Non-technical participant recruitment (target: 5–8)
- Task completion observation
- Authority comprehension testing
- Friction documentation
- Remediation of blocking usability issues

**Out of Scope:**
- Multi-platform testing
- Performance testing
- Load testing

**Acceptance Gates:**
- Minimum 5 non-technical participants complete the journey
- 100% authority comprehension (M8/M9 gate)
- No blocking usability friction
- All participant evidence recorded

**Evidence Required:**
- Participant test records
- Authority comprehension results
- Friction/remediation log

**Authority Invariants:** No authority expansion during remediation. Usability fixes only.

**Stop Condition:** M8/M9 gate satisfied with non-technical participants.

---

### P8 — Product Certification

**Objective:** Formally certify EVOSIA as a product ready for non-technical use.

**Inputs:**
- P7 usability validation
- All P0–P7 evidence
- LA0–LA6 certification

**In Scope:**
- Complete evidence review
- Programme reconciliation
- Final certification document
- Production baseline record
- Authority invariant final verification

**Out of Scope:**
- New features
- New engineering work

**Acceptance Gates:**
- All P0–P7 milestones PASS
- M8/M9 authority comprehension satisfied
- All authority invariants preserved
- No execution authority granted
- Production baseline recorded

**Evidence Required:**
- `docs/productization/P8_PRODUCT_CERTIFICATION.md`
- Updated `validation/PROGRAMME_STATUS_RECONCILIATION.md`

**Authority Invariants:** Final verification of all authority boundaries.

**Stop Condition:** Product certification issued.

---

## Authority Invariants (All Milestones)

| Invariant | Status |
|-----------|--------|
| DeviceProject authority | REVIEW_ONLY |
| ALLOWED_OPERATION_TYPES | `frozenset({"PROJECT_SCAN"})` |
| Execution authority | NOT GRANTED |
| Merge authority | NOT GRANTED |
| Deployment authority | NOT GRANTED |
| Autonomous job creation | NOT GRANTED |
| Arbitrary shell capability | NOT GRANTED |
| Filesystem scope expansion | NOT GRANTED |

Packaging existing capability does NOT constitute authority expansion.

---

## Relationship to Other Programmes

| Programme | Relationship |
|-----------|-------------|
| LA0–LA6 (Local Agent) | Certified dependency. COMPLETE. Do not reopen. |
| M0–M13 (Product Acceptance) | Independent track. P7/P8 may satisfy M8/M9/M13 human-validation dependencies. |
| Track B (Hosted Beta) | Independent track. External operator actions remain separate. |
| Track C (Evidence Cycles) | Completed historical evidence. No active cycles. |

---

## Change Boundary

P0 is documentation only. P1 is analysis only. P2 is specification only. P3–P8 may include implementation but ONLY within the scope defined above.

No milestone authorizes:
- Arbitrary command execution
- Autonomous coding
- Project file editing
- Merge
- Deployment
- Preparation authority
- Autonomous PROJECT_SCAN creation

---

*This programme document is the governing definition for EVOSIA Productization P0–P8. Do not amend without explicit programme-owner authorization.*
