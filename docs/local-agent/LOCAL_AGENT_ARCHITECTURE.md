# EVOSIA Local Agent & Device Architecture

**Programme:** I — Read-Only Multi-Device Foundation
**Date:** 2026-08-27
**Baseline:** `8c0de31179c74e3ffa6bcff895a1939a98acea1f`
**EVOSIA Runtime:** 1.3.0
**Purpose:** Document the architecture for a Local Agent that enables EVOSIA to safely review projects on authorised remote computers.

---

## 1. Existing Relevant Architecture

### 1.1 Components That Can Be Reused

| Component | Location | Reuse Potential |
|-----------|----------|-----------------|
| JWT authentication | `enterprise/services/__init__.py` | Device tokens can use same JWT infrastructure |
| User model | `enterprise/models/__init__.py` | Device belongs to a User |
| Repository model | `enterprise/models/__init__.py` | LocalProject maps to Repository |
| ScanJob model | `enterprise/models/__init__.py` | Remote scans create ScanJobs |
| JournalEvent model | `enterprise/models/__init__.py` | Device/project events create journal entries |
| Safety boundary | `enterprise/services/safety.py` | FORBIDDEN_OPERATIONS extends to Local Agent |
| Build provenance | `enterprise/services/build_info.py` | Local Agent reports its version |
| Scanning pipeline | `enterprise/services/scanner.py` | Remote scans invoke same pipeline |
| PreparedChange sandbox | `enterprise/services/preparation.py` | Path isolation patterns reusable |
| FastAPI app | `enterprise/app.py` | New routers added for device/project APIs |
| Database | `enterprise/database.py` | Same database, new tables |
| Alembic migrations | `enterprise/migrations/versions/` | New migration for device/project tables |

### 1.2 Components Requiring Extension

| Component | Extension Required |
|-----------|-------------------|
| `enterprise/models/__init__.py` | Add Device model (LA1); DeviceProject deferred to LA3 |
| `enterprise/schemas/__init__.py` | Add device request/response schemas |
| `enterprise/routers/` | Add devices router (control plane) |
| `enterprise/services/` | Add device_service, device_auth |
| `pyproject.toml` | Add `evosia-agent` entry point |

### 1.3 Components Not Affected

| Component | Reason |
|-----------|--------|
| Guided Mode | Unchanged — device scans feed into existing findings/missions |
| Human Review | Unchanged — device findings go through same adjudication |
| Gemini explanations | Unchanged — explanation-only boundary preserved |
| Frontend (enterprise-ui) | Extended, not redesigned — new views for devices/projects |
| Existing CLI commands | Unaffected — Local Agent is a new entry point |

---

## 2. Proposed Local Agent Architecture

### 2.1 High-Level Design

```
                    EVOSIA Cloud
              (Railway / Docker)
                    |
            +-------+-------+
            |               |
       /api/devices    /api/projects
       /api/scans     /api/agent
            |               |
            +-------+-------+
                    |
            +-------+-------+
            |               |
      Local Agent      Local Agent
        (Mac)          (Windows)
         |               |
    Authorised       Authorised
     Projects         Projects
```

### 2.2 Communication Direction

**CRITICAL: Local Agent initiates ALL outbound communication via polling.**

```
EVOSIA Cloud                          Local Agent
      |                                    |
      |  (Human requests scan in UI)       |
      |  (Cloud creates governed job)      |
      |                                    |
      |                                    |--- POST /api/agent/heartbeat --->
      |                                    |<-- 200 OK (no work) ------------
      |                                    |
      |                                    |--- POST /api/agent/heartbeat --->
      |                                    |<-- 200 OK (work available) ------
      |                                    |    { jobs: [{ job_id, ... }] }
      |                                    |
      |                                    |--- GET /api/agent/jobs/{id} ---->
      |                                    |<-- 200 OK (job details) ---------
      |                                    |
      |                                    |--- POST /api/agent/jobs/{id}/started
      |                                    |
      |                                    |--- POST /api/agent/jobs/{id}/results
      |                                    |<-- 200 OK (recorded) ------------
```

**Why outbound polling is selected for Programme I:**

1. **Simple** — Standard HTTP request/response, no persistent connections
2. **Firewall/NAT friendly** — Most networks allow outbound HTTPS; no inbound ports
3. **Cross-platform** — Works identically on macOS, Windows, Linux
4. **No inbound attack surface** — User's PC exposes no ports to the network
5. **Works with ordinary HTTPS infrastructure** — Railway, Docker, nginx all compatible
6. **Supports offline devices naturally** — Agent polls when connected; cloud shows offline when not

**Why NOT other approaches for Programme I:**

| Approach | Why Not Selected |
|----------|------------------|
| Cloud polls agent | Requires local port exposure, firewall/NAT issues |
| WebSocket | Complex, persistent connection, harder to debug |
| Message broker | Introduces infrastructure dependency |
| Cloud-initiated connection | Requires user to configure network access

### 2.3 Agent Authentication

**Bootstrap Registration Flow:**

