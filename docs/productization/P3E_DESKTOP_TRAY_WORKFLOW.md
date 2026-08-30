# P3e Desktop/Tray Product Workflow

**Authority:** Connector  
**Status:** Implementation complete  
**Milestone:** Desktop/tray shell for Windows customer workflow

## Scope

P3e converts CLI-based Connector flows into a customer-facing desktop/tray application for Windows. The tray application orchestrates existing P3c pairing, P3d project authorization, and certified PROJECT_SCAN flows.

## Technology Decision

**Selected:** tkinter (stdlib) + pystray (lightweight tray library)

- **tkinter:** Python standard library, no additional dependencies, native Windows appearance
- **pystray:** Lightweight tray icon library, cross-platform, well-maintained
- **Rationale:** Minimal footprint, no Electron overhead, suitable for tray applications

## Architecture

### State Machine (`evosia_connector/state_machine.py`)

12 states in the Connector lifecycle:

| State | Description |
|-------|-------------|
| `STARTING` | Application initializing |
| `NOT_CONNECTED` | No device credential |
| `CONNECTING` | Pairing flow in progress |
| `CONNECTED` | Device registered, no projects |
| `NO_PROJECTS` | Connected but no authorized projects |
| `READY` | Connected with projects, idle |
| `REVIEW_QUEUED` | Review request created, waiting |
| `REVIEW_IN_PROGRESS` | Review polling in progress |
| `REVIEW_COMPLETE` | Review finished successfully |
| `REVIEW_FAILED` | Review failed (can retry) |
| `OFFLINE` | Cloud unreachable |
| `ERROR` | Fatal error state |

### Desktop Application (`evosia_connector/desktop_tray.py`)

- System tray icon with pystray (fallback to tkinter window)
- State-dependent context menu
- Background heartbeat loop (30-second interval)
- Review lifecycle polling (2-second interval, 300 max attempts)
- Diagnostics window (version, cloud, device, status, projects, heartbeat, review)
- Thread-safe state transitions

## Actions

| Action | Available When | Action |
|--------|---------------|--------|
| Connect | NOT_CONNECTED | Opens browser for P3c pairing |
| Add Project | CONNECTED, READY | Opens folder picker for P3d authorization |
| Review Project | READY, REVIEW_FAILED | Creates PROJECT_SCAN, polls for completion |
| Open EVOSIA | Any connected state | Opens EVOSIA web app |
| Diagnostics | Any state | Shows diagnostic information |
| Exit | Any state | Closes application |

## Authority Invariants

- `DeviceProject.authority = REVIEW_ONLY`
- `ALLOWED_OPERATION_TYPES = frozenset({"PROJECT_SCAN"})`
- No Prepare/Execute authority granted
- No deployment or merge operations
- No mutation of cloud state

## Security

- No arbitrary shell execution (`shell=True`, `os.system`, `subprocess`)
- No credential exposure in diagnostics
- Safe browser launch via `webbrowser.open()`
- Path privacy (SHA256 fingerprint, no raw path in requests)

## Non-Goals

- Prepare/Execute authority
- Automatic updater
- Public installer release
- Signing
- Broad frontend redesign
- Deployment operations
- Merge operations
- Credential Manager migration

## Files

| File | Purpose |
|------|---------|
| `evosia_connector/state_machine.py` | Connector state machine |
| `evosia_connector/desktop_tray.py` | Desktop/tray application |
| `tests/test_p3e_desktop_tray.py` | P3e test suite (39 tests) |
| `packaging/evosia_connector.spec` | PyInstaller spec (updated) |

## Test Results

- **39 P3e tests:** All pass
- **78 total (P3c+P3d+P3e):** All pass, zero regressions
- **Authority boundary tests:** Verified no new authority introduced
- **Security boundary tests:** Verified no arbitrary shell, no credential exposure
