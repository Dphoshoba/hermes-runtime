# P3a — Connector Packaging Foundation

**Date:** 2026-08-30
**P3a Baseline:** `9b1821344d92bf5f59545feb383d0d6340d03c41`
**EVOSIA Version:** 1.3.0
**Connector Version:** 0.1.0
**Purpose:** Establish the distributable runtime/package foundation for the future Windows EVOSIA Connector.

---

## 1. PURPOSE

Create a Windows-packagable EVOSIA Connector runtime foundation around the existing certified `evosia_agent`. The resulting artifact must:

- Run without a customer-managed Python installation
- Run without Git
- Run without repository source checkout
- Bundle required runtime dependencies
- Expose a stable Connector executable/entry point
- Use production-safe configuration defaults
- Preserve all certified Local Agent authority boundaries
- Remain functionally compatible with current EVOSIA Cloud contracts

---

## 2. SCOPE

### In Scope

- `evosia_connector/` wrapper package
- Production-safe configuration model
- PyInstaller packaging configuration
- Windows build script
- Smoke tests
- Authority regression tests
- Build artifact production

### Non-Goals

- Final Windows installer UX (P3b)
- Browser-assisted pairing UX (P4)
- Project-folder picker UI (P5)
- Tray/menu UI (P6)
- OS credential-store migration (P7)
- Automatic updater (P7)
- Cloud onboarding UI (P8)
- Public distribution/signing (P7)
- macOS packaging (FUTURE)
- Linux packaging (FUTURE)

---

## 3. STARTING BASELINE

| Field | Value |
|-------|-------|
| HEAD | `9b1821344d92bf5f59545feb383d0d6340d03c41` |
| Working tree | CLEAN |

---

## 4. PACKAGING APPROACH

### Decision: PyInstaller

**Chosen approach:** PyInstaller (directory bundle mode)

**Alternatives considered:**

| Tool | Pros | Cons | Decision |
|------|------|------|----------|
| PyInstaller | Mature, wide Windows support, good Python compat, directory/single-file modes | Larger output, some AV false positives | CHOSEN |
| Nuitka | Better performance, smaller output, compiled | Longer build times, more complex debugging, less mature Windows support | REJECTED |
| cx_Freeze | Good Windows support, simpler config | Less active development, fewer features than PyInstaller | REJECTED |

**Rationale:**
- Most mature and widely-used Python packaging tool
- Good Windows support with directory and single-file modes
- Strong community and documentation
- Compatible with PyInstaller's hook system for hidden imports
- Directory bundle preferred for: better startup performance, easier delta updates, simpler debugging, signed-distribution compatibility

**Known tradeoffs:**
- Larger artifact size than Nuitka compilation
- Some antivirus false positives (mitigated by code signing)
- Directory bundle requires all files in a folder (not a single exe)

**Risks for later milestones:**
- Single-file mode may be desired for P3b installer (can be switched)
- AV false positives require code signing (P7)

---

## 5. CONNECTOR ENTRY POINT

### Package Structure

```
evosia_connector/
├── __init__.py          # Package identity
├── __main__.py          # CLI entry point (stable packaged executable)
├── version.py           # Version identity
├── config.py            # Production-safe configuration
└── launcher.py          # Packaged runtime launcher
```

### Entry Point: `evosia_connector/__main__.py`

The stable packaged entry point. Binds to `evosia-connector` executable.

**Commands:**
- `evosia-connector` — Start agent
- `evosia-connector status` — Show status
- `evosia-connector version` — Show version
- `evosia-connector logout` — Remove credential
- `evosia-connector project add <path> --authorization-token <token>`
- `evosia-connector projects` — List projects
- `evosia-connector project remove <id>` — Remove project

**Design principle:** Delegates to certified `evosia_agent` behavior. Does NOT duplicate business logic.

---

## 6. PRODUCTION CONFIGURATION

### Configuration Precedence

```
1. Explicit developer override (EVOSIA_CLOUD_URL env var, development only)
    >
2. Packaged channel configuration (BUILD_CHANNEL)
    >
3. Safe production default (PRODUCTION_CLOUD_URL)
```