```
1. Authenticated human chooses "Add device" in EVOSIA Cloud dashboard
2. Cloud creates a short-lived, single-use registration token/code
3. Cloud displays token to user (e.g., "EVOSIA-ABCD-1234")
4. User enters token in Local Agent: evosia-agent --register EVOSIA-ABCD-1234
5. Agent presents token over HTTPS to POST /api/devices/register
6. Cloud validates token (single-use, expires in 10 minutes)
7. Cloud creates Device record with status="active"
8. Cloud issues a dedicated device credential (JWT scoped to device_id)
9. Agent stores credential securely in local config
10. Every subsequent agent request uses device credential
11. Server checks device status/revocation on every request
12. Revocation invalidates future device authentication
```

**Why NOT user email/password for agent authentication:**

| Concern | Risk |
|---------|------|
| Password stored locally | Compromised if device stolen |
| Password in agent memory | Exposed in process memory dumps |
| Password transmitted | Intercepted if TLS misconfigured |
| Reuse across devices | Single compromised agent = all devices |

**Why registration tokens are safer:**

| Property | Benefit |
|----------|---------|
| Single-use | Cannot be reused if intercepted |
| Short-lived | Expires in 10 minutes |
| Device-specific | Scoped to one device_id |
| No user password | Agent never sees human credentials |
| Revocable | Device access revoked independently |

**Device Credential Properties:**

| Property | Value |
|----------|-------|
| Type | JWT (device-scoped) |
| Algorithm | HS256 |
| Expiry | 30 days (configurable) |
| Scope | device_id, ["read", "scan"] |
| Refresh | Re-registration required after expiry |
| Revocation | Device status checked server-side |

**Future Capabilities (not LA1):**

- Credential rotation
- Multiple credentials per device
- Credential expiry with re-registration

---

## 3. Trust Boundary Diagram

```
+------------------------------------------------------------------+
|                        EVOSIA CLOUD                               |
|  +--------------------------------------------------------------+
|  |  FastAPI Application                                         |
|  |  - JWT authentication                                        |
|  |  - Device/project management                                |
|  |  - Scan orchestration                                        |
|  |  - Findings/mission management                               |
|  |  - NO execution authority                                    |
|  +--------------------------------------------------------------+
|                           |                                       |
|  +------------------------+--------------------------------------+|
|  |                    Database                                   ||
|  |  - users                                                       ||
|  |  - devices                                                     ||
|  |  - device_projects                                             ||
|  |  - repositories                                                ||
|  |  - scan_jobs                                                   ||
|  |  - findings                                                    ||
|  |  - journal_events                                              ||
|  +--------------------------------------------------------------+
+------------------------------------------------------------------+
                           |
                    Outbound HTTPS
                    (Agent-initiated)
                           |
+------------------------------------------------------------------+
|                    LOCAL AGENT                                    |
|  +--------------------------------------------------------------+
|  |  Agent Process                                                |
|  |  - Authentication (JWT)                                       |
|  |  - Heartbeat                                                  |
|  |  - Project scanning                                           |
|  |  - Evidence collection                                        |
|  |  - NO arbitrary command execution                             |
|  +--------------------------------------------------------------+
|                           |                                       |
|  +------------------------+--------------------------------------+|
|  |  Authorised Project Roots                                    ||
|  |  /Users/David/Projects/BibleQuest                             ||
|  |  /Users/David/Projects/MenWise360                             ||
|  |                                                               ||
|  |  RESTRICTED:                                                  ||
|  |  /Users/David (parent traversal blocked)                      ||
|  |  /Users/David/.ssh (sensitive files blocked)                  ||
|  |  /Users/David/.env (secrets blocked)                          ||
|  +--------------------------------------------------------------+
+------------------------------------------------------------------+
```

---

## 4. Device Identity Design

### 4.1 Device Model

```python
class Device(Base):
    __tablename__ = "devices"
    
    id = Column(String(36), primary_key=True, default=_uuid)
    device_id = Column(String(128), unique=True, nullable=False, index=True)
    device_name = Column(String(255), nullable=False)
    platform = Column(String(50), nullable=False)  # "macos", "windows", "linux"
    agent_version = Column(String(50), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    # Status
    status = Column(String(30), default="pending")  # pending, active, revoked
    last_seen_at = Column(DateTime)
    
    # Capabilities
    capabilities = Column(JSON, default=list)  # ["read", "scan"]
    
    # Timestamps
    registered_at = Column(DateTime, default=_utcnow)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    
    # Relationships
    user = relationship("User")
    projects = relationship("DeviceProject", back_populates="device")
```

### 4.2 Device Identity Requirements

| Requirement | Implementation |
|-------------|----------------|
| Not based on hostname alone | device_id = UUID generated at first startup |
| Unique per installation | Stored in agent config file |
| Stable across restarts | Persisted locally, never regenerated |
| Platform-identifiable | `platform` field from `sys.platform` |
| Version-tracked | `agent_version` from package metadata |

### 4.3 Device Registration Flow

```
1. User starts agent: python -m evosia_agent
2. Agent prompts for registration token
3. User obtains token from EVOSIA Cloud dashboard:
   - User clicks "Add device"
   - Cloud generates single-use token (e.g., "EVOSIA-ABCD-1234")
   - Token expires in 10 minutes
4. User enters token in agent
5. Agent sends POST /api/devices/register with:
   - registration_token
   - device_name (user-provided or hostname-derived)
   - platform
   - agent_version
6. Cloud validates token (single-use, not expired)
7. Cloud creates Device record with status="active"
8. Cloud issues device credential (JWT scoped to device_id)
9. Agent stores credential locally
10. Agent can now perform operations
```

