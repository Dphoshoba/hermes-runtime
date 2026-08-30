# P3b — Windows Installer Foundation

**Date:** 2026-08-30
**P3b Baseline:** `42d5c19e167bcc4e49a6ba08d2563a8fbd35b7db`
**P3a Baseline (certified):** `794cd4067e8bd654d5816d10ba5de9e13ada1996`
**Connector Version:** 0.1.0
**EVOSIA Version:** 1.3.0
**Purpose:** Create the first real Windows installation shell around the certified EVOSIA Connector packaged runtime.

---

## 1. PURPOSE

Turn the P3a Windows Connector runtime bundle into a reproducible, installable and uninstallable Windows application package.

**Target customer experience:**

```
EVOSIA Connector installer
    ↓
Install
    ↓
EVOSIA Connector files placed in correct Windows application location
    ↓
Start Menu / application registration where appropriate
    ↓
Connector executable can launch
    ↓
Uninstall removes installed program cleanly
```

P3b establishes the installation shell only.

---

## 2. SCOPE

### In Scope

- Inno Setup installer configuration
- Installer build script
- Start Menu integration
- Add/Remove Programs registration
- Uninstall behavior
- Reinstall behavior
- Upgrade/downgrade readiness
- Running-process handling
- Installer security review
- Installer smoke tests
- Clean-Windows test plan
- P3b documentation

### Non-Goals

- Browser-assisted account pairing (P4)
- Customer project-folder authorization UX (P5)
- Tray/menu application (P6)
- Windows Credential Manager migration (P7)
- Automatic updater (P7)
- Cloud onboarding UI changes
- Frontend product UX changes
- Backend API changes
- Code-signing certificate purchase
- macOS packaging
- Linux packaging
- Public distribution publication

---

## 3. STARTING BASELINE

| Field | Value |
|-------|-------|
| HEAD | `42d5c19e167bcc4e49a6ba08d2563a8fbd35b7db` |
| Working tree | CLEAN |

---

## 4. INSTALLER TECHNOLOGY DECISION

### Decision: Inno Setup

**Chosen technology:** Inno Setup 6+

**Alternatives considered:**

| Technology | Pros | Cons | Decision |
|------------|------|------|----------|
| Inno Setup | Mature, free/open-source, excellent PyInstaller support, per-user install, Start Menu integration, uninstall support, code signing ready, small footprint, well-documented, CI automation via command-line compiler | Windows-only, no native MSI output | CHOSEN |
| WiX Toolset | MSI output, Group Policy deployment, enterprise integration | Complex authoring, steeper learning curve, MSI limitations with directory bundles | REJECTED |
| NSIS | Lightweight, scriptable | Older UI, less standard Windows integration, more manual work | REJECTED |
| MSIX | Modern Windows packaging, Store distribution | Requires AppxManifest, limited PyInstaller compatibility, more complex signing requirements | REJECTED |

**Rationale:**
- Best compatibility with PyInstaller directory bundles
- Per-user installation without admin privileges
- Built-in Start Menu and Add/Remove Programs integration
- Command-line compiler enables CI automation
- Active development and strong community
- Simple, declarative configuration (`.iss` file)
- Supports future code signing seamlessly

**Known limitations:**
- Windows-only (no cross-platform installer generation)
- No native MSI output (enterprise Group Policy deployment deferred)
- Unsigned builds trigger Windows SmartScreen warnings

**Future implications:**
- MSI output may be needed for enterprise deployment (separate future work)
- Code signing integration straightforward (SignTool directive in ISS file)

---

## 5. INSTALLATION SCOPE

### Decision: Per-User Installation

**Scope:** Per-user (no Administrator elevation required)

**Rationale:**
- EVOSIA Connector runs as a standard user process
- No system-wide services or drivers needed
- Follows principle of least privilege
- Standard users can install without IT support
- Credential storage is user-scoped (`%LOCALAPPDATA%`)

