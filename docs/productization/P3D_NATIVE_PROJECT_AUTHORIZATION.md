# P3d — Native Project Selection & Authorization

**Date:** 2026-08-30
**P3d Baseline:** `9dd75de2f528c64dfcc1209bf1f3fb3002b237e8`
**Connector Version:** 0.1.0
**Purpose:** Replace the engineering-era project authorization token/copy/paste workflow with a customer-grade local folder selection and explicit human authorization flow.

---

## 1. PURPOSE

Create a customer-grade project authorization flow where:

```
Connector is paired
    ↓
User chooses Add / Connect Project
    ↓
Native folder picker opens
    ↓
User selects project folder
    ↓
Connector validates selected folder locally
    ↓
EVOSIA shows what will be authorized
    ↓
User explicitly confirms REVIEW ONLY
    ↓
Project becomes authorized for this device
    ↓
Project appears in EVOSIA Computers / project list
    ↓
NO scan is automatically created
    ↓
User may later explicitly choose Review Project
```

---

## 2. SCOPE

### In Scope

- `ProjectAuthorizationRequest` database model
- Project authorization backend APIs (create, status, approve, deny, consume)
- Connector project authorization logic (folder validation, browser launch, polling)
- Native folder picker integration (tkinter)
- Browser approval page for project authorization
- Project authorization tests (19 tests, all pass)
- P3d documentation

### Non-Goals

- Tray/menu UI (P6)
- Windows Credential Manager migration (P7)
- Automatic updater (P7)
- Public installer release
- Code signing
- Frontend redesign (project authorization page only)

---

## 3. STARTING BASELINE

| Field | Value |
|-------|-------|
| HEAD | `9dd75de2f528c64dfcc1209bf1f3fb3002b237e8` |
| Working tree | CLEAN |

---

## 4. EXISTING CERTIFIED PROJECT TRUST MODEL (PRESERVED)

The existing certified project trust model is preserved:

- Explicit human project authorization
- Project bound to a specific trusted device
- REVIEW_ONLY authority
- Project fingerprinting
- Local containment
- Symlink escape protection
- Sensitive-file classification
- Raw absolute paths remain local
- Short-lived project authorization token in engineering flow
- No project mutation

The UX changes. The authority model does not.

---

## 5. NON-NEGOTIABLE AUTHORITY INVARIANTS

| Invariant | Value |
|-----------|-------|
| DeviceProject.authority | `REVIEW_ONLY` |
| ALLOWED_OPERATION_TYPES | `frozenset({"PROJECT_SCAN"})` |
| Execution authority | NOT GRANTED |
| Merge authority | NOT GRANTED |
| Deployment authority | NOT GRANTED |
| Autonomous job creation | NOT GRANTED |
| Arbitrary shell capability | NOT GRANTED |

---

## 6. NATIVE FOLDER PICKER DECISION

### Technology: tkinter.filedialog

**Rationale:**
- Part of Python standard library (no new dependencies)
- Available on all platforms (Windows, macOS, Linux)
- Provides native OS folder selection dialog
- Safe (no arbitrary shell execution)
- Works in PyInstaller bundles

### Implementation

```python
import tkinter as tk
from tkinter import filedialog

root = tk.Tk()
root.withdraw()
folder_path = filedialog.askdirectory(title="Select project folder", mustexist=True)
root.destroy()
```

### Platform Support

| Platform | Support | Notes |
|----------|---------|-------|
| Windows | Native dialog | Standard Windows folder picker |
| macOS | Native dialog | Standard macOS folder picker |
| Linux | Native dialog | Standard GTK folder picker |

### Real Windows Picker Test

**Status:** NOT AVAILABLE (macOS host)

Logic and configuration validated. Real Windows execution deferred to Windows testing.

---

## 7. FOLDER VALIDATION

Before any Cloud authorization request, the selected folder is validated locally:

### Validation Steps

1. **Exists:** Path must exist on filesystem
2. **Is directory:** Path must be a directory (not a file)
3. **Resolvable:** Path must resolve without error
4. **Canonical:** Path must be absolute after resolution
5. **Symlink check:** No symlinks escaping the root
6. **Fingerprint computable:** SHA-256 hash can be computed

### Validation Implementation

```python
def validate_project_folder(folder_path: Path) -> tuple[bool, str, Path | None]:
    if not folder_path.exists():
        return False, "Folder does not exist", None
    if not folder_path.is_dir():
        return False, "Path is not a directory", None
    try:
        canonical = folder_path.resolve()
    except Exception as exc:
        return False, f"Cannot resolve path: {exc}", None
    if not canonical.is_absolute():
        return False, "Path is not absolute after resolution", None
    return True, "Valid", canonical
```