**Why NOT this flow:**

```
❌ OLD FLOW (INCORRECT):
1. User installs agent
2. User starts agent
3. Agent prompts for EVOSIA credentials    ← WRONG: agent sees password
4. Agent authenticates via POST /api/auth/agent-login  ← WRONG: stores password
```

**Why this flow is correct:**

```
✅ NEW FLOW (CORRECT):
1. User starts agent
2. User obtains single-use token from cloud dashboard
3. User enters token in agent
4. Agent never sees user's password
5. Token is single-use and expires
```

---

## 5. Device Authentication Design

### 5.1 Device Credential Structure

```python
{
    "device_id": "device_uuid",
    "device_scopes": ["read", "scan"],
    "exp": datetime.utcnow() + timedelta(days=30),
    "iat": datetime.utcnow()
}
```

### 5.2 Credential Properties

| Property | Value |
|----------|-------|
| Algorithm | HS256 (same as existing JWT infrastructure) |
| Expiry | 30 days |
| Refresh | Re-registration required |
| Scope | Device-specific, cannot be escalated |
| Revocation | Device status checked on every request |

### 5.3 Authentication Middleware

```python
def get_current_device(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Device:
    """Authenticate a Local Agent request."""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    device_id = payload.get("device_id")
    if not device_id:
        raise HTTPException(status_code=401, detail="Invalid device token")
    
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device or device.status != "active":
        raise HTTPException(status_code=401, detail="Device not authorized")
    
    return device
```

### 5.4 Credential Lifecycle

| Phase | Action | Storage |
|-------|--------|---------|
| Registration | Token exchanged for credential | Agent: credential; Cloud: device record |
| Active | Credential used for requests | Agent: credential; Cloud: device record |
| Revocation | User revokes device | Agent: credential invalidated server-side |
| Expiry | Credential expires | Agent: re-registration required |
| Compromise | User revokes device | Agent: credential invalidated immediately |

### 5.5 Credential Storage (Agent Side)

```json
// ~/.config/evosia-agent/config.json
{
    "device_id": "uuid",
    "credential": "eyJhbGciOiJIUzI1NiIs...",
    "device_name": "David's MacBook",
    "registered_at": "2026-08-27T10:30:00Z"
}
```

**Security:**

- Credential file permissions: 0600 (owner read/write only)
- Credential never logged
- Credential never transmitted in plaintext (HTTPS only)
- Credential never stored in cloud database

---

## 6. Project Registration Design

**Note:** Project registration is deferred to LA3 when filesystem isolation and project-root authority are introduced. LA1 implements only the device trust domain.

### 6.1 DeviceProject Model (LA3)

```python
class DeviceProject(Base):
    __tablename__ = "device_projects"
    
    id = Column(String(36), primary_key=True, default=_uuid)
    device_id = Column(String(36), ForeignKey("devices.id"), nullable=False)
    project_name = Column(String(255), nullable=False)
    
    # Local path (stored on agent, not in cloud)
    local_root_hash = Column(String(64), nullable=False)  # SHA-256 of canonical path
    
    # Cloud-side identity
    repository_id = Column(String(36), ForeignKey("repositories.id"), nullable=True)
    
    # Authority
    authority_level = Column(String(30), default="review_only")  # review_only only for now
    
    # Status
    status = Column(String(30), default="active")  # active, revoked
    
    # Timestamps
    registered_at = Column(DateTime, default=_utcnow)
    last_scanned_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    
    # Relationships
    device = relationship("Device", back_populates="projects")
    repository = relationship("Repository")
```

### 6.2 Project Registration Flow

```
1. User selects project folder via agent CLI
2. Agent validates path:
   - Path exists
   - Path is a directory
   - Path is under user's home directory
   - No symlink escapes
   - No sensitive files exposed
3. Agent computes local_root_hash = SHA-256(canonical_path)
4. Agent sends POST /api/projects with:
   - device_id
   - project_name (user-provided)
   - local_root_hash
5. Cloud creates DeviceProject record
6. Cloud creates Repository record (provider="local_agent")
7. Project appears in EVOSIA dashboard
```

### 6.3 Path Canonicalisation

```python
def canonicalise_project_root(path: str) -> Path:
    """Canonicalise and validate a project root path."""
    root = Path(path).resolve()
    
    # Must be an absolute path
    if not root.is_absolute():
        raise ValueError(f"Path must be absolute: {path}")
    
    # Must exist and be a directory
    if not root.is_dir():
        raise ValueError(f"Path must be a directory: {path}")
    
    # Must be under user's home directory
    home = Path.home()
    try:
        root.relative_to(home)
    except ValueError:
        raise ValueError(f"Path must be under home directory: {path}")
    
    # Check for symlink escapes
    if root.is_symlink():
        real_root = root.resolve()
        if not str(real_root).startswith(str(home)):
            raise ValueError(f"Symlink escapes home directory: {path}")
    
    return root
```

---

## 7. Filesystem Isolation Design

**Note:** Filesystem isolation is deferred to LA3 when project-root authority and filesystem access are introduced. LA1 implements only the device trust domain.