**Privilege model:**
- Installer runs with user privileges (`PrivilegesRequired=lowest`)
- Connector runtime does NOT run elevated
- Installation elevation, if needed, remains installation-scoped only
- Installer privilege is NOT EVOSIA project authority

---

## 6. TARGET WINDOWS INSTALL LOCATION

### Decision: `%LOCALAPPDATA%\Programs\EVOSIA Connector\`

```
%LOCALAPPDATA%\Programs\EVOSIA Connector\
├── evosia-connector.exe          # Entry point
├── _internal/                    # PyInstaller runtime
│   ├── *.dll, *.pyd              # Runtime libraries
│   ├── evosia_agent/             # Agent package
│   └── evosia_connector/         # Connector wrapper
└── BUILD_METADATA.json           # Build provenance
```

### Mutable State (separate from application)

```
%LOCALAPPDATA%\EVOSIA\Connector\
├── device.json                   # Device credential (interim; P7 migrates to keychain)
├── projects.json                 # Authorized projects
└── logs/
    └── connector.log             # Runtime logs
```

**Separation principle:**
- Application binaries: `%LOCALAPPDATA%\Programs\EVOSIA Connector\`
- Mutable state: `%LOCALAPPDATA%\EVOSIA\Connector\`
- Never stored inside customer project directories
- Never stored inside Downloads after installation

---

## 7. PRODUCT IDENTITY

| Field | Value |
|-------|-------|
| Product Name | EVOSIA Connector |
| Publisher | Echoes & Visions |
| Version | 0.1.0 |
| Architecture | Windows x64 |
| Channel | production |
| Install Channel | production |

**Publisher identity status:** UNSIGNED / DEVELOPMENT DISTRIBUTION

No real signing certificate exists yet. Publisher name reflects legitimate project ownership. Signing deferred to P7.

---

## 8. VERSIONING

| Component | Version | Notes |
|-----------|---------|-------|
| Connector product version | 0.1.0 | Customer-facing |
| Installer version | 0.1.0 | Matches Connector version |
| Runtime/agent version | 0.1.0 | Internal |
| EVOSIA platform version | 1.3.0 | Cloud backend |

**Version-upgrade semantics:**
- Inno Setup detects existing installation via AppId
- Same version: prompts for confirmation
- Higher version: upgrade in place (files replaced, state preserved)
- Lower version: blocked with user confirmation

---

## 9. ARCHITECTURE TARGET

| Property | Value |
|----------|-------|
| Primary target | Windows x64 |
| ARM64 support | NOT CLAIMED |
| Installer filename | `EVOSIA-Connector-0.1.0-windows-x64-production-setup.exe` |

---

## 10. INSTALLER CONTENT

### Packaged

- EVOSIA Connector executable (`evosia-connector.exe`)
- Packaged runtime dependencies (PyInstaller `_internal/`)
- Build/version metadata (`BUILD_METADATA.json`)
- Product icons/metadata (if legitimate assets exist)

### NOT Packaged

- Developer tests
- Repository source tree
- Git history
- Python source not required by PyInstaller bundle
- Test fixtures
- API secrets
- Developer `.env` files
- Device credentials
- Bootstrap tokens
- Project authorization tokens

---

## 11. BUILD PIPELINE

### Target Concept

```
build P3a runtime
    ↓
verify runtime artifact
    ↓
build Windows installer (Inno Setup)
    ↓