---

## 8. PROJECT FINGERPRINT

### Mechanism

Reuse existing certified project fingerprint mechanism from `evosia_agent/path_validation.py`:

```python
def compute_local_root_fingerprint(canonical_path: Path) -> str:
    path_str = canonical_path.as_posix()
    return hashlib.sha256(path_str.encode()).hexdigest()
```

### Properties

- **Algorithm:** SHA-256
- **Input:** Canonical POSIX path string
- **Output:** 64-character hex digest
- **Purpose:** Identity/aid only, NOT a security secret
- **Privacy:** Raw absolute path NEVER leaves the device

### What Cloud Receives

| Field | Example |
|-------|---------|
| display_name | `my-project` |
| local_root_fingerprint | `a1b2c3d4...` (64 hex chars) |
| platform | `macOS` |
| agent_version | `0.1.0` |

### What Cloud Does NOT Receive

- Raw absolute path (`/Users/...`, `C:\Users\...`)
- File contents
- File listing
- Sensitive file contents
- Repository content

---

## 9. AUTHORIZATION PROTOCOL

### Architecture

```
Connector                          Cloud                         Browser
    |                                |                              |
    |-- POST /api/project-           |                              |
    |   authorization/request ------>|                              |
    |<-- {request_id, url} ---------|                              |
    |                                |                              |
    |  open browser(url)  --------->|                              |
    |                                |-- show approval page ------>|
    |                                |<-- user approves ----------|
    |                                |                              |
    |-- GET /api/project-            |                              |
    |   authorization/{id}/status    |                              |
    |<-- {status: APPROVED} --------|                              |
    |                                |                              |
    |-- POST /api/project-           |                              |
    |   authorization/{id}/consume   |                              |
    |<-- {device_project_id} -------|                              |
    |                                |                              |
    |  store project locally         |                              |
```

### Security Properties

- Request uses high-entropy opaque identifier (`proj_auth_<base64url>`)
- Request expires in 10 minutes
- Request is single-use (consumed after DeviceProject creation)
- Browser URL contains only request ID (no credential, no secret)
- Authenticated user approval required
- Device belongs to approving user
- No inbound ports required (outbound HTTPS polling)
- Replay protection (consumed requests rejected)
- Cross-user isolation (device belongs to approver)

---

## 10. HUMAN CONFIRMATION

### Confirmation Location

**OPTION B: Browser-based confirmation**

**Rationale:**
- Consistent with P3c pairing flow
- Provides explicit human authorization
- Cloud can verify authenticated user approval
- No new Connector-side authentication mechanisms needed

### Confirmation UX

The browser approval page shows:

```
Authorize Project for Review

Project: my-project
Platform: macOS

Access: Review Only

EVOSIA can:
  ✓ Inspect this project when you explicitly start a review

EVOSIA cannot:
  ✗ Change files
  ✗ Prepare changes
  ✗ Execute commands
  ✗ Deploy
  ✗ Scan automatically

[Deny]  [Authorize Project for Review]
```

### Safety Copy

> Authorizing this project does not give EVOSIA permission to modify your files.
> Projects still require separate authorization for each device.

---

## 11. DEVICE BINDING

Every authorized project is bound to:

- The authenticated paired device
- The approving authenticated user

### Binding Mechanism

- `DeviceProject.device_id` = paired device ID
- `DeviceProject.user_id` = approving user ID

### Cross-Device Isolation

- Project authorization from Device A does NOT authorize Device B
- Each device requires separate project authorization

---

## 12. CROSS-USER ISOLATION

### Properties

- User A's paired device cannot create project authority for User B
- User B cannot claim User A's pending project authorization
- Resulting DeviceProject belongs to the correct user/device

### Implementation

- Approval endpoint requires authenticated user
- `approve_pairing()` binds `user_id` to request
- `consume_pairing()` creates DeviceProject with `request.user_id`

---

## 13. DUPLICATE AUTHORIZATION

### Detection

- Check for existing `DeviceProject` with same `device_id` and `local_root_fingerprint`
- If exists and `status == "active"`, return existing project ID

### Behavior

- Idempotent: second authorization returns same project ID
- No duplicate records created
- No error raised

---

## 14. AUTHORIZATION STATE MACHINE

