# EVOSIA Local Agent — LA4 Operations Guide

## What is the Local Agent?

The EVOSIA Local Agent is a cross-platform client program that runs on your Mac or Windows PC. It allows your computer to connect to EVOSIA Cloud for device identification, status reporting, and governed read-only project scanning.

**LA4 ADDS GOVERNED READ-ONLY PROJECT SCANNING.**
**LA4 HAS NO WRITE, EXECUTE, MERGE, OR DEPLOY AUTHORITY.**

The Local Agent can only:
- Identify itself to EVOSIA Cloud
- Register using a one-time bootstrap token
- Send heartbeat/status updates
- Survive temporary network failures
- Reconnect automatically
- Shut down cleanly
- Execute governed read-only project scans (LA4)

## What LA4 Cannot Do

- Access project folders without explicit user authorization
- Read project files without a scan job
- Execute commands, scripts, or shell instructions
- Modify files
- Create preparation workspaces
- Merge code
- Deploy changes
- Expose inbound network ports
- Create its own scan jobs (requires human/cloud authority)

## Registration Process

1. Start the agent:
   ```bash
   python -m evosia_agent
   ```

2. The agent detects this computer is not registered and prompts for a bootstrap token.

3. In EVOSIA Cloud dashboard, create a new device registration token.

4. Paste the token when prompted:
   ```
   Enter the one-time device registration token
   shown in your EVOSIA dashboard:
   > la_boot_xxxxxxxxxxxxxxxxxxxxx
   ```

5. The agent exchanges the bootstrap token for a device credential and stores it locally.

6. Registration complete:
   ```
   Device registered successfully.

   Device: David's MacBook Pro
   Status: Connected
   Authority: Device connection + governed scanning

   Project folders can be authorised for read-only scanning.
   ```

## Starting the Agent

### macOS / Linux

```bash
# From the repository root
python -m evosia_agent

# Or if installed via pip
evosia-agent
```

### Windows (PowerShell 7+)

```powershell
# From the repository root
python -m evosia_agent

# Or if installed via pip
evosia-agent
```

## Status Command

Check agent status without starting the heartbeat loop:

```bash
python -m evosia_agent status
```

Output:
```
EVOSIA Local Agent
----------------------------------------
Device: David's MacBook Pro
Device ID: dev_abc12345...
Cloud: https://evosia-cloud.fly.dev
Agent version: evosia-agent/0.1.0
Authority: Device connection + governed scanning
Projects authorised: 1
Project access: LA4 governed read-only scanning
```

## Shutdown

- Press `Ctrl+C` to stop the agent gracefully
- The agent stops the heartbeat loop and exits cleanly
- No corrupted credential/config state

## Cloud URL Configuration

By default, the agent connects to the production EVOSIA Cloud URL. To use a different server:

```bash
# Set environment variable
export EVOSIA_CLOUD_URL="https://your-server.example.com"

# Then start the agent
python -m evosia_agent
```

## Local Credential Storage

The agent stores its device credential locally:

- **macOS**: `~/Library/Application Support/EVOSIA/device.json`
- **Windows**: `%LOCALAPPDATA%\EVOSIA\device.json`
- **Linux**: `~/.local/share/EVOSIA/device.json`

The credential file is created with restrictive permissions (owner read/write only) on Unix-like systems.

**Note**: The bootstrap token is never stored locally. Only the device credential (JWT) is persisted.

## Revocation Behavior

If the device is revoked in EVOSIA Cloud:

1. The agent detects revocation on the next heartbeat
2. Stops the heartbeat loop
3. Removes the local credential
4. Displays:
   ```
   This EVOSIA device has been revoked.
   Register this computer again from EVOSIA to reconnect.
   ```

To reconnect, re-register with a new bootstrap token.

## Network/Offline Behavior

- The agent handles temporary network failures gracefully
- Uses bounded retry/backoff (5s → 10s → 30s → 60s max)
- When connectivity returns, heartbeat resumes automatically
- Project registration is cached locally for offline use

