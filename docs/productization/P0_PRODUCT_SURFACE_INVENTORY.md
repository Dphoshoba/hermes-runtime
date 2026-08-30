# P0 — Canonical Baseline & Product Surface Inventory

**Date:** 2026-08-30
**Baseline:** `313aaed12985a23aca494ecd41093c1e52b36612`
**EVOSIA Version:** 1.3.0
**Purpose:** Answer "What exactly do we have today, what does a user currently experience, and what must be productized?"

---

## 1. CERTIFIED BASELINE

### Repository State

| Field | Value |
|-------|-------|
| HEAD | `313aaed12985a23aca494ecd41093c1e52b36612` |
| origin/main | `313aaed12985a23aca494ecd41093c1e52b36612` |
| HEAD == origin/main | YES |
| Working tree | CLEAN |

### Governing Evidence

| Document | Status |
|----------|--------|
| `validation/LOCAL_AGENT_PRODUCTION_CERTIFICATION.md` | READ — LA0–LA6 COMPLETE |
| `validation/PROGRAMME_STATUS_RECONCILIATION.md` | READ — All tracks reconciled |
| `validation/FINAL_ENGINEERING_CERTIFICATION.md` | READ — Engineering certified |

### Authority Freeze

| Constraint | Value |
|------------|-------|
| DeviceProject authority | `REVIEW_ONLY` |
| ALLOWED_OPERATION_TYPES | `frozenset({"PROJECT_SCAN"})` |
| Execution authority | NOT GRANTED |
| Merge authority | NOT GRANTED |
| Deployment authority | NOT GRANTED |
| Autonomous job creation | NOT GRANTED |

---

## 2. CURRENTLY VERIFIED

The following have been directly verified through production evidence and certification:

| Capability | Verification Source |
|------------|-------------------|
| Device registration and bootstrap token exchange | LA1 certification, production evidence |
| Device credential (JWT) issuance and storage | LA2 certification, `device.json` with `0o600` permissions |
| Device heartbeat with retry/backoff | LA2 certification, 60s interval, 5s→60s backoff |
| Device revocation | LA1 certification, backend guard verified |
| Explicit human project authorization | LA3 certification, one-time tokens |
| Canonical path fingerprinting (SHA-256) | LA3 certification, raw paths remain local |
| Symlink escape protection | LA3 certification, `has_symlink_escape()` |
| Sensitive file classification | LA3 certification, 13 patterns blocked |
| Governed PROJECT_SCAN execution | LA4 certification, bounded scanner |
| Scanner limits (1MB/file, 10MB total, 5000 files, 120s) | LA4 certification, enforced |
| `shell=False` subprocess safety | LA4 certification, hardcoded git allowlist |
| `LIVE_EVOSIA_EVIDENCE` provenance | LA4 certification, enforced |
| Computers UI with device state | LA5 certification, online/offline/revoked |
| Project authorization in UI | LA5 certification, token generation |
| Review project button and lifecycle | LA6 certification, full lifecycle verified |
| Review history display | LA5 certification |
| Truncation disclosure | LA6 certification, "Review completed with limits" |
| Active-job backend guard (HTTP 409) | LA6 certification |
| Frontend double-click protection | LA6 certification, `useRef` guards |
| Source-tree immutability | LA6 certification, `git status --porcelain` clean |

---

## 3. CURRENTLY IMPLEMENTED BUT NOT PRODUCTIZED

The following exist in the codebase but require productization for non-technical use:

| Component | Current State | Productization Needed |
|-----------|--------------|----------------------|
| **Agent installation** | `pip install` or `python -m evosia_agent` | Native installer, no Python required |
| **Agent startup** | `python -m evosia_agent` in terminal | Automatic background startup |
| **Bootstrap token exchange** | Paste token into terminal | In-app pairing flow |
| **Project authorization** | CLI: `python -m evosia_agent project add <path> --authorization-token <token>` | Native folder picker, in-app authorization |
| **Credential storage** | `device.json` with `0o600` (best-effort on Windows) | OS keychain integration |
| **Connection status** | Terminal output | Visual status in app |
| **Error messages** | Python tracebacks / log output | Friendly error UI |
| **Update mechanism** | Manual `pip install --upgrade` | Automatic update check |
| **Uninstall** | Manual `pip uninstall` | Standard Windows uninstaller |
| **Environment variable** | `EVOSIA_CLOUD_URL` for cloud URL | Pre-configured, no user action |
| **Python runtime** | Requires Python 3.x installed | Bundled runtime |
| **pip/virtualenv** | Requires pip, optional venv | Not required |
| **Git** | Optional, for git metadata extraction | Not required from user |
| **Onboarding** | No guided first-run for Connector | First-run wizard |
| **Background operation** | Agent runs in foreground terminal | System tray / service |

---

## 4. CURRENT CUSTOMER JOURNEY

### Actual Steps TODAY for a Brand-New Windows User

| Step | Human Action | Classification |
|------|-------------|---------------|
| 1 | Have an EVOSIA account with a project already in the cloud | CUSTOMER-READY |
| 2 | Open EVOSIA Computers page in browser | CUSTOMER-READY |
| 3 | Click "Add computer" | CUSTOMER-READY |
| 4 | Enter computer name, select platform, click "Generate code" | CUSTOMER-READY |
| 5 | Copy the bootstrap token displayed | NEEDS PRODUCTIZATION |
| 6 | Install Python on Windows (python.org or Microsoft Store) | DEVELOPER-ONLY |
| 7 | Open PowerShell or Command Prompt | DEVELOPER-ONLY |
| 8 | Run `pip install evosia-agent` or clone repository | DEVELOPER-ONLY |
| 9 | Run `python -m evosia_agent` | DEVELOPER-ONLY |
| 10 | Paste bootstrap token when prompted | DEVELOPER-ONLY |
| 11 | Agent connects, appears online in Computers page | CUSTOMER-READY (after steps 6–10) |
| 12 | In Cloud UI, click "Authorise project" for the device | CUSTOMER-READY |
| 13 | Copy the project authorization token | NEEDS PRODUCTIZATION |
| 14 | In terminal, run `python -m evosia_agent project add <path> --authorization-token <token>` | DEVELOPER-ONLY |
| 15 | Navigate to project folder in terminal (know absolute path) | DEVELOPER-ONLY |
| 16 | Project appears in Computers page with "Review project" button | CUSTOMER-READY |
| 17 | Click "Review project" | CUSTOMER-READY |
| 18 | See: Review queued → Review in progress → Review complete → Project unchanged | CUSTOMER-READY |
| 19 | See review results/findings | CUSTOMER-READY |

### Step Classification Summary

| Classification | Count |
|---------------|-------|
| CUSTOMER-READY | 9 |
| NEEDS PRODUCTIZATION | 2 |
| DEVELOPER-ONLY | 8 |
| **TOTAL** | **19** |

### Developer-Only Steps Detail

| Step | Why Developer-Only |
|------|-------------------|
| 6 | Requires Python installation knowledge |
| 7 | Requires terminal/PowerShell knowledge |
| 8 | Requires pip/repository cloning knowledge |
| 9 | Requires Python execution knowledge |
| 10 | Requires terminal interaction knowledge |
| 14 | Requires CLI syntax, path knowledge, token handling |
| 15 | Requires filesystem navigation knowledge |

---

## 5. REUSABLE CERTIFIED CONTRACTS

### DEVICE Contracts

| Contract | Endpoint/Method | Classification |
|----------|----------------|---------------|
| Bootstrap issuance | `POST /api/devices/register` → bootstrap token | REUSE AS-IS |
| Registration/exchange | `POST /api/devices/exchange` → device JWT | REUSE AS-IS |
| Device credential storage | `device.json` with `0o600` | WRAP FOR PRODUCT UX |
| Heartbeat | `POST /api/agent/heartbeat` with pending jobs | REUSE AS-IS |
| Online/offline status | `last_seen_at` timestamp, 60s threshold | REUSE AS-IS |
| Revocation | `POST /api/devices/{id}/revoke` | REUSE AS-IS |