### 7.1 Allowed Operations

| Operation | Allowed | Notes |
|-----------|---------|-------|
| Read files | YES | Within registered project root only |
| List directories | YES | Within registered project root only |
| Compute file hashes | YES | For immutability verification |
| Run read-only scans | YES | Using existing EVOSIA Core pipeline |
| Modify files | NO | Forbidden |
| Create files | NO | Forbidden |
| Delete files | NO | Forbidden |
| Execute shell commands | NO | Forbidden |
| Access parent directories | NO | Path traversal blocked |
| Access sensitive files | NO | .env, .pem, .key, etc. |

### 7.2 Path Traversal Protection

```python
def validate_project_access(project_root: Path, requested_path: str) -> Path:
    """Validate that a requested path is within the project root."""
    requested = (project_root / requested_path).resolve()
    
    try:
        requested.relative_to(project_root.resolve())
    except ValueError:
        raise PermissionError(f"Path traversal blocked: {requested_path}")
    
    # Check for symlink escapes
    if requested.exists() and requested.is_symlink():
        real_path = requested.resolve()
        try:
            real_path.relative_to(project_root.resolve())
        except ValueError:
            raise PermissionError(f"Symlink escape blocked: {requested_path}")
    
    return requested
```

### 7.3 Sensitive File Policy

```python
SENSITIVE_PATTERNS = {
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx",
    "id_rsa", "id_ed25519", "id_ecdsa",
    ".git-credentials", ".netrc",
    "*.keystore", "*.jks",
}

def is_sensitive_file(path: Path) -> bool:
    """Check if a file matches sensitive patterns."""
    name = path.name
    for pattern in SENSITIVE_PATTERNS:
        if path.match(pattern) or name == pattern:
            return True
    return False
```

### 7.4 Evidence Collection (Safe)

```python
def collect_safe_evidence(project_root: Path) -> dict:
    """Collect evidence without transmitting secrets."""
    evidence = {
        "file_count": 0,
        "directory_count": 0,
        "sensitive_files_found": [],
        "file_types": {},
    }
    
    for path in project_root.rglob("*"):
        if path.is_file():
            evidence["file_count"] += 1
            
            if is_sensitive_file(path):
                evidence["sensitive_files_found"].append(
                    str(path.relative_to(project_root))
                )
            else:
                ext = path.suffix.lower()
                evidence["file_types"][ext] = evidence["file_types"].get(ext, 0) + 1
        elif path.is_dir():
            evidence["directory_count"] += 1
    
    return evidence
```

---

## 8. Secret Handling Design

**Note:** Secret handling for project files is deferred to LA3 when filesystem access is introduced. LA1 implements only the device trust domain.

### 8.1 What Is NEVER Sent to Cloud

| Category | Examples |
|----------|----------|
| Secret values | `.env` contents, API keys, passwords |
| Private keys | SSH keys, TLS certificates |
| Credential files | `.git-credentials`, `.netrc` |
| Token stores | Browser data, password managers |

### 8.2 What IS Sent to Cloud

| Category | Examples |
|----------|----------|
| File existence | "Environment configuration file exists" |
| File metadata | Size, modification time |
| Non-sensitive scan results | Code structure, findings, recommendations |
| Project metadata | Name, language, file count |

### 8.3 Safe Evidence Example

```json
{
  "project_name": "BibleQuest",
  "file_count": 400,
  "directory_count": 45,
  "sensitive_files_found": [
    ".env",
    "config/secrets.yml"
  ],
  "file_types": {
    ".py": 120,
    ".js": 80,
    ".html": 45,
    ".css": 30
  },
  "scan_results": {
    "findings": [...],
    "recommendations": [...]
  }
}
```

---

## 9. Communication/Transport Design

### 9.1 Transport Choice

**Selected: Outbound HTTPS Polling (Agent → Cloud)**

| Option | Security | Complexity | Selected |
|--------|----------|------------|----------|
| Agent polls cloud (outbound) | Good | Low | **YES** |
| Cloud polls agent (inbound) | Requires local port | High | No |
| WebSocket | Complex | High | No |
| Message queue | Complex | High | No |

### 9.2 Why Outbound HTTPS Polling

1. **Simple** — Standard HTTP request/response, no persistent connections
2. **Firewall/NAT friendly** — Most networks allow outbound HTTPS; no inbound ports
3. **Cross-platform** — Works identically on macOS, Windows, Linux
4. **No inbound attack surface** — User's PC exposes no ports to the network
5. **Works with ordinary HTTPS infrastructure** — Railway, Docker, nginx all compatible
6. **Supports offline devices naturally** — Agent polls when connected; cloud shows offline when not

### 9.3 Control Plane vs Agent Work Plane

**CRITICAL: Human/cloud control plane is separate from agent work plane.**

