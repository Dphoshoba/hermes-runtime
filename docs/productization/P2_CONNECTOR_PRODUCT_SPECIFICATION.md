# P2 — EVOSIA Connector Product Specification

**Date:** 2026-08-30
**P2 Baseline:** `1c6dab63ab25c293f347632e37c99658a0625d81`
**EVOSIA Version:** 1.3.0
**Purpose:** Define exactly what the customer-grade EVOSIA Connector must be before implementation begins.

---

## 1. EXECUTIVE SUMMARY

The EVOSIA Connector is the customer-facing product that transforms the technically certified Local Agent into something a non-technical person can install, connect, understand, and use on their own computer.

The engineering programme (LA0–LA6) proved that EVOSIA can safely connect to and review a project on another computer. This specification defines how that experience becomes suitable for ordinary customers.

The target customer journey is:

```
Download EVOSIA Connector
    ↓
Install (normal OS installer)
    ↓
Connect / Pair with EVOSIA account
    ↓
Choose project folder (native folder picker)
    ↓
Confirm Review Only authority
    ↓
Connected
    ↓
Review Project (human-initiated)
    ↓
See review progress/results in EVOSIA
```

The customer SHOULD NOT normally need: Git, Python, pip, virtualenv, PowerShell, terminal commands, environment variables, manual token handling, or developer knowledge.

**Current certified baseline:** `1c6dab63ab25c293f347632e37c99658a0625d81`

---

## 2. SCOPE

### In Scope

- Connector product definition (what it is, what it does, what it is NOT)
- Installation experience specification
- Account pairing flow specification
- Project folder selection specification
- Project authorization flow specification
- Background operation specification
- Local status UX specification
- Update mechanism requirements
- Uninstall/disconnect/revoke specification
- Error handling and recovery specification
- Credential storage direction
- Configuration management
- Windows-first platform strategy
- Security threat review
- Connector state machine
- Cloud/Connector responsibility matrix
- P1 UX integration boundary
- Product requirements (CONN-* identifiers)
- Decision log
- P3+ implementation decomposition

### Non-Goals

- Implementation of the Connector
- Building an installer
- Changing frontend application code
- Changing backend application code
- Changing evosia_agent runtime code
- Changing database schema
- Deploying to production
- Modifying production
- Modifying Google AI Studio
- Selecting specific packaging technology (decision criteria for P3)
- Purchasing code-signing certificates

---

## 3. CERTIFIED BASELINE

### Authority Boundary (MUST PRESERVE)

| Invariant | Value |
|-----------|-------|
| DeviceProject.authority | `REVIEW_ONLY` |
| ALLOWED_OPERATION_TYPES | `frozenset({"PROJECT_SCAN"})` |
| Execution authority | NOT GRANTED |
| Merge authority | NOT GRANTED |
| Deployment authority | NOT GRANTED |
| Autonomous job creation | NOT GRANTED |

### What the Connector MAY Do

- Establish trusted device identity
- Maintain outbound connection to EVOSIA Cloud
- Register explicitly authorized projects
- Receive governed PROJECT_SCAN work
- Perform certified bounded read-only review
- Return governed evidence
- Report health/connectivity
- Manage its own customer-facing lifecycle

### What the Connector MUST NOT Do

- Edit project files
- Prepare candidate patches
- Execute project code arbitrarily
- Merge code
- Deploy
- Run arbitrary shell commands
- Manufacture jobs
- Manufacture authority
- Silently authorize folders
- Scan arbitrary filesystem locations
- Widen project scope without human consent

### Certified Network Architecture

```
EVOSIA Connector
        │
        │ outbound HTTPS (only)
        ▼
   EVOSIA Cloud
```

**Customer-facing security property:** Normal operation requires NO inbound port, NO router configuration, NO port forwarding, NO customer firewall exposure, NO public listener on customer machine.

---

## 4. CUSTOMER PERSONA

### Primary User

The primary customer owns or manages a software project but may NOT:

- Know Python
- Know Git
- Know PowerShell
- Know terminal commands
- Understand JWTs
- Understand environment variables
- Understand APIs
- Understand virtual environments
- Understand package managers

### Secondary Users

Technical users may receive advanced diagnostics. Developer knowledge must not be required for normal installation.

---

## 5. CURRENT ACER JOURNEY

The Acer 1 engineering journey (LA6 certification) revealed the following current steps:

| Step | Action | Classification |
|------|--------|---------------|
| 1 | Have EVOSIA account with project in cloud | CUSTOMER-READY |
| 2 | Open EVOSIA Computers page | CUSTOMER-READY |
| 3 | Click "Add computer" | CUSTOMER-READY |
| 4 | Copy bootstrap token | NEEDS PRODUCTIZATION |
| 5 | Install Python on Windows | DEVELOPER-ONLY |
| 6 | Open PowerShell | DEVELOPER-ONLY |
| 7 | Run `pip install evosia-agent` or clone repo | DEVELOPER-ONLY |
| 8 | Run `python -m evosia_agent` | DEVELOPER-ONLY |
| 9 | Paste bootstrap token | DEVELOPER-ONLY |
| 10 | Agent connects | CUSTOMER-READY (after dev steps) |
| 11 | Click "Authorise project" in Cloud | CUSTOMER-READY |
| 12 | Copy project authorization token | NEEDS PRODUCTIZATION |
| 13 | Run `python -m evosia_agent project add <path> --authorization-token <token>` | DEVELOPER-ONLY |
| 14 | Navigate to project folder in terminal | DEVELOPER-ONLY |
| 15 | Project appears, click "Review project" | CUSTOMER-READY |
| 16 | See review lifecycle | CUSTOMER-READY |
| 17 | See results | CUSTOMER-READY |

**Current counts:** 19 total, 8 developer-only, 2 needs-productization, 9 customer-ready.

---

## 6. TARGET CUSTOMER JOURNEY

### Step 1 — Download

Customer signs into EVOSIA. Computers page provides "Add Computer" with platform-appropriate download:

- "Download for Windows"
- "Download for macOS" (future)
- "Download for Linux" (future)

### Step 2 — Install

Customer launches a normal OS installer:

- Recognizable EVOSIA identity
- Install location managed automatically
- Runtime dependencies bundled
- No separate Python install required
- No Git requirement
- No source clone
- No virtualenv
- No pip command

### Step 3 — Connect / Pair

```
EVOSIA Cloud:
    Add Computer
        ↓
    Generate short-lived pairing authorization
        ↓
    Display pairing code (6-8 characters, alphanumeric)

Connector:
    First launch → "Connect to EVOSIA"
        ↓
    Enter pairing code (or browser-assisted flow)
        ↓
    Device registered
        ↓
    Device credential stored securely
        ↓
    "Connected" confirmation
```

**Security requirements:**
- Pairing code is single-use, short-lived (5 minutes)
- Pairing code is device-scoped (binds to specific device)
- Pairing code is account-scoped (binds to specific user)
- No raw bootstrap token visible to customer
- Backend bootstrap token contract preserved (wrapped, not replaced)

### Step 4 — Device Identity

Customer-visible device properties:

| Property | Source |
|----------|--------|
| Computer name | User-provided or OS hostname |
| Operating system | Detected by Connector |
| Connector version | Bundled version |
| Online/offline status | Heartbeat-derived |
| Last connected | `last_seen_at` timestamp |

**Rename behavior:** Connector detects hostname changes and updates display name on next heartbeat.

**Reinstall behavior:** New installation requires re-pairing. Previous device entry remains in Cloud until explicitly revoked.

**Revoked behavior:** Connector detects revocation via heartbeat response, deletes local credential, displays clear "This computer has been disconnected" message.

### Step 5 — Choose Project

Customer selects a folder through a native OS folder picker:

```
"Choose project folder"
    ↓
Native Windows folder picker opens
    ↓
Customer selects folder
    ↓
Connector validates:
    - Path is absolute
    - Path exists
    - Path is a directory
    - No symlink escape
    - No sensitive-file violations
    ↓
Display selected folder clearly
    ↓
Compute SHA-256 fingerprint of canonical path
    ↓
Keep raw absolute path LOCAL (never sent to Cloud)
```

**What Cloud learns:** Folder display name, SHA-256 fingerprint, platform, agent version.
**What remains local:** Raw absolute path, full filesystem listing, file contents.

### Step 6 — Authorize Project

The human authority invariant MUST remain. The customer must explicitly authorize the selected project.

```
"Review Only"
    ↓
EVOSIA may review this project when you request a review.
EVOSIA cannot edit, execute, merge or deploy it.
    ↓
"I authorize this project for review"
    ↓
Connector requests project authorization token from Cloud
    ↓
Cloud generates single-use, 10-minute token
    ↓
Connector exchanges token to register DeviceProject
    ↓
Project appears in Computers page
```

**Authorization requirements:**
- Human initiated
- Project scoped
- Device scoped
- Account/user scoped
- Bounded (REVIEW_ONLY only)
- Auditable

The Connector must not silently self-authorize.

### Step 7 — Connected State

After successful authorization:

```
Acer 1
Connected

evosia-local-agent
Review only

Ready for review
```

### Step 8 — Review Project

Preserve the certified human-initiated workflow:

```
Cloud: "Review project"
    ↓
Backend creates governed PROJECT_SCAN
    ↓
Connector receives job through existing heartbeat mechanism
    ↓
Bounded read-only scan (1MB/file, 10MB total, 5000 files, 120s timeout)
    ↓
Results returned to Cloud
    ↓
Cloud displays:
    Review queued
    Review in progress
    Review complete
    Project unchanged
    (bounded-scan disclosure where applicable)
```

**Target counts:** 0 terminal commands, 0 developer-only steps, ~8 human actions total.

---

## 7. PRODUCT IDENTITY

| Field | Value |
|-------|-------|
| Customer-facing name | EVOSIA Connector |
| Internal runtime name | evosia_agent |
| Relationship | Connector wraps evosia_agent; Connector is the customer-visible product; evosia_agent is the internal implementation |
| Parent product | EVOSIA Enterprise / EVOSIA Cloud |
| Organization | Echoes & Visions |

**Do NOT rename packages during P2.** Document terminology only.

---

## 8. ARCHITECTURE

### Layered Architecture

```
┌─────────────────────────────────┐
│     EVOSIA Cloud (Control)      │
│  User identity, device trust,   │
│  project authorization, job     │
│  creation, review display       │
└──────────────┬──────────────────┘
               │ outbound HTTPS
               │ (no inbound ports)
┌──────────────▼──────────────────┐
│     EVOSIA Connector (Product)  │
│  Customer-facing lifecycle,     │
│  installation, pairing,         │
│  folder selection, tray UI      │
├─────────────────────────────────┤
│     evosia_agent (Runtime)      │
│  Device identity, credential,   │
│  heartbeat, bounded scan,       │
│  evidence submission            │
├─────────────────────────────────┤
│     Local Filesystem            │
│  Authorized project folders     │
│  Only with explicit human auth  │
└─────────────────────────────────┘
```

### Separation of Concerns

| Layer | Responsibility |
|-------|---------------|
| Connector UI | Installation, pairing UX, folder picker, tray, status display |
| evosia_agent Runtime | Credential management, heartbeat, scan execution, evidence submission |
| EVOSIA Cloud | User identity, device trust, project authorization, job creation, review presentation |

---

## 9. FIRST-RUN EXPERIENCE

### Sequence

1. Customer launches EVOSIA Connector after installation
2. Connector displays: "Welcome to EVOSIA Connector"
3. Connector explains: "EVOSIA Connector connects your computer to EVOSIA so you can review your software projects."
4. Connector provides: "Connect to EVOSIA" button
5. Customer clicks button
6. Connector opens browser to EVOSIA login (or pairing code entry)
7. Customer authenticates
8. Browser returns pairing result to Connector
9. Connector confirms: "Connected to EVOSIA as [account name]"
10. Connector prompts: "Choose a project folder to review"
11. Native folder picker opens
12. Customer selects folder
13. Connector explains Review Only authority
14. Customer authorizes
15. Connector confirms: "Ready for review"
16. Connector moves to background / tray