### PROJECT Contracts

| Contract | Endpoint/Method | Classification |
|----------|----------------|---------------|
| Project authorization token creation | `POST /api/devices/{id}/project-auth-token` | REUSE AS-IS |
| DeviceProject registration | `POST /api/device-projects/` | REUSE AS-IS |
| Local-root fingerprint | SHA-256 of canonical POSIX path | REUSE AS-IS |
| Local project registry | `projects.json` with `0o600` | WRAP FOR PRODUCT UX |
| REVIEW_ONLY authority | Hardcoded in `device_project_service.py` | REUSE AS-IS |

### WORK Contracts

| Contract | Endpoint/Method | Classification |
|----------|----------------|---------------|
| Human PROJECT_SCAN request | `POST /api/device-projects/{id}/scans` | REUSE AS-IS |
| Active-job guard | HTTP 409 when scan already active | REUSE AS-IS |
| Job polling | Heartbeat `pending_jobs` + `GET /api/agent/jobs/{id}` | REUSE AS-IS |
| Job retrieval | `GET /api/agent/jobs/next` | REUSE AS-IS |
| Started transition | `POST /api/agent/jobs/{id}/started` | REUSE AS-IS |
| Result submission | `POST /api/agent/jobs/{id}/results` | REUSE AS-IS |
| Completed/failed states | `completed_at`, `failed_at` timestamps | REUSE AS-IS |

### EVIDENCE Contracts

| Contract | Implementation | Classification |
|----------|---------------|---------------|
| Provenance | `LIVE_EVOSIA_EVIDENCE` literal | REUSE AS-IS |
| Truncation | `truncated` boolean + limits dict | REUSE AS-IS |
| Bounded scan | 1MB/file, 10MB total, 5000 files, 120s | REUSE AS-IS |
| Project unchanged | `git status --porcelain` clean | REUSE AS-IS |
| Failure reporting | `failure_reason` string | REUSE AS-IS |
| Findings | Type-classified dict (SYMLINK_ESCAPE, SENSITIVE_FILE, etc.) | REUSE AS-IS |

---

## 6. PLATFORM ASSUMPTIONS

### Windows

| Assumption | Current Implementation |
|------------|----------------------|
| Credential path | `%LOCALAPPDATA%\EVOSIA\device.json` |
| Project registry | `%LOCALAPPDATA%\EVOSIA\projects.json` |
| File permissions | Best-effort `chmod` (warning logged if fails) |
| Process lifecycle | Foreground terminal process |
| Startup behavior | Manual `python -m evosia_agent` |
| Python dependency | Requires Python 3.x installed |
| Package installation | `pip install` or repository clone |
| Environment variables | `EVOSIA_CLOUD_URL` (optional) |
| Executable assumption | `python -m evosia_agent` |
| Permissions | Standard user (no admin required for agent) |
| Project selection | Absolute path via CLI argument |

### macOS

| Assumption | Current Implementation |
|------------|----------------------|
| Credential path | `~/Library/Application Support/EVOSIA/device.json` |
| Project registry | `~/Library/Application Support/EVOSIA/projects.json` |
| File permissions | `0o600` enforced via `chmod` |
| Process lifecycle | Foreground terminal process |
| Startup behavior | Manual `python -m evosia_agent` |
| Python dependency | Requires Python 3.x installed |
| Package installation | `pip install` or repository clone |
| Environment variables | `EVOSIA_CLOUD_URL` (optional) |
| Executable assumption | `python -m evosia_agent` |
| Permissions | Standard user |
| Project selection | Absolute path via CLI argument |

### Linux