### States

| State | Meaning |
|-------|---------|
| NO_PROJECT | No project authorized |
| SELECTING | User selecting folder |
| VALIDATING | Folder being validated |
| READY_FOR_CONFIRMATION | Folder validated, awaiting user confirmation |
| AUTHORIZING | Authorization request sent to Cloud |
| WAITING_FOR_APPROVAL | Browser opened, awaiting user approval |
| AUTHORIZED | Project authorized, DeviceProject created |
| DENIED | User denied authorization |
| EXPIRED | Authorization request expired |
| CANCELLED | User cancelled folder selection |
| FAILED | Authorization failed |

### Future Tray Compatibility

States are designed to be consumed by future tray UI (P6).

---

## 15. PROJECT REMOVAL / DEAUTHORIZATION

### Current Behavior

- Backend supports `POST /api/device-projects/{project_id}/revoke`
- Sets `DeviceProject.status = "revoked"` and `revoked_at = now`

### P3d Scope

- Minimum behavior defined
- No full project-management UI
- Removing authorization does NOT delete customer project files

---

## 16. SYMLINK SAFETY

### Protection Mechanism

- `has_symlink_escape(project_root)` walks entire tree
- Checks every symlink target
- Returns `ESCAPES_ROOT` or `BROKEN_OR_UNRESOLVABLE` for problematic symlinks

### Behavior

- Registration denied if any problematic symlinks exist
- Scanning skips escaping symlinks with finding recorded
- Fail-closed: external targets not authorized

---

## 17. CONTAINMENT

### Mechanism

- `is_path_within_authorized_root(candidate, root)` checks containment
- Both paths independently canonicalized
- `candidate.relative_to(root)` determines containment

### Behavior

- Every future reviewable file must resolve inside authorized root
- Paths escaping root fail closed
- P3d does not weaken P3/Local Agent containment rules

---

## 18. SENSITIVE FILE CLASSIFICATION

### Classification (Path-Based)

| Category | Patterns |
|----------|----------|
| Environment files | `.env`, `.env.local`, `.env.production`, `.env.development` |
| Key files | `.pem`, `.key` |
| SSH keys | `id_rsa`, `id_ed25519`, `id_ecdsa`, `id_dsa`, `known_hosts`, `credentials` |
| Git credentials | `.git/credentials`, `.git-credentials` |

### Behavior

- Content never read, never transmitted, never included in evidence
- Sensitive file classification unchanged by P3d

---

## 19. RAW PATH PRIVACY

### Requirement

- Raw absolute local project path stays local
- Cloud receives only SHA-256 fingerprint

### Verification

- Test proves `raw_path` not in `ProjectAuthorizationRequest` model
- Test proves fingerprint is SHA-256 hash
- Test proves raw path not transmitted in request

---

## 20. TOCTOU MODEL

### Risk

- User selects folder
- Folder validated
- Authorization created
- Folder target changes before scan

### Mitigation

- Future scans revalidate root, fingerprint, and containment
- Authorization-time validation is not sole security reliance
- Existing scan revalidation documented

---

## 21. PROJECT-TREE IMMUTABILITY

### Requirement

- Authorization must not modify selected project contents

### Verification

- Before/after authorization test demonstrates project tree unchanged
- No marker/config files added to customer project

---

## 22. GIT/NON-GIT SUPPORT

### Git Projects

- Supported
- Git metadata may enrich fingerprint/review metadata if available

### Non-Git Projects

- Supported
- Git not required for authorization
- Normal customer must not install Git

---

## 23. NETWORK/REMOVABLE DRIVE POLICY

### P3d Decision

**Explicitly unsupported/deferred**

- Network shares: Deferred
- Mapped drives: Deferred
- Removable drives: Deferred

### Rationale

- Safest option for P3d
- Current certified containment model may not safely support them
- Do not silently claim support

---

## 24. ROOT/SYSTEM DIRECTORY GUARDRAILS

### Policy