```
HUMAN/CLOUD CONTROL PLANE (user-authorized):
  POST /api/device-projects/{project_id}/scans
  → Creates governed scan request after normal user authorization
  → User must be authenticated
  → Cloud validates user authority

AGENT WORK PLANE (device-authorized):
  POST /api/agent/heartbeat
  → Device reports liveness
  → Cloud returns work queue (if any)

  GET /api/agent/jobs/next
  → Device fetches next authorized work item
  → Cloud returns only work authorized for that device

  POST /api/agent/jobs/{job_id}/started
  → Device reports work started
  → Cloud validates job belongs to this device

  POST /api/agent/jobs/{job_id}/results
  → Device submits governed results
  → Cloud validates job + device + project match

  POST /api/agent/jobs/{job_id}/failed
  → Device reports failure
  → Cloud validates job belongs to this device
```

### 9.4 API Endpoints

| Endpoint | Method | Plane | Auth | Description |
|----------|--------|-------|------|-------------|
| `/api/devices/register` | POST | Control | Registration token | Register new device |
| `/api/devices` | GET | Control | User token | List user's devices |
| `/api/devices/{id}` | GET | Control | User token | Get device details |
| `/api/devices/{id}/revoke` | POST | Control | User token | Revoke device |
| `/api/device-projects` | GET | Control | User token | List device projects |
| `/api/device-projects` | POST | Control | User token | Register project |
| `/api/device-projects/{id}/scans` | POST | Control | User token | Request scan |
| `/api/device-projects/{id}/revoke` | POST | Control | User token | Revoke project |
| `/api/agent/heartbeat` | POST | Agent | Device token | Device heartbeat + work poll |
| `/api/agent/jobs/next` | GET | Agent | Device token | Fetch next work item |
| `/api/agent/jobs/{id}` | GET | Agent | Device token | Get job details |
| `/api/agent/jobs/{id}/started` | POST | Agent | Device token | Report work started |
| `/api/agent/jobs/{id}/results` | POST | Agent | Device token | Submit results |
| `/api/agent/jobs/{id}/failed` | POST | Agent | Device token | Report failure |

### 9.5 Work Item Structure

```python
# Cloud returns to agent
class AgentJob(BaseModel):
    job_id: str
    job_type: str  # "PROJECT_SCAN" — only type for Programme I
    project_id: str  # Opaque project identifier
    scan_type: str  # "full", "incremental"
    parameters: dict  # Bounded scan parameters
    created_at: datetime
    expires_at: datetime  # Job expires if not started
```

**Critical invariant:** Work items contain narrow operation identifiers, NOT arbitrary commands.

```json
// GOOD: governed operation
{
    "job_id": "uuid",
    "job_type": "PROJECT_SCAN",
    "project_id": "uuid",
    "scan_type": "full",
    "parameters": { "branch": "main" }
}

// BAD: arbitrary command — NEVER PERMITTED
{
    "command": "cd /Users/... && some command"
}
```

---

## 10. Offline/Reconnection Design

### 10.1 Device States

```python
DEVICE_STATES = {
    "pending": "Awaiting user approval",
    "active": "Connected and authorized",
    "offline": "Not seen for > 5 minutes",
    "revoked": "User revoked access",
}
```

### 10.2 Heartbeat Mechanism

```python
HEARTBEAT_INTERVAL = 60  # seconds
OFFLINE_THRESHOLD = 300  # 5 minutes

class AgentHeartbeat:
    def __init__(self, device_id: str, api_url: str):
        self.device_id = device_id
        self.api_url = api_url
        self.last_heartbeat = None
    
    def send_heartbeat(self):
        """Send heartbeat to cloud."""
        response = requests.post(
            f"{self.api_url}/api/agent/heartbeat",
            json={
                "device_id": self.device_id,
                "timestamp": datetime.utcnow().isoformat(),
                "agent_version": get_version(),
            },
            headers={"Authorization": f"Bearer {self.token}"}
        )
        self.last_heartbeat = datetime.utcnow()
        return response.json()
```

### 10.3 Offline Scan Handling

```python
def create_scan_request(
    device_id: str,
    project_id: str,
    user: User,
    db: Session,
) -> ScanJob:
    """User requests a scan on a potentially offline device."""
    device = db.query(Device).filter(Device.device_id == device_id).first()
    
    if not device:
        raise ValueError("Device not found")
    
    if device.status == "revoked":
        raise ValueError("Device has been revoked")
    
    if device.status == "offline":
        # Create scan job with DEVICE_OFFLINE status
        job = ScanJob(
            repository_id=project_id,
            status="device_offline",
            scan_type="remote",
            requested_by=user.email,
            metadata_json={
                "device_id": device_id,
                "device_status": device.status,
                "last_seen": device.last_seen_at.isoformat() if device.last_seen_at else None,
            }
        )
        db.add(job)
        db.commit()
        return job
    
    # Device is active — create pending scan for agent to pick up
    job = ScanJob(
        repository_id=project_id,
        status="pending",
        scan_type="remote",
        requested_by=user.email,
        metadata_json={"device_id": device_id}
    )
    db.add(job)
    db.commit()
    return job


def get_next_agent_job(device_id: str, db: Session) -> ScanJob | None:
    """Agent polls for next available work item."""
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device or device.status != "active":
        return None
    
    # Find pending scan job for this device
    job = db.query(ScanJob).filter(
        ScanJob.status == "pending",
        ScanJob.scan_type == "remote",
        ScanJob.metadata_json["device_id"].as_string() == device_id,
    ).first()
    
    return job
```

---

## 11. Provenance Design