| Assumption | Current Implementation |
|------------|----------------------|
| Credential path | `~/.local/share/EVOSIA/device.json` |
| Project registry | `~/.local/share/EVOSIA/projects.json` |
| File permissions | `0o600` enforced via `chmod` |
| Process lifecycle | Foreground terminal process |
| Startup behavior | Manual `python -m evosia_agent` |
| Python dependency | Requires Python 3.x installed |
| Package installation | `pip install` or repository clone |
| Environment variables | `EVOSIA_CLOUD_URL` (optional) |
| Executable assumption | `python -m evosia_agent` |
| Permissions | Standard user |
| Project selection | Absolute path via CLI argument |

### Cross-Platform Notes

| Note | Detail |
|------|--------|
| HTTP client | `urllib.request` (stdlib, no third-party deps) |
| TLS | Enabled (default `urlopen` behavior) |
| JSON parsing | `json` (stdlib) |
| Subprocess | `subprocess.run` with `shell=False` (git metadata only) |
| Encoding | UTF-8 with `errors="replace"` for file reads |

---

## 7. GOOGLE AI STUDIO INPUTS

### Prompt Review

| Field | Value |
|-------|-------|
| File | `docs/google-ai-studio/EVOSIA_GOOGLE_AI_STUDIO_BUILD_PROMPT.md` |
| Lines | 546 |
| Sections | 13 numbered sections + repository evidence appendix |
| Reviewed | YES |

### Concept Inventory

#### PRESENT IN PRODUCTION

| Concept | Production Implementation |
|---------|--------------------------|
| Guided Mode | `GuidedModePage.tsx` (974 lines), `guided.py` router (20 endpoints) |
| First-run onboarding | `FirstRunOnboarding.tsx` (6-step wizard) |
| Needs Attention | `NeedsAttentionView` with severity/category badges |
| Needs Context | `ContextQuestion` cards with answer options |
| Proposed Work / Mission Decision | `MissionDecisionView` with What/Why/Benefit/Risk/Scope |
| Prepared Change Review | `PreparedChangeView` with diff, validation, rollback |
| Safety badge ("0 changes made") | Persistent badge in Guided Mode header |
| Authority level display | Authority badge in header |
| Demo/Live toggle | `DemoModeToggle` component |
| Provenance display | `ProvenanceBadge` component |
| Login/session | JWT auth, `AuthContext`, `ProtectedRoute` |
| Dashboard | `DashboardPage.tsx` with stats, activity, overnight summary |
| Findings | `FindingsPage.tsx` with severity filter |
| Journal | `JournalPage.tsx` with event type filter |
| Human Review | `HumanReviewPage.tsx` with adjudication interface |
| Repositories | `RepositoriesPage.tsx` with sync/scan actions |
| Scans | `ScansPage.tsx` with cancel/retry |
| Missions | `MissionsPage.tsx` |
| Reports | `ReportsPage.tsx` |
| Computers | `DevicesPage.tsx` with device lifecycle |

#### PARTIALLY PRESENT

| Concept | Current State | Gap |
|---------|--------------|-----|
| Non-technical primary user | Guided Mode targets this audience | Installation still requires developer knowledge |
| Project selection | Guided Mode has project selection component | No native folder picker — requires CLI project registration |
| Conversational intelligence (Gemini) | `/api/guided/explain/*` endpoints exist | Not integrated as chat interface, only on-demand explanations |
| Expert/technical views | Separate pages exist (Findings, Journal, etc.) | Not structured as "progressive disclosure" from Guided Mode |
| Authority consequence statement | Present in MissionDecisionView | Could be more prominent for non-technical users |

#### ABSENT

| Concept | Status |
|---------|--------|
| Native installer / Connector | Not implemented |
| Automatic background startup | Not implemented |
| Native folder picker | Not implemented |
| In-app pairing flow | Not implemented (requires terminal) |
| Connection status visual | Only in Cloud UI, not in Connector |
| Update mechanism | Not implemented |
| Uninstall mechanism | Not implemented |
| OS keychain integration | Not implemented |
| System tray integration | Not implemented |
| First-run wizard for Connector | Not implemented |
| Chat/conversation interface | Only API endpoints, no UI |