emit installer artifact
```

### Build Scripts

| Script | Purpose |
|--------|---------|
| `packaging/build_connector.py` | P3a runtime build |
| `packaging/windows/build_installer.py` | P3b installer build |
| `packaging/windows/evosia_connector.iss` | Inno Setup configuration |

### Build Command

```bash
python packaging/windows/build_installer.py
```

### Build Dependencies (engineering machine only)

- Inno Setup 6+ (`iscc.exe`)
- P3a runtime bundle (pre-built)

### Customer Runtime Dependencies

- NONE (all bundled with installer)

---

## 12. START MENU INTEGRATION

### Implementation

| Shortcut | Location | Description |
|----------|----------|-------------|
| EVOSIA Connector | Start Menu > EVOSIA Connector | Launch EVOSIA Connector |
| EVOSIA Connector Status | Start Menu > EVOSIA Connector | Show status |
| Uninstall EVOSIA Connector | Start Menu > EVOSIA Connector | Uninstall |

### Desktop Shortcut

**Default: NO** — Desktop shortcut is NOT created by default. Start Menu entry is sufficient for P3b.

---

## 13. ADD/REMOVE PROGRAMS REGISTRATION

### Registration

EVOSIA Connector appears in Windows Settings > Apps > Installed apps with:

| Field | Value |
|-------|-------|
| Product name | EVOSIA Connector |
| Version | 0.1.0 |
| Publisher | Echoes & Visions |
| Uninstall | Standard Windows uninstall |

---

## 14. UNINSTALL BEHAVIOR

### Removes

- Installed application binaries (`%LOCALAPPDATA%\Programs\EVOSIA Connector\`)
- Start Menu shortcuts
- Installer registration

### Preserves (conservative default)

- Device credential (`%LOCALAPPDATA%\EVOSIA\device.json`)
- Authorized project metadata (`%LOCALAPPDATA%\EVOSIA\Connector\projects.json`)
- Logs (`%LOCALAPPDATA%\EVOSIA\Connector\logs\`)

### Rationale for Preservation

- Uninstalling software should NOT silently destroy account/device trust records in EVOSIA Cloud
- Cloud revocation remains a separate authority action
- User can manually remove state if desired
- Reinstall re-pairs with existing credential if still valid

### Disclosure

Documentation clearly states what is preserved and how to manually clean up.

---

## 15. REINSTALL BEHAVIOR

### Same-Version Reinstall

- Detects existing installation
- Prompts for confirmation
- Files replaced in-place
- Existing credential preserved
- Authorized project records preserved
- No manual cleanup required

### After Uninstall + Reinstall

- New installation requires re-pairing
- Previous device entry remains in Cloud until explicitly revoked
- User can re-pair to restore connectivity

---

## 16. UPGRADE READINESS

### Detection

Inno Setup detects existing installation via AppId.

### Upgrade Behavior

| Scenario | Behavior |
|----------|----------|
| 0.1.0 → 0.1.1 | Files replaced, state preserved, no re-pairing needed |
| 0.1.x → 0.2.x | Files replaced, state preserved, check compatibility |

### State Preservation

- Device credential: PRESERVED
- Authorized projects: PRESERVED
- Logs: PRESERVED
- Application files: REPLACED

### Rollback Limitations

- Previous version is NOT retained after upgrade
- Rollback requires reinstall of previous version
- State format changes may require manual intervention

---

## 17. DOWNGRADE BEHAVIOR

### Policy: Block with Confirmation

When an older installer is run over a newer Connector:

- Installer detects version mismatch
- Prompts user for confirmation
- Warns that downgrade may cause compatibility issues
- Proceeds only if user explicitly confirms

---

## 18. RUNNING-PROCESS HANDLING

### Installer Behavior

1. Detects running `evosia-connector.exe` process
2. Prompts user: "EVOSIA Connector is currently running. Setup will close it to continue."
3. If user confirms: `taskkill /F /IM evosia-connector.exe`
4. Brief wait for process cleanup
5. Continues installation

### Uninstaller Behavior

1. Detects running `evosia-connector.exe` process
2. Prompts user: "EVOSIA Connector is currently running. Uninstall will close it."
3. If user confirms: terminates process
4. Continues uninstallation

### Safety

- Only terminates EVOSIA Connector processes (not unrelated processes)
- Does NOT introduce generic process-management authority
- User must confirm before process termination

---

## 19. RESTART BEHAVIOR

### Target: No Machine Restart Required

- Inno Setup file operations do not require restart under normal conditions
- If a restart is required (e.g., file in use), it is prompted explicitly
- No silent forced reboot

---

## 20. FILE PERMISSIONS

### Installed Application Files

- Per-user install means user-owned files
- No broadly writable directories
- Executable directory is user-owned (safe)

### Mutable State

- `device.json`: best-effort `0o600` permissions
- Logs: user-owned
- No secrets stored beside executable binaries

---

## 21. CREDENTIAL COMPATIBILITY

### Current State (preserved by P3b)

| File | Location | Format |
|------|----------|--------|
| `device.json` | `%LOCALAPPDATA%\EVOSIA\device.json` | `{device_id, device_name, credential, cloud_url}` |

### P3b Decision

**KEEP** current credential format and location.

**Rationale:**
- Existing paired engineering devices remain valid
- P2's Windows Credential Manager / DPAPI migration scheduled for P7
- No installer-critical need to change format

**Installer behavior:**
- Does NOT overwrite valid existing credential during upgrade/reinstall
- Does NOT delete credential during uninstall (preserves by default)

---

## 22. LOG COMPATIBILITY

### Log Location

```
%LOCALAPPDATA%\EVOSIA\Connector\logs\connector.log
```

### Installer Behavior

- Logs NOT stored inside install directory
- Logs NOT stored inside customer project
- Logs remain in dedicated EVOSIA state directory
- Uninstall preserves logs by default

---

## 23. PRODUCTION CONFIGURATION

### Compatibility

Installed runtime retains P3a production-safe Cloud endpoint:

| Property | Value |
|----------|-------|
| Production Cloud URL | `https://evosia-cloud.fly.dev` |
| Build channel | `production` |
| Env var override | Ignored in production builds |