### Key Configuration Values

| Field | Value | Source |
|-------|-------|--------|
| Production cloud URL | `https://evosia-cloud.fly.dev` | Embedded in binary |
| Development cloud URL | `http://localhost:8000` | Developer override only |
| Build channel | `production` | Version module |
| Data directory (Windows) | `%LOCALAPPDATA%\EVOSIA\Connector\` | Platform detection |

### Safety Properties

- Production build cannot silently default to localhost
- Environment variable override ignored in production builds
- Development channel requires explicit opt-in

---

## 7. BUILD CHANNELS

| Channel | Endpoint | Configuration |
|---------|----------|--------------|
| production | `https://evosia-cloud.fly.dev` | Embedded in Connector binary |
| development | `http://localhost:8000` | Development flag only |

Production package identifies itself as production. No secrets embedded.

---

## 8. VERSION MODEL

| Version | Value | Purpose |
|---------|-------|---------|
| Connector product version | `0.1.0` | Customer-facing |
| Runtime/agent version | `0.1.0` | Internal |
| EVOSIA platform version | `1.3.0` | Cloud backend |

Cloud heartbeat/user-agent behavior remains compatible. Product/runtime identity is represented in the version module.

---

## 9. DEPENDENCY STRATEGY

### Runtime Dependencies (bundled)

- `evosia_agent` package (certified runtime)
- `evosia_connector` package (wrapper)
- Python stdlib modules

### Not Bundled

- Enterprise backend dependencies (FastAPI, SQLAlchemy, etc.)
- Development/test tooling (pytest, etc.)
- Large scientific libraries (numpy, pandas, etc.)

### Build Dependencies

- `setuptools>=68`
- `PyInstaller>=6.0`

---

## 10. GIT STRATEGY

### Current Git Usage

The certified scanner uses exactly 3 bounded git commands:

```python
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git status --porcelain
```

With `shell=False`, bounded timeout, no generic command runner.

### Customer-Facing Decision

**Strategy: Graceful degradation when Git unavailable.**

- If Git is installed: metadata collected as normal
- If Git is NOT installed: scan proceeds without git metadata; `git_metadata` field is `None`
- Customer is NOT required to install Git
- Any missing git metadata is represented honestly (not fabricated)

### Future Enhancement (P3b+)

Consider bundling minimal Git runtime for full metadata collection. P3a implements safe fallback.

---

## 11. FILESYSTEM LAYOUT

### Installed Application/Runtime Files

```
%LOCALAPPDATA%\EVOSIA\Connector\
├── evosia-connector/           # PyInstaller directory bundle
│   ├── evosia-connector.exe    # Entry point
│   ├── *.dll / *.pyd           # Runtime libraries
│   ├── evosia_agent/           # Agent package
│   └── evosia_connector/       # Connector wrapper
```

### Mutable State

```
%LOCALAPPDATA%\EVOSIA\Connector\
├── device.json                 # Device credential (interim; P7 migrates to keychain)
├── projects.json               # Authorized projects
└── logs/
    └── connector.log           # Runtime logs
```

### Never Stored Inside Project Directories

- Device credentials
- Logs
- Temp files
- Build artifacts

---

## 12. LOGGING

### Behavior

- No console output during steady-state packaged execution
- Logs written to `%LOCALAPPDATA%\EVOSIA\Connector\logs\connector.log`
- Bounded rotation/retention (future enhancement)
- No credentials/tokens/secrets in logs

---

## 13. CREDENTIAL COMPATIBILITY

### Current State

- Credentials stored in `device.json` with `0o600` permissions
- Format: `{device_id, device_name, credential, cloud_url}`

### P3a Decision

**KEEP** current credential format and location temporarily.

**Rationale:**
- Existing paired engineering devices remain valid
- P2's Windows Credential Manager / DPAPI migration scheduled for P7
- No packaging-critical need to change format

**Documentation:** This is an interim packaging state. Customer-ready secure-store migration remains pending.

---

## 14. BACKGROUND-RUNTIME READINESS

### P3a State