#### REQUIRES VISUAL P1 COMPARISON

| Concept | Reason |
|---------|--------|
| Google AI Studio generated app visual design | Must be visually examined during P1 |
| Dark theme color palette alignment | Prompt specifies exact colors — verify against generated app |
| Typography and spacing | Prompt specifies "premium, calm, trustworthy" — verify |
| Badge system visual states | Prompt specifies DRAFT/APPROVED/PREPARED colors — verify |
| Card component styling | Prompt specifies elevated cards, subtle borders — verify |

---

## 8. PRODUCTIZATION GAPS

### Priority 1 — Installation & Packaging

| Gap | Impact | Current State |
|-----|--------|--------------|
| No native installer | Blocks non-technical users entirely | Requires Python, pip, terminal |
| No bundled Python runtime | Requires user to install Python | User must know Python |
| No Windows MSI/EXE packaging | No standard Windows install experience | pip/repository only |
| No automatic startup | Agent stops when terminal closes | Foreground process |
| No system tray icon | No visual indicator of agent running | Terminal output only |

### Priority 2 — Account & Device Pairing

| Gap | Impact | Current State |
|-----|--------|--------------|
| Bootstrap token paste into terminal | Requires terminal interaction | Token shown in UI, pasted in CLI |
| No in-app pairing flow | Requires copy-paste across browser/terminal | Manual process |
| No connection status in Connector | User doesn't know if connected | Only visible in Cloud UI |
| No re-pairing after revocation | User must repeat full terminal process | Manual re-registration |

### Priority 3 — Project Authorization

| Gap | Impact | Current State |
|-----|--------|--------------|
| No native folder picker | Requires knowing absolute path | CLI argument |
| Project auth token paste into terminal | Requires terminal interaction | Token shown in UI, pasted in CLI |
| No authorization explanation in Connector | User doesn't understand "Review only" | Only in Cloud UI |
| No project list management in Connector | Must use Cloud UI or terminal | CLI `projects` command |

### Priority 4 — Onboarding & UX

| Gap | Impact | Current State |
|-----|--------|--------------|
| No Connector first-run wizard | User dropped into terminal | No guided experience |
| No error recovery guidance | Python tracebacks | Log output only |
| No update notifications | User must manually check | No update mechanism |
| No uninstall mechanism | Manual pip uninstall | No standard removal |

### Priority 5 — Background Operation

| Gap | Impact | Current State |
|-----|--------|--------------|
| No Windows service integration | Agent doesn't start with Windows | Manual startup |
| No heartbeat visualization | User can't see agent is alive | Cloud UI shows last seen |
| No automatic reconnection | Agent stops on error, requires manual restart | Retry/backoff exists but process dies |

### Priority 6 — Security & Credential Management

| Gap | Impact | Current State |
|-----|--------|--------------|
| No OS keychain integration | Credentials in JSON file | Best-effort file permissions |
| No credential rotation | 30-day JWT expiry, no auto-renewal | Manual re-registration |
| Windows file permissions best-effort | Warning logged, not enforced | `chmod` may fail on Windows |

---

## 9. TARGET CUSTOMER JOURNEY

### Ideal Product Journey (16 Steps)