### Installer Behavior

- Does NOT introduce localhost default
- Does NOT introduce developer endpoint default
- Does NOT embed secrets
- Does NOT add installer text box for Cloud URL

---

## 24. SECURITY REVIEW

### Findings

| Threat | Severity | Mitigation | Status |
|--------|----------|------------|--------|
| Installer tampering | MEDIUM | Code signing (deferred to P7) | ACCEPTED (development) |
| Unsigned installer warning | MEDIUM | SmartScreen disclosure | DOCUMENTED |
| DLL search path | LOW | Per-user install, user-owned directory | MITIGATED |
| Writable installation directory | LOW | Per-user install (user-owned) | MITIGATED |
| Malicious pre-existing files | LOW | Clean install location | MITIGATED |
| Path injection | LOW | Standard Inno Setup path handling | MITIGATED |
| Environment/PATH hijacking | LOW | No PATH modification | MITIGATED |
| Unsafe temp extraction | LOW | Inno Setup temp handling | MITIGATED |
| Command-line injection in installer | LOW | No user input in ISS script commands | MITIGATED |
| Privilege escalation | LOW | Per-user install, no admin required | MITIGATED |
| Uninstall abuse | LOW | Standard uninstall, user-initiated | MITIGATED |
| Credential deletion risk | MEDIUM | Uninstall preserves credentials by default | MITIGATED |
| Accidental secret packaging | LOW | No secrets in installer config | MITIGATED |

### Unresolved Deferred Risks

1. Code signing for trusted distribution (P7)
2. SmartScreen warnings for unsigned builds (P7)
3. OS keychain credential storage (P7)

---

## 25. SIGNING READINESS

### Current Artifact Status

**DEVELOPMENT / UNSIGNED**

No real signing certificate exists. Build artifact is unsigned.

### Future Signing Points

| Signing Point | When | Requirement |
|---------------|------|-------------|
| Executable signing | P7 | Code signing certificate |
| Installer signing | P7 | Code signing certificate |
| Timestamping | P7 | Timestamp server |
| Release verification | P7 | Checksum/signature publication |

### Architecture Readiness

Inno Setup supports SignTool directive for future signing:

```
SignTool=sign /f certificate.pfx /p password /t timestamp /fd sha256
```

No architectural changes needed for signing integration.

---

## 26. SMARTSCREEN EXPECTATION

### Expectation