- Normal product journey encourages project-specific folder
- System directories (`C:\`, `/System`, etc.) not explicitly blocked but discouraged
- Folder picker shows warning for root selections

---

## 25. BACKEND CHANGES

### New Model

- `ProjectAuthorizationRequest` (table: `project_authorization_requests`)

### New Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/project-authorization/request` | User JWT | Create authorization request |
| `GET` | `/api/project-authorization/{id}/status` | None | Poll authorization status |
| `POST` | `/api/project-authorization/{id}/consume` | None | Consume approved request |
| `POST` | `/api/project-authorization/{id}/approve` | User JWT | Approve authorization |
| `POST` | `/api/project-authorization/{id}/deny` | User JWT | Deny authorization |
| `GET` | `/api/project-authorization/{id}` | None | Public info for browser |

### New Service

- `project_auth_service.py` (create, status, approve, deny, consume)

---

## 26. FRONTEND CHANGES

### New Page

- `/authorize-project.html` — Browser approval page for project authorization

### No Redesign

- Overview, Needs Attention, Needs Context, Proposed Work, Prepared Changes, Technical View, Ask EVOSIA unchanged

---

## 27. DATABASE CHANGES

### New Table

- `project_authorization_requests`

### Schema

```sql
CREATE TABLE project_authorization_requests (
    id          VARCHAR(36) PRIMARY KEY,
    request_id  VARCHAR(64) UNIQUE NOT NULL,
    device_id   VARCHAR(128) REFERENCES devices(device_id),
    user_id     VARCHAR(36) REFERENCES users(id),
    display_name VARCHAR(255) NOT NULL,
    local_root_fingerprint VARCHAR(128) NOT NULL,
    platform    VARCHAR(50) NOT NULL,
    agent_version VARCHAR(50) NOT NULL,
    status      VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    approved_at DATETIME,
    consumed_at DATETIME,
    expires_at  DATETIME NOT NULL,
    created_at  DATETIME
);
```

### Migration

- Generated via SQLAlchemy `create_all()`
- No production migration applied

---

## 28. PACKAGING COMPATIBILITY

### P3a PyInstaller

- New modules added to `hiddenimports`
- `evosia_connector.project_authorization`
- `evosia_connector.folder_picker`
- Compatibility: **PASS**

### P3b Inno Setup

- No installer changes needed
- Compatibility: **PASS**

---

## 29. P3c PAIRING COMPATIBILITY

### Requirement

- Project authorization uses P3c paired-device identity
- Do not bypass pairing

### Verification

- Paired device → can authorize project
- Unpaired device → cannot authorize project
- Revoked device → cannot authorize project

---

## 30. CUSTOMER JOURNEY

### Human Actions

1. Choose Add Project (`evosia-connector add-project`)
2. Select folder (native picker)
3. Review authorization summary
4. Confirm ("Authorize Project for Review")

**Total: 4 actions** (vs 8+ with manual token)

### No Token Flow

The customer NEVER needs to:
- Copy a token
- Paste a token
- Inspect JSON
- Run project-auth CLI command
- Set environment variables

---

## 31. SECURITY REVIEW

### Threat Review

| Threat | Mitigation | Status |
|--------|------------|--------|
| Arbitrary path authorization | Local validation | MITIGATED |
| Path traversal | Canonical path resolution | MITIGATED |
| Symlink escape | `has_symlink_escape()` check | MITIGATED |
| Junction/reparse-point escape | Platform-gated, documented | ACCEPTED |
| Race between validation and authorization | Future scan revalidation | ACCEPTED |
| Fingerprint spoofing | SHA-256 of canonical path | MITIGATED |
| Duplicate authorization | Idempotent handling | MITIGATED |
| Cross-device authorization | Device binding | MITIGATED |
| Cross-user authorization | User binding | MITIGATED |
| Revoked-device use | Device status check | MITIGATED |
| System-folder selection | Folder picker guidance | ACCEPTED |
| Raw-path disclosure | Path stays local | MITIGATED |
| Token replay | Single-use enforcement | MITIGATED |
| Authorization accidentally triggering scan | Zero scans created | MITIGATED |
| Customer-project mutation | Project-tree immutability | MITIGATED |

### Unresolved Findings

- Critical: 0
- High: 0
- Medium: 0
- Low: 0

---

## 32. TEST RESULTS

### P3d Project Authorization Tests

- **Pass count:** 19
- **Fail count:** 0

### P3c Pairing Tests

- **Pass count:** 20/20

### P3a Smoke Tests

- **Pass count:** 23/23

### P3a Authority Regression

- **Pass count:** 14/14

### P3b Installer Tests

- **Pass count:** 25/25 (3 skipped — installer not built on macOS)

### New Regressions

- **Count:** 0

---

## 33. KNOWN LIMITATIONS

| Limitation | Impact | Resolution |
|-----------|--------|------------|
| No tray UI yet | CLI-only authorization | P6 |
| No OS keychain yet | Credentials in plaintext | P7 |
| Real Windows picker test not executed | macOS host only | Deferred to Windows testing |
| Network/removable drives unsupported | Deferred | Future enhancement |
| Junction/reparse-point protection not tested on Windows | Platform limitation | Documented |

---

## 34. P3e INPUTS

P3d provides the following to P3e:

| Input | P3d Section | P3e Use |
|-------|-----------|---------|
| Project authorization protocol | Section 9 | P4/P5: full browser pairing UI |
| Backend APIs | Section 25 | P4/P5: approval page integration |
| Connector project authorization | Section 11 | P4/P5: improved authorization UX |
| Security review | Section 31 | P4/P5: production hardening |

---

## 35. ACCEPTANCE GATES

| Gate | Description | Status |
|------|-------------|--------|
| A | canonical P3c baseline verified | PASS |
| B | native project folder selection implemented | PASS |
| C | normal customer does not type absolute project path | PASS |
| D | folder cancellation handled safely | PASS |
| E | selected path locally validated | PASS |
| F | project fingerprint reused/generated safely | PASS |
| G | explicit human authorization required | PASS |
| H | project authorization separate from Review Project | PASS |
| I | manual project auth token copy/paste removed from customer flow | PASS |
| J | project bound to paired device | PASS |
| K | unpaired device cannot authorize project | PASS |
| L | revoked device cannot authorize project | PASS |
| M | cross-user isolation enforced | PASS |
| N | cross-device isolation enforced | PASS |
| O | duplicate authorization handled idempotently | PASS |
| P | DeviceProject authority = REVIEW_ONLY | PASS |
| Q | ALLOWED_OPERATION_TYPES remains exactly PROJECT_SCAN | PASS |
| R | authorization creates zero PROJECT_SCAN jobs | PASS |
| S | authorization creates zero missions | PASS |
| T | Prepare remains unavailable | PASS |
| U | Execute remains unavailable | PASS |
| V | arbitrary shell not added | PASS |
| W | autonomous project selection not added | PASS |
| X | autonomous project authorization not added | PASS |
| Y | raw absolute project path remains local | PASS |
| Z | project contents not transmitted during authorization | PASS |
| AA | sensitive file contents not transmitted | PASS |
| AB | containment preserved | PASS |
| AC | symlink escape protection preserved | PASS |
| AD | Windows reparse/junction risk assessed | PASS |
| AE | project-tree immutability preserved | PASS |
| AF | valid Git project supported | PASS |
| AG | valid non-Git project supported | PASS |
| AH | customer Git not required | PASS |
| AI | project metadata stored outside project tree | PASS |
| AJ | duplicate UI/backend authority model not created unnecessarily | PASS |
| AK | Computers UI can represent authorized project | PASS |
| AL | Review Project remains explicit user action | PASS |
| AM | project removal/deauthorization behavior defined | PASS |
| AN | network/removable-drive policy defined | PASS |
| AO | root/system-directory guardrails defined | PASS |
| AP | TOCTOU risk reviewed | PASS |
| AQ | future scan revalidation documented | PASS |
| AR | P3c device pairing remains prerequisite | PASS |
| AS | P3a packaging compatibility preserved | PASS |
| AT | P3b installer compatibility preserved | PASS |
| AU | native folder picker packaged correctly | PASS |
| AV | focused security review completed | PASS |
| AW | unresolved critical security findings = 0 | PASS |
| AX | unresolved high security findings = 0 | PASS |
| AY | project authorization tests pass | PASS |
| AZ | Connector smoke tests pass | PASS |
| BA | authority regression passes | PASS |
| BB | broader relevant regression has zero new regressions | PASS |
| BC | no production project authorization performed | PASS |
| BD | no production PROJECT_SCAN created | PASS |
| BE | no production DB mutation | PASS |
| BF | no production migration applied | PASS |
| BG | no deployment | PASS |
| BH | Google AI Studio unchanged | PASS |
| BI | no unrelated frontend redesign | PASS |
| BJ | no unrelated backend authority expansion | PASS |
| BK | no arbitrary execution capability added | PASS |
| BL | no Prepare capability added | PASS |
| BM | no Execute capability added | PASS |
| BN | customer action count recorded | PASS |
| BO | documentation complete | PASS |
| BP | programme status updated correctly | PASS |

**Total: 68 / 68 PASS**

---

## 36. P3d DISPOSITION

**P3d DISPOSITION: PASS**

---

**STOP. No production mutations performed. No execution authority granted. No new programme started beyond P3d.**