| Step | User Action | System Response |
|------|------------|----------------|
| 1 | User signs into EVOSIA | Login page, authentication |
| 2 | User opens Computers | Device list displayed |
| 3 | User clicks "Add computer" | Dialog opens |
| 4 | User clicks "Download EVOSIA Connector for Windows" | Installer downloads |
| 5 | User runs the installer | Standard Windows installer wizard |
| 6 | Connector securely pairs with EVOSIA account | Automatic pairing (no terminal) |
| 7 | EVOSIA shows "Computer connected" | Status updated in UI |
| 8 | User clicks "Choose project folder" | Native Windows folder picker opens |
| 9 | User selects the folder | Folder selected |
| 10 | EVOSIA explains: "Review only — EVOSIA may inspect this project when you request a review. EVOSIA cannot edit, execute, merge or deploy it." | Clear disclosure displayed |
| 11 | User authorizes the project | Authorization confirmed |
| 12 | Project appears in Computers | Project listed with status |
| 13 | User clicks "Review project" | Review lifecycle begins |
| 14 | User sees: Review queued → Review in progress → Review complete → Project unchanged | Status updates displayed |
| 15 | User sees useful review results/findings | Findings presented clearly |
| 16 | User understands EVOSIA has NOT changed their project | Authority comprehension verified |

### CURRENT vs TARGET Separation

| Aspect | CURRENT | TARGET |
|--------|---------|--------|
| Installation | Python + pip + terminal | Native installer |
| Pairing | Paste bootstrap token in terminal | In-app pairing |
| Project authorization | CLI with path and token | Native folder picker |
| Background operation | Foreground terminal | System tray / service |
| Status visibility | Cloud UI only | Connector + Cloud UI |
| Error handling | Python tracebacks | Friendly error UI |
| Updates | Manual pip upgrade | Automatic update check |
| Uninstall | Manual pip uninstall | Standard Windows uninstall |

**Do not conflate CURRENT with TARGET. Current behaviour is documented above. Target behaviour is documented here. They are separate.**

---

## 10. AUTHORITY BOUNDARY

### Certified Authority State

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

### Productization Does NOT Authorize

- Arbitrary command execution
- Autonomous coding
- Project file editing
- Merge
- Deployment
- Preparation authority
- Autonomous PROJECT_SCAN creation
- Any capability beyond REVIEW_ONLY governed scan

### Authority Expansion Protocol

If a future requirement appears to need additional authority:

1. DOCUMENT the requirement
2. DOCUMENT the proposed authority expansion
3. DO NOT IMPLEMENT until a separate programme authorizes it

---

## 11. P0 DISPOSITION

| Field | Status |
|-------|--------|
| Certified baseline verified | YES |
| Authority freeze verified | YES |
| Product surface inventoried | YES — 12 routes, 89 API endpoints, 19 router modules |
| Current Windows journey mapped | YES — 19 steps, 8 developer-only, 2 needs-productization |
| Reusable contracts classified | YES — 20 contracts (16 REUSE AS-IS, 4 WRAP FOR PRODUCT UX) |
| Platform assumptions documented | YES — Windows, macOS, Linux |
| Google AI Studio prompt reviewed | YES — 546 lines, 13 sections |
| AI Studio concepts classified | YES — 20 present, 5 partially present, 12 absent, 5 require P1 visual comparison |
| Productization gaps identified | YES — 6 priority categories, 22 specific gaps |
| Target customer journey documented | YES — 16 steps |
| Current vs target clearly separated | YES |
| Programme P0–P8 defined | YES — 9 milestones with objectives, gates, evidence |
| Authority boundary preserved | YES |
| Documentation only | YES — no code changes |

### P0 STATUS: PASS

---

## 12. SOURCE DOCUMENTS

| Document | Path |
|----------|------|
| Productization Programme | `docs/productization/EVOSIA_PRODUCTIZATION_PROGRAMME.md` |
| P0 Evidence (this document) | `docs/productization/P0_PRODUCT_SURFACE_INVENTORY.md` |
| Local Agent Certification | `validation/LOCAL_AGENT_PRODUCTION_CERTIFICATION.md` |
| Programme Reconciliation | `validation/PROGRAMME_STATUS_RECONCILIATION.md` |
| Final Engineering Certification | `validation/FINAL_ENGINEERING_CERTIFICATION.md` |
| Google AI Studio Build Prompt | `docs/google-ai-studio/EVOSIA_GOOGLE_AI_STUDIO_BUILD_PROMPT.md` |

---

**STOP. No production mutations performed. No execution authority granted. No new programme started beyond P0.**