**Total human actions:** ~8 (sign in, connect, choose folder, authorize, review)

---

## 10. INSTALLATION

### Windows Target

| Requirement | Specification |
|-------------|--------------|
| Installer type | Standard Windows installer (EXE or MSI) |
| Runtime | Bundled Python runtime or equivalent |
| Dependencies | Bundled with installer |
| Install location | `%PROGRAMFILES%\EVOSIA\` or `%LOCALAPPDATA%\EVOSIA\` |
| Start menu | "EVOSIA Connector" shortcut |
| Desktop shortcut | Optional (preference) |
| Automatic startup | Configurable during install (default: yes) |
| Uninstaller | Standard Windows "Add or Remove Programs" entry |
| Permissions | Standard user (no admin required for agent operation) |

### Packaging Decision Criteria (for P3)

P3 must evaluate:

- Python runtime bundling approach (PyInstaller, Nuitka, embedded Python, etc.)
- Installer framework (Inno Setup, NSIS, WiX, Electron Builder, etc.)
- Binary size constraints
- Code signing requirements
- Update mechanism compatibility
- Cross-platform strategy (Windows first, macOS/Linux later)

### What the Installer Must NOT Require

- Python installed separately
- Git installed
- pip command
- virtualenv
- Repository clone
- Environment variable configuration
- Terminal/PowerShell interaction

---

## 11. PAIRING

### Recommended Approach: Browser-Assisted Pairing

**Flow:**

1. Customer clicks "Connect to EVOSIA" in Connector
2. Connector starts local HTTP listener on `127.0.0.1` (random high port, temporary)
3. Connector opens default browser to `https://evosia-cloud.fly.dev/pair?port=XXXXX&token=YYYYY`
4. Customer signs into EVOSIA in browser (if not already)
5. Browser shows: "Connect [Computer Name] to your EVOSIA account?"
6. Customer clicks "Connect"
7. Browser sends pairing confirmation to Connector's local listener
8. Connector closes local listener
9. Connector exchanges bootstrap token with Cloud for device credential
10. Connector stores credential securely
11. Connector displays: "Connected to EVOSIA"

**Security properties:**
- Local listener is bound to `127.0.0.1` only (not accessible from network)
- Listener is temporary (exists only during pairing)
- Pairing token is short-lived (5 minutes)
- Pairing token is single-use
- Pairing token is device-scoped
- No raw bootstrap token visible to customer
- Bootstrap token contract is preserved (wrapped by browser flow)

### Alternative: Pairing Code

If browser-assisted pairing is not feasible:

1. Customer clicks "Add Computer" in EVOSIA Cloud
2. Cloud displays 6-8 character pairing code
3. Customer enters code in Connector
4. Connector exchanges pairing code for device credential

**Security properties:**
- Code is short-lived (5 minutes)
- Code is single-use
- Code is device-scoped
- Code is account-scoped

### Decision: Browser-assisted pairing is RECOMMENDED for P3

Rationale:
- No manual code entry required
- Leverages existing EVOSIA authentication
- More secure (no code visible to shoulder-surfers)
- Better UX (one click in browser)
- Standard pattern (OAuth device flow)

---

## 12. DEVICE IDENTITY

### Customer-Visible Properties

| Property | Display | Source |
|----------|---------|--------|
| Computer name | User-provided or hostname | OS `socket.gethostname()` |
| Operating system | "Windows", "Mac", "Linux" | `platform.system()` |
| Connector version | "0.1.0" | Bundled constant |
| Status | "Online" / "Offline" / "Revoked" | Heartbeat-derived |
| Last seen | "2 minutes ago" | `last_seen_at` timestamp |

### State Behavior

| Event | Connector Behavior |
|-------|-------------------|
| Computer renamed | Update display name on next heartbeat |
| Connector reinstalled | Requires re-pairing; previous entry remains until revoked |
| Credential missing | Prompt re-pairing |
| Credential expired | Prompt re-pairing (AUTH_REQUIRED state) |
| Device revoked | Display "This computer has been disconnected from EVOSIA"; delete local credential |
| User changes account | Disconnect current; re-pair with new account |

---

## 13. FOLDER SELECTION

### Native OS Folder Picker

- Windows: `IFileDialog` / `SHBrowseForFolder`
- macOS: `NSOpenPanel`
- Linux: `GtkFileChooserDialog`

### Validation

After folder selection, Connector validates:

1. Path is absolute
2. Path exists and is a directory
3. Symlink escape check (fail-closed)
4. Sensitive-file classification

### Fingerprint Computation

```
canonical_path = resolve(path) → absolute, normalized
fingerprint = SHA-256(canonical_path.as_posix())
```

### Data Boundary

| Data | Sent to Cloud | Remains Local |
|------|--------------|---------------|
| Folder display name | YES | — |
| SHA-256 fingerprint | YES | — |
| Platform | YES | — |
| Agent version | YES | — |
| Raw absolute path | — | YES |
| File listing | — | YES |
| File contents | — | YES (during scan only) |
| Symlink targets | — | YES |

---

## 14. PROJECT AUTHORIZATION

### Wrapped Contract

The existing single-use project authorization token contract is wrapped behind the product UX:

```
Customer clicks "Authorize for review"
    ↓
Connector calls POST /api/devices/{id}/project-auth-token
    ↓
Cloud generates single-use, 10-minute token
    ↓
Connector calls POST /api/device-projects/ with token
    ↓
DeviceProject created with authority=REVIEW_ONLY
    ↓
Project appears in Computers page
```

### Authority Consequence Statement (Required)

> EVOSIA may review this project when you request a review.
> EVOSIA cannot edit, execute, merge or deploy it.
> Review only.

---

## 15. CONNECTED STATE

### Customer-Visible States

| State | Meaning | Customer Action |
|-------|---------|----------------|
| Connecting | Pairing in progress | Wait |
| Connected | Active and ready | Normal operation |
| Offline | Not communicating | Check internet |
| Authorization required | Project needs authorization | Authorize project |
| Project ready | Authorized and ready for review | Click "Review project" |
| Review queued | Review request sent | Wait |
| Reviewing | Scan in progress | Wait |
| Review complete | Results available | View results |
| Review failed | Scan encountered error | Retry or diagnose |
| Device revoked | Trust revoked | Re-pair or contact admin |
| Update available | New Connector version | Update recommended |