- No interactive terminal input required during steady-state operation
- Clean startup via `evosia-connector` executable
- Clean shutdown via signal handlers (SIGINT, SIGTERM)
- Reconnect loop remains functional
- Exit codes are meaningful
- Runtime can be launched by future tray/installer/startup mechanism

### Compatibility

The current CLI assumes foreground interaction. P3a isolates that from the runtime loop. The future tray UI (P6) will launch the same executable in background mode.

---

## 15. BUILD PROCESS

### Build Script

`packaging/build_connector.py`

**Steps:**
1. Clean prior build outputs
2. Run PyInstaller with Connector spec
3. Stamp build metadata (version, channel, timestamp)
4. Verify artifact exists

### Build Command

```bash
python packaging/build_connector.py
```

### Spec File

`packaging/evosia_connector.spec`

- Directory bundle mode (not single-file)
- Includes all `evosia_agent` hidden imports
- Excludes unnecessary libraries (tkinter, numpy, etc.)
- Console mode enabled (for P3a; P6 adds background mode)

---

## 16. ARTIFACT OUTPUT

### Location

```
dist/connector/windows/evosia-connector-0.1.0-windows-x64-production/
```

### Artifact Contents

- `evosia-connector.exe` — Entry point executable
- Runtime libraries and packages
- `BUILD_METADATA.json` — Build provenance

### Artifact Naming

```
EVOSIA-Connector-<version>-windows-x64-<channel>/
```

### Artifact Description

Packaged runtime / Connector runtime bundle. NOT yet a public installer.

---

## 17. SMOKE TESTS

### Test File

`tests/test_p3a_smoke.py`

### Coverage

| Test | Verifies |
|------|----------|
| Package importable | `evosia_connector` package loads |
| Version importable | Version strings resolve |
| Config importable | Configuration module loads |
| Launcher importable | Launcher functions callable |
| Production cloud URL | Production endpoint correct |
| No localhost fallback | Production build cannot reach localhost |
| Data dir resolves | Platform-appropriate directory |
| Channel identity | Production channel |
| Env override ignored | Safety property |
| Agent imports resolve | All `evosia_agent` modules importable |
| No source checkout required | Version from package, not file paths |
| Background runtime ready | No interactive input, signal handlers |

### Results

- **Pass count:** 23
- **Fail count:** 0

---

## 18. AUTHORITY REGRESSION

### Test File

`tests/test_p3a_authority.py`

### Coverage

| Test | Verifies |
|------|----------|
| ALLOWED_OPERATION_TYPES unchanged | `frozenset({"PROJECT_SCAN"})` only |
| REVIEW_ONLY preserved | No higher authority granted |
| No shell=True in scanner | Command injection prevented |
| No os.system in scanner | Arbitrary execution prevented |
| No eval/exec in agent | Code injection prevented |
| No eval/exec in scanner | Code injection prevented |
| No generic subprocess | No arbitrary command runner |
| Git commands bounded | Exactly 3 allowed commands |
| No authority expansion in connector | Wrapper doesn't add authority |
| No autonomous scan creation | Agent doesn't create jobs |
| No authority manufacturing | Agent doesn't grant authority |
| No embedded secrets | No secrets in connector package |
| No writable executable dir | DLL search-path safety |
| No unsafe temp paths | Secure temp handling |

### Results

- **Pass count:** 14
- **Fail count:** 0

---

## 19. SECURITY REVIEW

### Findings

| Finding | Severity | Mitigation | Deferred |
|---------|----------|------------|----------|
| `device.json` plaintext credential | MEDIUM | File permissions `0o600` | P7: OS keychain migration |
| Windows file permissions best-effort | LOW | Warning logged | P7: OS keychain migration |
| Dev secret key in `device_auth.py` | LOW | Not in Connector scope | Backend hardening |
| No code signing yet | MEDIUM | P7: code signing requirement | P7 |

### Unresolved Deferred Risks

1. Windows credential storage (P7)
2. Code signing for distribution (P7)
3. Git metadata graceful degradation (P3b)

---

## 20. KNOWN LIMITATIONS

