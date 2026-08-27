# EVOSIA Local Agent — LA2 Operations Guide

## What is the Local Agent?

The EVOSIA Local Agent is a cross-platform client program that runs on your Mac or Windows PC. It allows your computer to connect to EVOSIA Cloud for device identification and status reporting.

**LA2 HAS NO PROJECT FILE ACCESS.**
**LA2 HAS NO EXECUTION AUTHORITY.**

The Local Agent can only:
- Identify itself to EVOSIA Cloud
- Register using a one-time bootstrap token
- Send heartbeat/status updates
- Survive temporary network failures
- Reconnect automatically
- Shut down cleanly

## What LA2 Cannot Do

- Access project folders
- Register projects
- Read project files
- Scan repositories
- Receive jobs
- Execute commands
- Modify files
- Create preparation workspaces
- Merge code
- Deploy changes
- Expose inbound network ports

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
   Authority: Device connection only

   No project folders have been authorised.
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
Authority: Device connection only
Projects authorised: None
Project access: Not enabled in LA2
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
- No project work exists to queue yet

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
- **Device credentials**: 30-day JWT, stored with restrictive file permissions
- **Communication**: All outbound HTTPS, no inbound ports
- **TLS verification**: Always enabled, never disabled
- **No secrets in logs**: Bootstrap tokens and JWTs are never logged

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