Unsigned development installers WILL trigger Windows SmartScreen warnings:

- "Windows protected your PC" dialog
- "Unknown publisher" warning
- User must click "More info" → "Run anyway"

### Policy

- Do NOT attempt to bypass SmartScreen
- Do NOT instruct users to disable Windows security
- Public distribution remains blocked until trust/signing requirements are satisfied
- P3b is engineering/development certification, not public distribution

---

## 27. SMOKE TESTS

### Test File

`tests/test_p3b_installer.py`

### Coverage

| Test | Verifies |
|------|----------|
| ISS file exists | Installer configuration present |
| Build script exists | Build automation present |
| Product name correct | "EVOSIA Connector" in ISS |
| Version correct | "0.1.0" in ISS |
| Publisher defined | "Echoes & Visions" in ISS |
| Per-user install | `PrivilegesRequired=lowest` |
| No admin for runtime | Runtime not elevated |
| Correct install location | `localappdata\Programs` |
| Start Menu shortcut | `{group}` entries present |
| Uninstall configured | Uninstall metadata present |
| x64 targeted | `x64compatible` present |
| Running process handled | `taskkill` in Code section |
| LZMA compression | `SolidCompression=yes` |
| No desktop shortcut default | No `{autodesktop}` |
| Runtime artifact exists | P3a bundle present |
| Runtime has executable | Entry point found |
| No test files in runtime | Clean bundle |
| No source tree in runtime | No `.git` |
| No dev files in runtime | No `.env`, `pyproject.toml` |
| No embedded tokens | No `bearer`, `api_key` |
| No API keys | No `sk-`, `pk-` |
| Build script valid | Has `main`, version, runtime check |

### Results

- **Pass count:** 28
- **Skip count:** 3 (installer output tests — installer not built on macOS)
- **Fail count:** 0

---

## 28. CLEAN WINDOWS TEST PLAN

### Prerequisites

- Fresh Windows 10/11 machine (or VM)
- No Python installed
- No Git installed
- No source checkout
- No developer tools

### Test Steps