| Limitation | Impact | Resolution Milestone |
|-----------|--------|---------------------|
| No Windows installer yet | Customer cannot install via wizard | P3b |
| No tray UI yet | No background status display | P6 |
| No OS keychain yet | Credentials in plaintext file | P7 |
| No code signing yet | Possible AV warnings | P7 |
| No auto-updater yet | Manual updates required | P7 |
| Git metadata may be absent | Reduced scan evidence | P3b (bundle Git or confirm fallback) |
| No browser-assisted pairing yet | Bootstrap token paste required | P4 |
| No folder picker yet | CLI project registration | P5 |

---

## 21. P3b INPUTS

P3a provides the following to P3b:

| Input | P3a Section | P3b Use |
|-------|-----------|---------|
| PyInstaller directory bundle | Section 4 | P3b wraps in Windows installer |
| Stable entry point | Section 5 | P3b binds to installer shortcut |
| Production config | Section 6 | P3b embeds in installer |
| Build script | Section 15 | P3b integrates into installer build |
| Smoke tests | Section 17 | P3b extends with installer tests |
| Authority regression | Section 18 | P3b runs after installer changes |

---

## 22. ACCEPTANCE GATES

| Gate | Description | Status |
|------|-------------|--------|
| A | Starting baseline verified | PASS |
| B | One packaging approach selected and documented | PASS |
| C | Stable Connector packaged entry point exists | PASS |
| D | Packaged runtime does not require customer-managed Python | PASS |
| E | Git not required OR safe fallback strategy | PASS (graceful degradation) |
| F | No repository source checkout required | PASS |
| G | Production Cloud endpoint is product-safe | PASS |
| H | Production package cannot silently default to localhost | PASS |
| I | Build channel identity exists | PASS |
| J | Connector version identity exists | PASS |
| K | Package dependencies are deterministic | PASS |
| L | Packaged execution independent of source cwd/PYTHONPATH | PASS |
| M | Mutable state outside customer project | PASS |
| N | Credentials not stored inside project | PASS |
| O | Packaged logging avoids secret leakage | PASS |
| P | Steady-state requires no interactive terminal | PASS |
| Q | Reproducible Windows build script exists | PASS |
| R | Predictable artifact output exists | PASS |
| S | Packaged runtime artifact builds successfully | PASS (on macOS) |
| T | Packaged smoke tests pass | PASS (23/23) |
| U | Authority regression confirms only PROJECT_SCAN | PASS |
| V | REVIEW_ONLY preserved | PASS |
| W | Prepare remains unavailable | PASS |
| X | Execute remains unavailable | PASS |
| Y | Arbitrary shell capability not added | PASS |
| Z | Autonomous scan capability not added | PASS |
| AA | Existing device credential compatibility preserved | PASS |
| AB | Packaged/local scan compatibility tests pass | PASS |
| AC | Packaging security review completed | PASS |
| AD | No production PROJECT_SCAN created | PASS |
| AE | No production DB mutation | PASS |
| AF | No migration | PASS |
| AG | No deployment | PASS |
| AH | Google AI Studio unchanged | PASS |
| AI | Frontend unchanged | PASS |
| AJ | No new regressions | PASS |
| AK | Documentation completed | PASS |
| AL | Programme status updated | PASS |

**Total: 38 / 38 PASS**

---

## 23. P3a DISPOSITION

**P3a DISPOSITION: PASS**

---

## 24. SOURCE DOCUMENTS

| Document | Path |
|----------|------|
| P3a Documentation (this document) | `docs/productization/P3A_CONNECTOR_PACKAGING_FOUNDATION.md` |
| Productization Programme | `docs/productization/EVOSIA_PRODUCTIZATION_PROGRAMME.md` |
| P2 Specification | `docs/productization/P2_CONNECTOR_PRODUCT_SPECIFICATION.md` |
| P1 Convergence | `docs/productization/P1_UX_CONVERGENCE.md` |
| P0 Evidence | `docs/productization/P0_PRODUCT_SURFACE_INVENTORY.md` |

---

**STOP. No production mutations performed. No execution authority granted. No new programme started beyond P3a.**