**Note:** Detailed scan provenance is deferred to LA4 when scanning is introduced. LA1 implements only the device trust domain.

### 11.1 Remote Scan Provenance

```json
{
    "scan_id": "uuid",
    "device_id": "device_uuid",
    "device_name": "David's MacBook",
    "device_platform": "macos",
    "agent_version": "1.0.0",
    "project_id": "project_uuid",
    "project_name": "BibleQuest",
    "repository_id": "repo_uuid",
    "started_at": "2026-08-27T10:30:00Z",
    "completed_at": "2026-08-27T10:32:15Z",
    "provenance": "LIVE_EVOSIA_EVIDENCE",
    "scan_type": "remote_local_agent",
    "evidence_source": "device_local_scan",
    "target_immutability_verified": true
}
```

### 11.2 Provenance Properties

| Property | Value |
|----------|-------|
| Device identification | Always included |
| Project identification | Always included |
| Agent version | Always included |
| Live vs sample | Distinguished clearly |
| Immutability proof | Before/after hash comparison |

---

## 12. Audit/Event Design

### 12.1 Journal Event Types

**LA1 Scope:**

| Event Type | Description |
|------------|-------------|
| `device.registered` | New device registered |
| `device.connected` | Device came online |
| `device.disconnected` | Device went offline |
| `device.revoked` | Device access revoked |

**Deferred to LA3+:**

| Event Type | Description |
|------------|-------------|
| `project.registered` | New project registered |
| `project.access_revoked` | Project access revoked |

**Deferred to LA4+:**

| Event Type | Description |
|------------|-------------|
| `scan.requested` | Scan requested by user |
| `scan.started` | Scan started on device |
| `scan.completed` | Scan completed successfully |
| `scan.failed` | Scan failed |

### 12.2 Journal Event Example

```json
{
    "event_id": "evt_uuid",
    "timestamp": "2026-08-27T10:30:00Z",
    "event_type": "device.registered",
    "stage": "device_management",
    "actor": "user@example.com",
    "payload": {
        "device_id": "device_uuid",
        "device_name": "David's MacBook",
        "platform": "macos",
        "agent_version": "1.0.0",
        "capabilities": ["read", "scan"]
    },
    "payload_sha256": "hash_of_payload"
}
```

---

## 13. Proposed Data Model Changes

### 13.1 New Tables (LA1)

| Table | Purpose |
|-------|---------|
| `devices` | Device identity and status |

**Note:** `device_projects` table is deferred to LA3 when project-root authority and filesystem isolation are introduced.

### 13.2 Modified Tables

| Table | Changes |
|-------|---------|
| `repositories` | Add `provider="local_agent"` support (LA3) |
| `scan_jobs` | Add `scan_type="remote"` support |
| `journal_events` | Add device/project event types |

### 13.3 Migration Strategy

```python
# 005_local_agent_devices.py

def upgrade():
    # Create devices table
    op.create_table(
        'devices',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('device_id', sa.String(128), unique=True, nullable=False),
        sa.Column('device_name', sa.String(255), nullable=False),
        sa.Column('platform', sa.String(50), nullable=False),
        sa.Column('agent_version', sa.String(50), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('status', sa.String(30), default='pending'),
        sa.Column('credential_hash', sa.String(255), nullable=False),
        sa.Column('last_seen_at', sa.DateTime),
        sa.Column('capabilities', sa.JSON, default=list),
        sa.Column('registered_at', sa.DateTime),
        sa.Column('revoked_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),
    )
```

---

## 14. Proposed API Contracts

### 14.1 Device Registration (Control Plane)

```python
# POST /api/devices/register
class DeviceRegisterRequest(BaseModel):
    registration_token: str  # Single-use, short-lived token
    device_name: str  # User-provided or hostname-derived
    platform: str  # "macos", "windows", "linux"
    agent_version: str

class DeviceRegisterResponse(BaseModel):
    device_id: str
    credential: str  # JWT device credential
    device_status: str
```

### 14.2 Device Management (Control Plane)

```python
# GET /api/devices
class DeviceResponse(BaseModel):
    id: str
    device_id: str
    device_name: str
    platform: str
    agent_version: str
    status: str
    last_seen_at: datetime | None
    capabilities: list[str]
    registered_at: datetime
```

### 14.3 Agent Work Plane

```python
# POST /api/agent/heartbeat
class HeartbeatRequest(BaseModel):
    timestamp: str
    agent_version: str

class HeartbeatResponse(BaseModel):
    status: str
    work_available: bool
    jobs: list[AgentJob]  # If work available

# GET /api/agent/jobs/next
class AgentJob(BaseModel):
    job_id: str
    job_type: str  # "PROJECT_SCAN" — only type for Programme I
    project_id: str  # Opaque project identifier
    scan_type: str  # "full", "incremental"
    parameters: dict  # Bounded scan parameters
    created_at: datetime
    expires_at: datetime

# POST /api/agent/jobs/{id}/started
class JobStartedRequest(BaseModel):
    agent_version: str

# POST /api/agent/jobs/{id}/results
class JobResultsRequest(BaseModel):
    status: str  # "completed", "failed"
    results: dict  # Governed scan results
    duration_seconds: float

# POST /api/agent/jobs/{id}/failed
class JobFailedRequest(BaseModel):
    error_message: str
    error_classification: str
```