| Step | Action | Expected |
|------|--------|----------|
| 1 | Run `EVOSIA-Connector-0.1.0-windows-x64-production-setup.exe` | Installer launches |
| 2 | Accept defaults | Per-user install location shown |
| 3 | Click Install | Files installed to `%LOCALAPPDATA%\Programs\EVOSIA Connector\` |
| 4 | Check Start Menu | "EVOSIA Connector" shortcut present |
| 5 | Launch EVOSIA Connector | Executable starts |
| 6 | Check Add/Remove Programs | "EVOSIA Connector" listed |
| 7 | Uninstall | Clean removal of application files |
| 8 | Check Start Menu | Shortcuts removed |
| 9 | Check Add/Remove Programs | Entry removed |
| 10 | Check credential preserved | `device.json` still exists (if previously paired) |

### Status

**NOT TESTED ON WINDOWS** — P3b provides configuration and test plan; actual Windows execution requires Windows environment.

---

## 29. KNOWN LIMITATIONS

| Limitation | Impact | Resolution |
|-----------|--------|------------|
| No real Windows install test | Cannot verify actual installation | P3c or manual Windows testing |
| Unsigned installer | SmartScreen warnings | P7: code signing |
| No tray UI yet | No background status display | P6 |
| No OS keychain yet | Credentials in plaintext file | P7 |
| No auto-updater yet | Manual updates required | P7 |
| No browser-assisted pairing yet | Bootstrap token paste required | P4 |
| No folder picker yet | CLI project registration | P5 |
| macOS/Linux packaging deferred | Windows only for now | FUTURE |

---

## 30. P3c INPUTS

P3b provides the following to P3c:

| Input | P3b Section | P3c Use |
|-------|-----------|---------|
| Inno Setup configuration | Section 4 | P3c may refine installer UX |
| Installer build script | Section 11 | P3c integrates into CI/CD |
| Start Menu integration | Section 12 | P3c may add tray integration |
| Uninstall behavior | Section 14 | P3c may add credential cleanup |
| Security review | Section 24 | P3c addresses deferred risks |
| Clean-Windows test plan | Section 28 | P3c executes on Windows |

---

## 31. ACCEPTANCE GATES

| Gate | Description | Status |
|------|-------------|--------|
| A | canonical P3a baseline verified | PASS |
| B | one installer technology selected | PASS |
| C | installer technology decision documented | PASS |
| D | install scope decided | PASS |
| E | privilege model follows least privilege | PASS |
| F | Connector runtime does not run elevated by default | PASS |
| G | deterministic install location defined | PASS |
| H | installer consumes certified P3a runtime bundle | PASS |
| I | customer does not require Python | PASS |
| J | customer does not require Git | PASS |
| K | customer does not require repository checkout | PASS |
| L | installer version = Connector version | PASS |
| M | Windows x64 target identified honestly | PASS |
| N | reproducible installer build configuration exists | PASS |
| O | installer artifact builds successfully OR environment limitation explicitly recorded | PASS (macOS limitation recorded) |
| P | product metadata is defined | PASS |
| Q | Start Menu behavior is defined/implemented | PASS |
| R | installed-app/uninstall registration defined/implemented | PASS |
| S | uninstall behavior defined | PASS |
| T | reinstall behavior defined | PASS |
| U | upgrade readiness defined | PASS |
| V | downgrade behavior defined | PASS |
| W | running-process handling defined | PASS |
| X | restart behavior defined | PASS |
| Y | credential compatibility preserved | PASS |
| Z | logs remain outside project/install directory | PASS |
| AA | production Cloud configuration remains safe | PASS |
| AB | no localhost fallback introduced | PASS |
| AC | focused installer security review completed | PASS |
| AD | signing readiness documented | PASS |
| AE | unsigned development status disclosed honestly | PASS |
| AF | SmartScreen bypass not implemented | PASS |
| AG | clean-Windows validation procedure documented | PASS |
| AH | P3a smoke tests still pass | PASS (23/23) |
| AI | authority regression still passes | PASS (14/14) |
| AJ | REVIEW_ONLY preserved | PASS |
| AK | ALLOWED_OPERATION_TYPES remains exactly PROJECT_SCAN | PASS |
| AL | Prepare remains unavailable | PASS |
| AM | Execute remains unavailable | PASS |
| AN | arbitrary shell capability not added | PASS |
| AO | autonomous scan capability not added | PASS |
| AP | autonomous project authorization not added | PASS |
| AQ | no production PROJECT_SCAN created | PASS |
| AR | no production DB mutation | PASS |
| AS | no migration | PASS |
| AT | no deployment | PASS |
| AU | Google AI Studio unchanged | PASS |
| AV | no frontend product UX implementation started | PASS |
| AW | no backend authority expansion | PASS |
| AX | no new regressions | PASS |
| AY | P3b documentation complete | PASS |
| AZ | programme status updated appropriately | PASS |

**Total: 52 / 52 PASS**

---

## 32. P3b DISPOSITION

**P3b DISPOSITION: PASS**

---

## 33. SOURCE DOCUMENTS

| Document | Path |
|----------|------|
| P3b Documentation (this document) | `docs/productization/P3B_WINDOWS_INSTALLER_FOUNDATION.md` |
| P3a Documentation | `docs/productization/P3A_CONNECTOR_PACKAGING_FOUNDATION.md` |
| P2 Specification | `docs/productization/P2_CONNECTOR_PRODUCT_SPECIFICATION.md` |
| Productization Programme | `docs/productization/EVOSIA_PRODUCTIZATION_PROGRAMME.md` |
| Inno Setup Configuration | `packaging/windows/evosia_connector.iss` |
| Installer Build Script | `packaging/windows/build_installer.py` |
| Installer Tests | `tests/test_p3b_installer.py` |

---

**STOP. No production mutations performed. No execution authority granted. No new programme started beyond P3b.**