---

## 16. BACKGROUND OPERATION

### Recommended Model: Background Process + System Tray

**Connector UI Process:**
- Tray icon with context menu
- No visible window during normal operation
- Opens settings/status window on tray icon click

**Connector Background Runtime:**
- Heartbeat loop (60s interval)
- Job polling (via heartbeat response)
- Scan execution
- Evidence submission
- Retry/backoff (5s → 60s)

**Startup behavior:**
- Starts automatically on Windows login (configurable)
- Survives user closing settings window
- Reconnects after network loss
- Reconnects after restart
- Bounded retry/backoff

### Decision: Background process + system tray is RECOMMENDED for P3

Rationale:
- Standard Windows UX pattern
- No terminal required
- Visible status via tray icon
- User can quit deliberately
- Compatible with bundled runtime

---

## 17. LOCAL UX (SYSTEM TRAY)

### Context Menu

| Action | Description |
|--------|-------------|
| "Open EVOSIA" | Open EVOSIA Cloud in browser |
| "Status" | Show connection status window |
| "Add project" | Open folder picker |
| "Authorized projects" | List authorized projects |
| "Check for update" | Manual update check |
| "Diagnostics" | Show diagnostic info |
| "Quit" | Disconnect and quit |

### Status Window

- Connector version
- Operating system
- Connection state
- Last successful Cloud contact
- Authorized project count
- Last review state
- Update state

### Authority-Sensitive Actions

All actions obey Cloud/backend contracts. The local UI is NOT a second authority system.

---

## 18. STARTUP AND RESTART BEHAVIOR

| Event | Behavior |
|-------|----------|
| Windows login | Connector starts if auto-start enabled |
| Machine reboot | Connector restarts if auto-start enabled |
| Temporary internet loss | Retry/backoff; offline status displayed |
| Cloud outage | Retry/backoff; offline status displayed |
| Connector crash | OS auto-restart (if configured); otherwise manual restart |
| Sleep/wake | Reconnect on wake; retry/backoff |
| Credential expiry | Display "Re-pairing required"; delete local credential |
| Revoked device | Display "Disconnected"; delete local credential |

**No connectivity must never imply permission expansion.**

---

## 19. CREDENTIAL STORAGE

### Current State

| File | Location (Windows) | Permissions |
|------|-------------------|-------------|
| `device.json` | `%LOCALAPPDATA%\EVOSIA\device.json` | Best-effort `0o600` |

Contents: `device_id`, `device_name`, `credential` (JWT), `cloud_url`.

### Target Direction: REPLACE with OS-native secure storage

| Platform | Target Store | Classification |
|----------|-------------|---------------|
| Windows | Windows Credential Manager / DPAPI | REPLACE |
| macOS | macOS Keychain | REPLACE |
| Linux | Linux secret service / keyring | REPLACE |

### Rationale

- Current file-based storage has known limitations (Windows permissions best-effort)
- OS keychain provides encryption at rest, access control, and user visibility
- Standard pattern for application credentials
- Customer can manage credentials through OS security UI

**Do not implement during P2.** Specify direction for P3.

---

## 20. CONFIGURATION

### Production Endpoint

The customer must NOT manually set `EVOSIA_CLOUD_URL`.

| Channel | Endpoint | Configuration |
|---------|----------|--------------|
| Production | `https://evosia-cloud.fly.dev` | Embedded in Connector binary |
| Development | `http://localhost:8000` | Development flag only |
| Staging | (future) | Configuration flag |

### Environment Separation

- Production Connector connects to production Cloud only
- Development Connector requires explicit opt-in
- No accidental customer connection to development endpoints

### Secrets

No secrets are embedded in the Connector binary. All authentication is through pairing flow.

---

## 21. UPDATES

### Update Strategy

| Requirement | Specification |
|-------------|--------------|
| Update discovery | Connector checks Cloud on startup/heartbeat |
| Signed updates | Required for production distribution |
| User notification | "Update available" in tray/status |
| Automatic update | Configurable (default: notify only) |
| Rollback | Previous version retained until new version confirmed |
| Cloud compatibility | Cloud defines minimum supported Connector version |

### What Updates Must NOT Require

- `git pull`
- Source checkout
- `pip install -e`
- Manual dependency repair
- Developer intervention

---

## 22. VERSION COMPATIBILITY

### Current Versions

| Component | Version |
|-----------|---------|
| EVOSIA Platform | 1.3.0 |
| evosia-agent | 0.1.0 |

### Compatibility Model

| Scenario | Cloud Behavior |
|----------|---------------|
| Supported Connector | Normal operation |
| Old but compatible Connector | Operation with deprecation warnings |
| Upgrade required Connector | Reject with clear upgrade instructions |
| Unknown/newer Connector | Allow with capability negotiation |

### Minimum Supported Version

Cloud defines `MINIMUM_CONNECTOR_VERSION`. Connectors below this version receive explicit upgrade instructions.

---

## 23. DISCONNECT / REVOKE / UNINSTALL

### Distinct Customer Actions

| Action | Effect | Reversible |
|--------|--------|-----------|
| **Disconnect** | Temporarily stop Connector connectivity; credential preserved | Reconnect |
| **Remove project** | Stop authorization for a particular project; DeviceProject revoked | Re-authorize |
| **Revoke computer** | Cloud invalidates device trust; credential deleted | Re-pair |
| **Uninstall** | Remove Connector software from computer | Reinstall + re-pair |

### State Transitions

```
Connected --Disconnect--> Disconnected (credential preserved)
Disconnected --Reconnect--> Connected

Connected --Remove project--> Project removed (other projects unaffected)

Connected --Revoke computer--> Revoked (credential deleted, all projects revoked)

Connected --Uninstall--> Removed (all state deleted)
```

No action should silently grant authority later.

---

## 24. RECOVERY FLOWS