## Project Authorization (LA6)

LA6 introduces human-authorized project connection. A project can only be registered after an authenticated human explicitly authorizes it.

### Connecting a Project

1. **Connect Computer**: Register your computer with EVOSIA (see Device Registration above)
2. **Open Computers**: Navigate to the Computers page in EVOSIA
3. **Select computer**: Click on the computer you want to connect a project to
4. **Authorise project**: Click "Authorise project" button
5. **Copy token**: Copy the one-time authorization code shown in the modal
6. **Run command locally**: On your computer, run:
   ```bash
   python -m evosia_agent project add "/Users/david/Projects/BibleQuest" --authorization-token la_proj_abc123def456
   ```
7. **Token consumed**: The token is consumed during registration and cannot be reused
8. **Project registered**: The project is registered with REVIEW_ONLY authority

### What Authorization Does NOT Do

- Authorization itself does NOT scan the project
- Authorization does NOT read or modify project files
- Authorization does NOT grant execution, merge, or deploy permissions
- "Review Project" remains a separate human action

### Registering a Project

```bash
python -m evosia_agent project add "/Users/david/Projects/BibleQuest" --authorization-token <token>
```

Output:
```
Project:
  BibleQuest

Location:
  /Users/david/Projects/BibleQuest

Authority:
  Review only

EVOSIA will be able to inspect this project only after future scan
functionality is separately authorized.
No files have been changed.

Project registered successfully.
```

### Without Authorization Token

If you run `project add` without `--authorization-token`, the agent prints instructions:

```
Project authorization required.

Generate a one-time authorization code from EVOSIA Computers,
then run this command again with that code:

  python -m evosia_agent project add <path> --authorization-token <token>
```

### Listing Registered Projects

```bash
python -m evosia_agent projects
```

Output:
```
EVOSIA Local Agent
----------------------------------------

Authorised projects:

1. BibleQuest
   Path: BibleQuest
   Authority: Review Only
   Status: Active

Total: 1 project(s)
```

### Removing a Project

```bash
python -m evosia_agent project remove BibleQuest
```

Output:
```
Project removed: BibleQuest
Cloud registration unchanged. Use EVOSIA dashboard to revoke.
```

#### Project Security

- **No automatic discovery**: User explicitly selects project root
- **No source file reading**: LA6 does not scan or read project contents
- **No Git commands**: No git status, branch, or log commands
- **Path containment**: Traversal escape (`../`) is denied
- **Symlink protection**: Symlinks escaping root are detected and denied
- **Sensitive file policy**: `.env`, `.pem`, `.key`, SSH keys are classified
- **Path privacy**: Raw absolute paths are not sent to cloud (only SHA-256 fingerprint)
- **Immutability**: Registration does not modify the target project
- **Human authorization required**: Agent cannot mint its own authorization tokens

### Project Authority

All registered projects start with:
- **Authority**: REVIEW_ONLY
- **No**: WRITE, PREPARE, EXECUTE, MERGE, DEPLOY

### Project Authorization Token

- **Created by**: Authenticated human via EVOSIA Computers UI
- **Single-use**: Consumed during registration, cannot be reused
- **Short-lived**: Expires after 10 minutes
- **Device-bound**: Token is bound to a specific device
- **Not persisted**: Agent does not store the token after registration
- **Not logged**: Token is never written to logs or local files

### Project Revocation

Projects can be revoked locally:
```bash
python -m evosia_agent project remove <project-id>
```

Cloud revocation requires using the EVOSIA dashboard.

## Governed Read-Only Scanning (LA4)

LA4 introduces governed read-only project scanning. The agent can scan project files ONLY when a scan job exists that was created by an authenticated user or cloud system.

### How Scanning Works