---

## 15. Local Agent Package Structure

### 15.1 Proposed Layout

```
enterprise/
    agents/
        __init__.py
        local_agent/
            __init__.py
            __main__.py      # python -m evosia_agent entry point
            agent.py         # Main agent class (LA2)
            auth.py          # Authentication (LA2)
            heartbeat.py     # Heartbeat mechanism (LA2)
            scanner.py       # Local scanning (LA4)
            fs_utils.py      # Filesystem utilities (LA3)
            path_validator.py # Path validation (LA3)
            config.py        # Agent configuration (LA2)
            version.py       # Version info (LA2)
```

### 15.2 Milestone Mapping

| File | Milestone | Purpose |
|------|-----------|---------|
| `__main__.py` | LA2 | Entry point |
| `agent.py` | LA2 | Main agent class |
| `auth.py` | LA2 | Authentication |
| `heartbeat.py` | LA2 | Heartbeat mechanism |
| `config.py` | LA2 | Agent configuration |
| `version.py` | LA2 | Version info |
| `fs_utils.py` | LA3 | Filesystem utilities |
| `path_validator.py` | LA3 | Path validation |
| `scanner.py` | LA4 | Local scanning |

### 15.2 Entry Point

```python
# enterprise/agents/local_agent/__main__.py
"""Entry point for Local Agent: python -m evosia_agent"""

def main():
    """Start the EVOSIA Local Agent."""
    from .agent import LocalAgent
    agent = LocalAgent()
    agent.run()

if __name__ == "__main__":
    main()
```

### 15.3 pyproject.toml Addition

```toml
[project.scripts]
evosia-agent = "enterprise.agents.local_agent.__main__:main"
```

---

## 16. macOS Strategy

### 16.1 Installation

```bash
# Install via pip
pip install evosia-runtime[agent]

# Or install from source
pip install -e ".[enterprise]"
```

### 16.2 Startup

```bash
# Start agent
python -m evosia_agent

# Or using installed script
evosia-agent
```

### 16.3 Configuration

```bash
# Agent config stored at
~/.config/evosia-agent/config.json

# Contains:
# - device_id (UUID)
# - encrypted JWT token
# - registered projects
```

### 16.4 Future Distribution

- Phase 1: `python -m evosia_agent` (current)
- Phase 2: `EVOSIA Agent.app` (macOS app bundle)
- Phase 3: Notarized macOS app

---

## 17. Windows Strategy

### 17.1 Installation

```powershell
# Install via pip
pip install evosia-runtime[agent]

# Or install from source
pip install -e ".[enterprise]"
```

### 17.2 Startup

```powershell
# Start agent
python -m evosia_agent

# Or using installed script
evosia-agent
```

### 17.3 Configuration

```powershell
# Agent config stored at
%APPDATA%\evosia-agent\config.json

# Or
~/.config/evosia-agent/config.json
```

### 17.4 Path Handling

```python
# Use pathlib for cross-platform paths
from pathlib import Path

# Windows paths work with pathlib
project_root = Path("C:\\Users\\David\\Projects\\BibleQuest")
```

### 17.5 Future Distribution

- Phase 1: `python -m evosia_agent` (current)
- Phase 2: `EVOSIA Agent Setup.exe` (NSIS installer)
- Phase 3: `EVOSIA Agent.msi` (Windows Installer)

---

## 18. Threat Model

### 18.1 Trust Boundaries

| Boundary | Trust Level |
|----------|-------------|
| EVOSIA Cloud | High — controls device/project registry |
| Local Agent | Medium — runs on user's machine |
| Project Files | Low — untrusted code |
| Network | Medium — outbound HTTPS only |

### 18.2 Threats and Mitigations

| Threat | Mitigation |
|--------|------------|
| **Stolen device credential** | Credential scoped to device_id; revocable by user; expires after 30 days |
| **Replayed bootstrap token** | Single-use, expires in 10 minutes; cannot be reused |
| **Brute-force registration code** | Rate limiting on registration endpoint; token format not guessable |
| **Revoked device continuing to poll** | Device status checked server-side on every request; revoked devices rejected |
| **Device claiming another device's job** | Jobs bound to device_id; server validates job-device assignment |
| **Device submitting results for another job** | Server validates job + device + project match on result submission |
| **Malicious cloud job payload** | Only predefined operation types (PROJECT_SCAN); no arbitrary commands |
| **Command-injection payload** | No execute endpoint; governed operations only; parameters validated |
| **Stale/offline device** | Heartbeat mechanism; offline threshold; jobs expire if not started |
| **Local malware reading agent credential** | Credential file permissions 0600; credential never logged; HTTPS only |
| **Agent compromise** | User controls when agent runs; device can be revoked; minimal attack surface |
| **Cloud compromise** | Device access can be revoked; provenance tracks all operations |

### 18.3 Security Properties

| Property | Enforced |
|----------|----------|
| Target project not modified | YES — read-only scans |
| No unrestricted filesystem access | YES — path validation |
| No arbitrary cloud commands | YES — governed operations only |
| Access limited to registered roots | YES — path traversal protection |
| Device access revocable | YES — device status check |
| Secrets not transmitted | YES — sensitive file policy |
| Provenance identifies device/project | YES — scan metadata |
| Existing authority boundaries intact | YES — no execution authority |
| Gemini explanation-only | YES — unchanged |
| No autonomous execution | YES — no execute/merge/deploy |