| Failure | Customer Message | Resolution |
|---------|-----------------|------------|
| Pairing code expired | "Pairing code expired. Please generate a new one." | New pairing code |
| Pairing failed | "Could not connect. Please try again." | Retry pairing |
| Computer already registered | "This computer is already connected." | Show existing connection |
| Project already authorized | "This project is already authorized." | Show in project list |
| Folder moved | "Project folder not found at expected location." | Re-authorize at new location |
| Folder deleted | "Project folder no longer exists." | Remove from authorized list |
| Fingerprint changed | "Project appears to be different. Please re-authorize." | Re-authorize |
| Credential missing | "Re-pairing required." | Re-pair with EVOSIA |
| Device revoked | "This computer has been disconnected from EVOSIA." | Contact admin or re-pair |
| Cloud unreachable | "EVOSIA Cloud is temporarily unavailable. Retrying..." | Automatic retry |
| Review failed | "Review encountered an error. Please try again." | Retry review |
| Review reached limits | "Review completed with limits. Some files may not have been examined." | Results available |
| Connector outdated | "A new version of EVOSIA Connector is available." | Update recommended |
| Update failed | "Update failed. Current version is still working." | Retry update |

Every failure provides: what happened, whether anything changed, what the user can safely do next.

---

## 25. DIAGNOSTICS

### Customer-Facing Diagnostics

| Field | Visible |
|-------|---------|
| Connector version | YES |
| Operating system | YES |
| Connection state | YES |
| Last successful Cloud contact | YES |
| Authorized project count | YES |
| Last review state | YES |
| Update state | YES |

### Advanced Diagnostics

- Sanitized logs (redacted)
- Available via "Diagnostics" menu

### Secret Redaction Requirements

NEVER expose:

- Device credentials
- Bootstrap tokens
- Project authorization tokens
- API keys
- Secrets
- Sensitive project contents
- Raw file paths (use fingerprints)

---

## 26. PROJECT PRIVACY MODEL

### What the Connector May Inspect

Only the project the customer explicitly authorizes.

### What EVOSIA Cloud Receives

| Data | Received | Notes |
|------|----------|-------|
| Folder display name | YES | Directory name only |
| SHA-256 fingerprint | YES | Of canonical path |
| Platform | YES | "windows", "macos", "linux" |
| Agent version | YES | "evosia-agent/0.1.0" |
| Scan results | YES | Bounded evidence |
| Git metadata | YES | Branch, commit, status (truncated) |
| File contents | YES | During scan only, bounded |
| Raw absolute path | NO | Never leaves device |
| Full file listing | NO | Only scanned files in evidence |
| Sensitive files | NO | Content never transmitted |

### Bounded Scan Constraints

| Limit | Value |
|-------|-------|
| Max file size | 1 MB |
| Max total scan content | 10 MB |
| Max file count | 5,000 |
| Scan timeout | 120 seconds |

### Customer-Facing Disclosure

> EVOSIA reviews only the project you explicitly authorize.
> Raw absolute project paths remain on your computer.
> Sensitive credential/key files are not transmitted as ordinary review content.
> Reviews are bounded and may not examine every file.

---

## 27. OFFLINE BEHAVIOR

### Decision: Review button unavailable while computer is offline

**Rationale:**
- Current job architecture requires active device connection
- Queueing offline work introduces expiry, cancellation, stale-work handling, and authority revalidation complexity
- Simpler customer experience: "Connect your computer to start a review"
- Avoids false expectations about offline capability

### Cloud Behavior When Device Offline

| State | Cloud Display |
|-------|--------------|
| Computer online | "Online" badge |
| Computer offline | "Offline — last seen [time]" |
| Review requested but offline | "Review unavailable — computer must be connected" |

---

## 28. MULTIPLE COMPUTERS

### Behavior

- Each computer is a separate Device
- Project authorization is device-specific
- Same project can be authorized on multiple devices (separate DeviceProject records)
- Path equality across machines is NOT assumed (fingerprints may differ)
- Each device independently polls for jobs

### Customer Experience

- Computers page shows all connected devices
- Each device shows its authorized projects independently
- Review history is per-device-project

---

## 29. MULTIPLE ACCOUNTS / ORGANIZATIONS

### Current Production Support

Source inspection confirms: user_id ownership is enforced. Each Device belongs to one user. No organization model is currently implemented.

### Specification

- Connector connects to one EVOSIA account at a time
- To switch accounts: disconnect current, re-pair with new account
- Future organization support: record as FUTURE REQUIREMENT

---

## 30. PLATFORM MATRIX

| Property | Windows | macOS | Linux |
|----------|---------|-------|-------|
| Certified runtime | YES (LA6) | YES (LA2) | YES (LA2) |
| Installer required | YES | YES | YES |
| Credential store target | Windows Credential Manager / DPAPI | macOS Keychain | Linux secret service |
| Startup model | Background process + tray | Background process + menu bar | Background process + tray |
| Local UI model | System tray | Menu bar | System tray |
| Update model | Signed installer | Signed package | Package manager |
| Productization status | PRIMARY (P3) | FUTURE | FUTURE |

---

## 31. ACER LESSONS → PRODUCT REQUIREMENTS

| # | Lesson | Product Requirement |
|---|--------|-------------------|
| A | Source checkout not required | CONN-INSTALL-001: No source clone needed |
| B | Python bundled/hidden | CONN-INSTALL-002: Runtime bundled with installer |
| C | Virtualenv not customer-managed | CONN-INSTALL-003: No virtualenv required |
| D | Cloud URL not from env vars | CONN-RUNTIME-001: Production endpoint embedded |
| E | Registration not raw token workflow | CONN-PAIR-001: Browser-assisted pairing |
| F | Deterministic credential storage | CONN-SEC-001: OS keychain integration |
| G | Authorization preserves human authority | CONN-AUTH-001: Wrapped authorization UX |
| H | Background agent no terminal | CONN-RUNTIME-002: Background process |
| I | Timezone-safe timestamps | CONN-SEC-002: UTC timestamps throughout |
| J | UI polls/refreshes correctly | CONN-UX-001: Heartbeat-driven status |
| K | Synchronous duplicate-click protection | CONN-UX-002: Frontend request guards |
| L | Backend rejects duplicate active jobs | CONN-SEC-003: Active-job guard preserved |
| M | Customer sees queued/reviewing/complete/failed | CONN-UX-003: Review lifecycle display |
| N | Customer sees "Project unchanged" | CONN-UX-004: Immutability confirmation |
| O | Bounded review disclosure | CONN-UX-005: Truncation disclosure |
| P | Updates not via git pull | CONN-UPDATE-001: Signed update mechanism |
| Q | Recovery not via repo debugging | CONN-RECOVERY-001: Friendly error messages |