1. **User creates scan job**: An authenticated user creates a scan job via the EVOSIA dashboard or API
2. **Agent polls for jobs**: During heartbeat, the agent checks for pending scan jobs
3. **Agent executes scan**: If a job exists, the agent performs a bounded, read-only scan
4. **Agent submits evidence**: Scan results are submitted as cryptographically signed evidence

### Scan Authority Requirements

- **Scan jobs CANNOT be created by the agent** — only by authenticated users or cloud systems
- **Each scan requires explicit authorization** — no implicit or cached authority
- **Agent verifies job authenticity** — checks device_id, project_id, and job status
- **Read-only enforcement** — scanner cannot write, execute, or modify files

### Scan Limits

The scanner enforces strict resource limits:
- **File size**: 1MB per file maximum
- **Total read**: 10MB aggregate maximum
- **File count**: 5000 files maximum
- **Timeout**: 120 seconds maximum
- **Path containment**: Cannot escape project root
- **Symlink protection**: Symlinks escaping root are denied

### Git Metadata

The scanner reads only these git metadata fields (hardcoded allowlist):
- `git rev-parse --abbrev-ref HEAD` (current branch)
- `git rev-parse HEAD` (commit hash)
- `git status --porcelain` (changed files)

No other git commands are executed.

### Evidence Format

Scan results are submitted as evidence with:
- `provenance = "LIVE_EVOSIA_EVIDENCE"`
- `evidence_source = "device_local_scan"`
- Cryptographic signature for tamper detection
- Timestamp and scan metadata

### Starting a Scan

The agent automatically scans when a pending job is detected during heartbeat. No manual action is required.

### Monitoring Scans

Check scan status via the EVOSIA dashboard or API:
```bash
# List scan jobs for a project
curl -H "Authorization: Bearer <token>" \
  https://evosia-cloud.fly.dev/api/device-projects/<project-id>/scans
```

### Scan Security

- **No shell execution**: Scanner cannot run shell commands
- **No file writes**: Scanner is strictly read-only
- **Path containment**: All file access is within project root
- **Symlink fail-closed**: Symlinks that escape root are denied
- **Resource bounded**: File count, size, and time limits enforced
- **Human authority required**: Agent cannot create its own scan jobs

## Logout

Remove the local credential without revoking the device in EVOSIA Cloud:

```bash
python -m evosia_agent logout
```

Output:
```
Logged out from device: David's MacBook Pro
Local credential removed.
The device is still registered in EVOSIA Cloud.
To fully revoke, use the EVOSIA dashboard.
```

## Security Model

- **Bootstrap tokens**: Single-use, 5-minute expiry, never stored locally
- **Project authorization tokens**: Single-use, 10-minute expiry, created by authenticated human only
- **Device credentials**: 30-day JWT, stored with restrictive file permissions
- **Communication**: All outbound HTTPS, no inbound ports
- **TLS verification**: Always enabled, never disabled
- **No secrets in logs**: Bootstrap tokens, JWTs, and project authorization tokens are never logged
- **Scan authority**: Human-initiated only, no self-authorization
- **Project authority**: REVIEW_ONLY — no execution, merge, or deploy
- **Read-only enforcement**: Scanner cannot write, execute, or modify files

## Development Setup

For development against a local EVOSIA backend:

```bash
# Start local EVOSIA backend (Terminal A)
cd hermes-runtime-v0.3-runtime
uvicorn enterprise.app:app --reload

# Point agent to local backend (Terminal B)
export EVOSIA_CLOUD_URL="http://localhost:8000"
python -m evosia_agent
```

## Troubleshooting

### "Registration failed: Invalid bootstrap token"
- Check the token was copied correctly
- Ensure the token hasn't expired (5-minute limit)
- Ensure the token hasn't been used already

### "Device revoked"
- The device was revoked in EVOSIA Cloud
- Re-register with a new bootstrap token

### "Credential expired"
- The device credential has expired (30-day limit)
- Re-register with a new bootstrap token

### Connection issues
- Check network connectivity
- Verify the cloud URL is correct
- Check if the EVOSIA Cloud service is running