---

## 19. Authority Invariants

These must remain true throughout Programme I:

| Invariant | Status |
|-----------|--------|
| A. Target project not modified | ENFORCED |
| B. Cloud does not receive unrestricted filesystem access | ENFORCED |
| C. Local Agent cannot execute arbitrary cloud commands | ENFORCED |
| D. Access limited to explicitly registered project roots | ENFORCED |
| E. Device access can be revoked | ENFORCED |
| F. Secrets not transmitted as scan evidence | ENFORCED |
| G. Provenance identifies originating device/project | ENFORCED |
| H. Existing EVOSIA authority boundaries remain intact | ENFORCED |
| I. Gemini remains explanation-only | ENFORCED |
| J. No autonomous execution, merge or deployment capability | ENFORCED |
| K. Human/user authority creates governed work | ENFORCED |
| L. Agent credentials authenticate a device; they do not grant human authority | ENFORCED |
| M. Agent may execute only predefined read-only operation types | ENFORCED |
| N. Agent cannot claim jobs belonging to another device | ENFORCED |
| O. Result submission must match device + project + job assignment | ENFORCED |

---

## 20. Test Strategy

### 20.1 Unit Tests (LA1 Scope)

| Test | Purpose |
|------|---------|
| Device registration (bootstrap token) | Verify single-use token exchange |
| Device authentication (device credential) | Verify JWT token validation |
| Device revocation | Verify revoked device rejected |
| Device status transitions | Verify pending → active → revoked |
| Device heartbeat | Verify identity and liveness |
| Capability model | Verify capabilities stored correctly |
| Audit event creation | Verify journal events for device operations |
| Authority invariants | Verify no execution capability |

### 20.2 Integration Tests (LA1 Scope)

| Test | Purpose |
|------|---------|
| Bootstrap registration flow | End-to-end device setup |
| Revocation flow | Verify device revocation |

### 20.3 Security Tests (LA1 Scope)

| Test | Purpose |
|------|---------|
| Replayed bootstrap token | Verify single-use enforcement |
| Revoked device authentication | Verify revoked device rejected |
| Credential theft | Verify device can be revoked |
| Token manipulation | Verify JWT validation |

### 20.4 Future Tests (LA2+)

| Test | Purpose | Milestone |
|------|---------|-----------|
| Path traversal attacks | Verify all traversal attempts blocked | LA3 |
| Symlink attacks | Verify symlink escapes blocked | LA3 |
| Secret exfiltration | Verify no secrets in scan results | LA3 |
| Scan orchestration | Verify scan request flow | LA4 |
| Offline handling | Verify graceful degradation | LA4 |
| Provenance tracking | Verify device/project attribution | LA4 |

---

## 21. Risks/Open Questions

### 21.1 Open Questions

| Question | Impact | Recommended Answer |
|----------|--------|-------------------|
| Should agent credential refresh be automatic? | UX | Re-registration required (simpler, more secure) |
| How to handle agent updates? | Distribution | Agent reports version, cloud warns if outdated |
| Should we support agent behind corporate proxy? | Network | Outbound HTTPS should work; document proxy settings |
| How to handle multiple users on same device? | Multi-user | Each user gets separate device_id |
| Should agent work offline? | Availability | Yes, queue scans until reconnected |
| How long should bootstrap tokens be valid? | Security | 10 minutes; single-use |

### 21.2 Risks

| Risk | Mitigation |
|------|------------|
| Agent becomes attack surface | Device registration requires user approval |
| User installs agent on shared computer | Document security implications |
| Agent credential stolen | Token scoped to device, revocable |
| Cloud API compromised | Device access can be revoked |
| Bootstrap token intercepted | Single-use, expires in 10 minutes |

---

## 22. Proposed LA1 Scope

### 22.1 LA1 — Device Domain & Contracts

**Implement:**
- Device model
- Device registration/bootstrap model
- Device credential model/service
- Device capability representation
- Device status
- Heartbeat contract (if needed for identity tests)
- Revocation
- Authentication/revocation tests
- Audit events
- Migration

**NO:**
- Filesystem access
- Project registration
- DeviceProject implementation (unless minimal placeholder strictly required by existing schema dependency)
- Scanning
- Local Agent code

**Deliverables:**
- `enterprise/models/__init__.py` — Device model (DeviceProject deferred to LA3)
- `enterprise/schemas/__init__.py` — Device schemas
- `enterprise/routers/devices.py` — Device API endpoints (control plane)
- `enterprise/services/device_service.py` — Device business logic
- `enterprise/services/device_auth.py` — Device authentication/bootstrap
- `enterprise/migrations/versions/005_local_agent_devices.py` — Migration
- `tests/test_devices.py` — Device tests

**Tests:**
- Device registration (bootstrap token flow)
- Device authentication (device credential)
- Device revocation
- Device status (pending, active, offline, revoked)
- Capability model
- Authority invariants (A-O)
- Audit event creation

**Commit. Run tests. STOP.**

---

**STOP. This is LA0 — documentation/architecture only. No implementation.**