---

## 32. DISTRIBUTION TRUST

### Requirements

| Requirement | Specification |
|-------------|--------------|
| Official download source | EVOSIA website / EVOSIA Cloud |
| Installer integrity | SHA-256 checksum |
| Code signing | Required for Windows production |
| Publisher identity | "Echoes & Visions" or "EVOSIA" |
| OS trust warnings | Minimize via code signing |
| Release provenance | Version + build metadata |
| Update package verification | Signature verification |

### What Must Be Solved Before Public Windows Distribution

1. Code signing certificate procurement
2. Publisher identity verification
3. Installer signing workflow
4. Update package signing

---

## 33. SECURITY THREAT REVIEW

| Threat | Existing Mitigation | Productization Gap | P3+ Requirement |
|--------|-------------------|-------------------|----------------|
| Stolen pairing code | 5-min TTL, single-use | Short window only | Browser-assisted pairing reduces exposure |
| Replayed pairing token | Single-use enforcement | None | Preserve single-use |
| Stolen device credential | 30-day JWT, revocation | File-based storage | OS keychain integration |
| Malicious local user | File permissions (best-effort) | Windows permissions weak | OS keychain provides better protection |
| Malicious project symlink | Symlink escape detection, fail-closed | None | Preserve escape detection |
| Path escape | Canonical path validation | None | Preserve validation |
| Fake EVOSIA Cloud endpoint | HTTPS, embedded URL | Env var override possible | Embed URL, remove env var override for production |
| Malicious update package | (not yet implemented) | No update mechanism | Signed updates required |
| Stale/revoked device | Heartbeat revocation detection | None | Preserve detection |
| Duplicate job submission | Active-job guard (409) | None | Preserve guard |
| Unauthorized folder registration | Human authorization required | Token copy/paste UX | Wrapped authorization UX |
| Sensitive-file exfiltration | Content never transmitted | None | Preserve protection |
| Log secret leakage | (not yet implemented) | No log redaction | Redaction requirements |
| Local privilege escalation | Standard user operation | None | No privilege escalation required |
| Compromised customer project | Bounded scan limits | None | Preserve limits |

---

## 34. CONNECTOR STATE MACHINE

### States

| State | Customer Meaning | Allowed Actions | Authority |
|-------|-----------------|----------------|-----------|
| NOT_INSTALLED | Connector not on computer | Install | None |
| INSTALLED_UNPAIRED | Installed but not connected | Pair | None |
| PAIRING | Pairing in progress | Wait | None |
| CONNECTED_NO_PROJECT | Connected, no projects authorized | Add project | None |
| PROJECT_AUTHORIZATION_REQUIRED | Project selected, awaiting authorization | Authorize | None |
| READY | Connected and authorized | Review project | REVIEW_ONLY |
| REVIEW_QUEUED | Review request sent | Wait | REVIEW_ONLY |
| REVIEWING | Scan in progress | Wait | REVIEW_ONLY |
| REVIEW_COMPLETE | Results available | View results | REVIEW_ONLY |
| REVIEW_FAILED | Scan encountered error | Retry | REVIEW_ONLY |
| OFFLINE | Not communicating | Check connection | None |
| REVOKED | Trust revoked | Re-pair | None |
| UPDATE_REQUIRED | New version available | Update | REVIEW_ONLY |

### Transitions

```
NOT_INSTALLED --install--> INSTALLED_UNPAIRED
INSTALLED_UNPAIRED --pair--> PAIRING
PAIRING --success--> CONNECTED_NO_PROJECT
PAIRING --failure--> INSTALLED_UNPAIRED
CONNECTED_NO_PROJECT --add project--> PROJECT_AUTHORIZATION_REQUIRED
PROJECT_AUTHORIZATION_REQUIRED --authorize--> READY
PROJECT_AUTHORIZATION_REQUIRED --cancel--> CONNECTED_NO_PROJECT
READY --review request--> REVIEW_QUEUED
REVIEW_QUEUED --job received--> REVIEWING
REVIEWING --complete--> REVIEW_COMPLETE
REVIEWING --failure--> REVIEW_FAILED
REVIEW_FAILED --retry--> REVIEW_QUEUED
REVIEW_COMPLETE --new review--> REVIEW_QUEUED
ANY --network loss--> OFFLINE
OFFLINE --reconnect--> previous state
ANY --revoked--> REVOKED
ANY --credential expired--> INSTALLED_UNPAIRED
ANY --update available--> UPDATE_REQUIRED (overlay)
```

**No state may imply expanded authority.**

---

## 35. CLOUD / CONNECTOR RESPONSIBILITY MATRIX

| Responsibility | Cloud | Connector | Shared |
|---------------|-------|-----------|--------|
| User identity | PRIMARY | — | — |
| Human authority | PRIMARY | — | — |
| Device trust issuance | PRIMARY | — | — |
| Device trust revocation | PRIMARY | — | DETECT |
| Project authorization | PRIMARY | — | — |
| Governed job creation | PRIMARY | — | — |
| Review presentation | PRIMARY | — | — |
| Authoritative findings | PRIMARY | — | — |
| Gemini explanation governance | PRIMARY | — | — |
| Device credential possession | — | PRIMARY | — |
| Local project path | — | PRIMARY | — |
| Filesystem containment | — | PRIMARY | — |
| Local bounded scan | — | PRIMARY | — |
| Local git metadata collection | — | PRIMARY | — |
| Heartbeat | — | PRIMARY | — |
| Governed job consumption | — | PRIMARY | — |
| Safe result submission | — | PRIMARY | — |
| Device status | — | — | SYNCHRONIZE |
| Project display identity | — | — | SYNCHRONIZE |
| Review lifecycle | — | — | SYNCHRONIZE |
| Version compatibility | — | — | NEGOTIATE |

**Authority duplication is explicitly prevented.**

---

## 36. P1 UX INTEGRATION

### Integration Boundary

A completed real PROJECT_SCAN feeds the canonical P1 product UX:

**Guided Mode:**
- Overview (plain-language summary)
- Needs Your Attention (findings)
- Needs Context (questions)
- Recommendations (proposed work)
- Ask EVOSIA (conversational explanations)

**Technical View:**
- Technical findings
- Classifications, locations, evidence hashes
- Provenance
- Mission traceability
- Audit/governance information

### Same Authoritative State Principle

Guided Mode and Technical View MUST consume the SAME authoritative backend state. The Connector provides evidence; the Cloud presents it.

**P2 must NOT implement these surfaces.** It specifies the integration boundary for later milestones.

---

## 37. CUSTOMER SUCCESS METRICS

| Metric | Target |
|--------|--------|
| Terminal commands required | 0 |
| Developer-only steps required | 0 |
| Human actions (total) | ≤ 8 |
| Successful first connection | Target: > 95% |
| Successful project authorization | Target: > 95% |
| Successful first review | Target: > 90% |
| Recovery from common failures | Target: > 90% self-service |

---

## 38. PRODUCT REQUIREMENTS

### CONN-INSTALL

| ID | Requirement | Rationale | Source | Acceptance | Milestone |
|----|-------------|-----------|--------|------------|-----------|
| CONN-INSTALL-001 | No source clone required | Acer lesson A | LA6 | Customer never clones repo | P3 |
| CONN-INSTALL-002 | Runtime bundled with installer | Acer lesson B | LA6 | No separate Python install | P3 |
| CONN-INSTALL-003 | No virtualenv required | Acer lesson C | LA6 | No virtualenv interaction | P3 |
| CONN-INSTALL-004 | Standard OS installer UX | Customer expectation | P0 | Normal installer wizard | P3 |
| CONN-INSTALL-005 | No admin privileges required | Accessibility | P0 | Standard user can install | P3 |

### CONN-PAIR

| ID | Requirement | Rationale | Source | Acceptance | Milestone |
|----|-------------|-----------|--------|------------|-----------|
| CONN-PAIR-001 | Browser-assisted pairing | Acer lesson E, UX | P1 | No manual token paste | P4 |
| CONN-PAIR-002 | Single-use pairing token | Security | LA1 | Token consumed on use | P4 |
| CONN-PAIR-003 | 5-minute pairing expiry | Security | LA1 | Expired token rejected | P4 |
| CONN-PAIR-004 | Device-scoped pairing | Security | LA1 | Token bound to device | P4 |
| CONN-PAIR-005 | Account-scoped pairing | Security | LA1 | Token bound to user | P4 |

### CONN-AUTH

| ID | Requirement | Rationale | Source | Acceptance | Milestone |
|----|-------------|-----------|--------|------------|-----------|
| CONN-AUTH-001 | Wrapped authorization UX | Acer lesson G | P1 | No manual token paste | P5 |
| CONN-AUTH-002 | Explicit human authorization | Authority invariant | LA3 | Human must explicitly authorize | P5 |
| CONN-AUTH-003 | REVIEW_ONLY authority | Authority invariant | LA0 | Only review authority granted | P5 |
| CONN-AUTH-004 | Authority consequence statement | P1 UX | P1 | Statement displayed | P5 |

### CONN-PROJECT

| ID | Requirement | Rationale | Source | Acceptance | Milestone |
|----|-------------|-----------|--------|------------|-----------|
| CONN-PROJECT-001 | Native folder picker | UX | P0 | OS folder picker used | P5 |
| CONN-PROJECT-002 | Symlink escape protection | Security | LA3 | Escape detected, fail-closed | P5 |
| CONN-PROJECT-003 | Sensitive-file protection | Security | LA3 | Sensitive files not read | P5 |
| CONN-PROJECT-004 | Path fingerprint only to Cloud | Privacy | LA3 | Raw path never sent | P5 |

### CONN-RUNTIME

| ID | Requirement | Rationale | Source | Acceptance | Milestone |
|----|-------------|-----------|--------|------------|-----------|
| CONN-RUNTIME-001 | Production endpoint embedded | Acer lesson D | P0 | No env var required | P3 |
| CONN-RUNTIME-002 | Background process | Acer lesson H | P0 | No terminal required | P6 |
| CONN-RUNTIME-003 | Heartbeat every 60s | Certified | LA2 | Heartbeat loop running | P6 |
| CONN-RUNTIME-004 | Retry/backoff 5s→60s | Certified | LA2 | Backoff functioning | P6 |
| CONN-RUNTIME-005 | Bounded scan limits | Certified | LA4 | Limits enforced | P6 |

### CONN-UPDATE

| ID | Requirement | Rationale | Source | Acceptance | Milestone |
|----|-------------|-----------|--------|------------|-----------|
| CONN-UPDATE-001 | Signed update mechanism | Security | P2 | Updates verified | P7 |
| CONN-UPDATE-002 | Update discovery via Cloud | UX | P2 | Cloud notifies of updates | P7 |
| CONN-UPDATE-003 | No git pull required | Acer lesson P | P6 | Updates via installer | P7 |

### CONN-SEC

| ID | Requirement | Rationale | Source | Acceptance | Milestone |
|----|-------------|-----------|--------|------------|-----------|
| CONN-SEC-001 | OS keychain integration | Security | P2 | Credentials in OS keychain | P6 |
| CONN-SEC-002 | UTC timestamps | Acer lesson I | LA6 | Timezone-safe throughout | P6 |
| CONN-SEC-003 | Active-job guard | Security | LA4 | Duplicate jobs rejected | P6 |
| CONN-SEC-004 | Log secret redaction | Security | P2 | No secrets in logs | P6 |

### CONN-UX

| ID | Requirement | Rationale | Source | Acceptance | Milestone |
|----|-------------|-----------|--------|------------|-----------|
| CONN-UX-001 | Heartbeat-driven status | Acer lesson J | LA6 | Status reflects actual state | P6 |
| CONN-UX-002 | Duplicate-click protection | Acer lesson K | LA6 | Frontend guards in place | P6 |
| CONN-UX-003 | Review lifecycle display | Acer lesson M | LA6 | Queued/reviewing/complete/failed shown | P6 |
| CONN-UX-004 | Immutability confirmation | Acer lesson N | LA6 | "Project unchanged" displayed | P6 |
| CONN-UX-005 | Truncation disclosure | Acer lesson O | LA6 | Limits disclosed | P6 |

### CONN-RECOVERY

| ID | Requirement | Rationale | Source | Acceptance | Milestone |
|----|-------------|-----------|--------|------------|-----------|
| CONN-RECOVERY-001 | Friendly error messages | Acer lesson Q | P6 | No stack traces to customer | P6 |
| CONN-RECOVERY-002 | Self-service recovery | UX | P2 | > 90% self-service | P6 |

---

## 39. DECISION LOG

| # | Decision | Alternatives | Reason | Security Effect | UX Effect | Reversible |
|---|----------|-------------|--------|----------------|-----------|------------|
| 1 | Browser-assisted pairing | Pairing code, QR, manual token | Better UX, leverages existing auth, no code visible | Reduced shoulder-surf risk | One-click pairing | YES |
| 2 | REVIEW_ONLY authority | Higher authority levels | Certified boundary; authority expansion requires separate programme | Maintains safety | Clear limitation | NO (by design) |
| 3 | Background process + tray | Windows service, console app | Standard UX pattern, visible status, user can quit | Neutral | Good | YES |
| 4 | OS keychain for credentials | File-based storage | Better encryption, access control, user visibility | Improved | Standard UX | YES |
| 5 | Offline: review unavailable | Queue while offline | Simpler, avoids expiry/stale-work complexity | Neutral | Clear expectation | YES |
| 6 | Windows-first | Simultaneous cross-platform | Validated path, reduces risk, faster delivery | Neutral | Faster to market | YES |
| 7 | Signed updates | Unsigned updates | Security requirement for distribution | Required | Trust signal | NO (by design) |
| 8 | No env var for production URL | Env var configuration | Customer must not configure endpoints | Reduced misconfiguration | Simpler setup | YES |

---

## 40. P3+ DECOMPOSITION

### Recommended Implementation Milestones

| Milestone | Scope | Dependencies |
|-----------|-------|-------------|
| P3a | Connector packaging foundation (bundled runtime, basic installer) | P2 |
| P3b | Windows installer (MSI/EXE, start menu, auto-start) | P3a |
| P4a | Browser-assisted pairing (local listener, Cloud integration) | P3b |
| P4b | Pairing confirmation and device lifecycle | P4a |
| P5a | Native folder picker integration | P4b |
| P5b | Project authorization wrapping | P5a |
| P6a | Background startup, tray icon, status display | P5b |
| P6b | Review lifecycle integration, scanning, results | P6a |
| P6c | Recovery flows, error handling, diagnostics | P6b |
| P7a | OS keychain credential storage | P6c |
| P7b | Signed update mechanism | P7a |
| P7c | Distribution signing and packaging | P7b |
| P8 | Non-technical onboarding validation | P7c |

---

## 41. ACCEPTANCE GATES

| Gate | Description | Status |
|------|-------------|--------|
| A | Current Acer journey converted to product requirements | PASS |
| B | Target journey requires zero terminal commands | PASS |
| C | Target journey requires zero developer-only steps | PASS |
| D | Installation experience specified | PASS |
| E | Pairing experience specified | PASS |
| F | Project folder selection specified | PASS |
| G | Project authorization preserves human authority without manual token paste | PASS |
| H | Background operation specified | PASS |
| I | Restart/reconnect behavior specified | PASS |
| J | Credential storage direction specified | PASS |
| K | Production endpoint configuration specified | PASS |
| L | Update mechanism requirements specified | PASS |
| M | Uninstall/disconnect/revoke behavior specified | PASS |
| N | Recovery flows specified | PASS |
| O | Diagnostics and redaction specified | PASS |
| P | Privacy/data-boundary disclosure specified | PASS |
| Q | Offline behavior decided | PASS |
| R | Multi-computer behavior specified | PASS |
| S | Windows-first strategy specified | PASS |
| T | Installer trust/signing requirements identified | PASS |
| U | Focused threat review complete | PASS |
| V | Connector state machine defined | PASS |
| W | Cloud/Connector responsibility matrix defined | PASS |
| X | P1 UX integration boundary defined | PASS |
| Y | Measurable onboarding success criteria defined | PASS |
| Z | Durable product requirements enumerated | PASS |
| AA | P3+ implementation decomposition defined | PASS |
| AB | REVIEW_ONLY remains unchanged | PASS |
| AC | ALLOWED_OPERATION_TYPES remains exactly PROJECT_SCAN | PASS |
| AD | Prepare remains unavailable to REVIEW_ONLY projects | PASS |
| AE | Execute remains unavailable | PASS |
| AF | No application code changed | PASS |
| AG | No migration occurred | PASS |
| AH | No production mutation occurred | PASS |
| AI | No deployment occurred | PASS |
| AJ | No PROJECT_SCAN was created | PASS |
| AK | Google AI Studio was not modified | PASS |

**Total: 37 / 37 PASS**

---

## 42. P2 DISPOSITION

**P2 DISPOSITION: PASS**

---

## 43. SOURCE DOCUMENTS

| Document | Path |
|----------|------|
| P2 Specification (this document) | `docs/productization/P2_CONNECTOR_PRODUCT_SPECIFICATION.md` |
| Productization Programme | `docs/productization/EVOSIA_PRODUCTIZATION_PROGRAMME.md` |
| P0 Evidence | `docs/productization/P0_PRODUCT_SURFACE_INVENTORY.md` |
| P1 Convergence | `docs/productization/P1_UX_CONVERGENCE.md` |
| Local Agent Certification | `validation/LOCAL_AGENT_PRODUCTION_CERTIFICATION.md` |

---

**STOP. No production mutations performed. No execution authority granted. No new programme started beyond P2.**
