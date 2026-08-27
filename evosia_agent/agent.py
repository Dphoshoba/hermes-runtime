"""Agent — main Local Agent loop and first-run experience."""

from __future__ import annotations

import logging
import signal
import sys
import threading
from datetime import datetime, timezone
from typing import NoReturn

from .api_client import ApiClient, ApiError
from .config import AgentConfig, HEARTBEAT_INTERVAL_SECONDS
from .credential_store import CredentialStore, DeviceCredential
from .device_identity import DeviceIdentity
from .heartbeat import HeartbeatLoop
from .version import AGENT_VERSION

logger = logging.getLogger(__name__)


class AgentState:
    """Agent runtime state."""

    UNREGISTERED = "unregistered"
    CONNECTING = "connecting"
    REGISTERED = "registered"
    CONNECTED = "connected"
    REVOKED = "revoked"
    AUTH_REQUIRED = "auth_required"
    STOPPED = "stopped"


class LocalAgent:
    """EVOSIA Local Agent — LA2 implementation.

    Handles:
    - First-run detection and registration
    - Device identity and credential management
    - Heartbeat loop with retry/backoff
    - Graceful shutdown on SIGINT/SIGTERM
    """

    def __init__(self, config: AgentConfig | None = None) -> None:
        self._config = config or AgentConfig()
        self._store = CredentialStore(self._config.data_dir)
        self._state = AgentState.UNREGISTERED
        self._heartbeat: HeartbeatLoop | None = None
        self._shutdown_event = threading.Event()

    def run(self, bootstrap_token: str | None = None) -> None:
        """Run the agent. Main entry point.

        Args:
            bootstrap_token: If provided, register with this token.
                           If None and not registered, prompt for token.
        """
        self._setup_signal_handlers()
        self._print_banner()

        if not self._store.is_registered:
            if bootstrap_token:
                self._register(bootstrap_token)
            else:
                self._interactive_register()
        else:
            self._load_existing_credential()

        if self._state in (AgentState.REGISTERED, AgentState.CONNECTED):
            self._run_heartbeat_loop()
        elif self._state == AgentState.REVOKED:
            self._print_revoked_message()
        elif self._state == AgentState.AUTH_REQUIRED:
            self._print_auth_required_message()

        self._state = AgentState.STOPPED
        logger.info("Agent stopped")

    def _setup_signal_handlers(self) -> None:
        """Register handlers for graceful shutdown."""
        def _shutdown_handler(signum: int, frame: object) -> None:
            logger.info("Received signal %d — shutting down", signum)
            self._shutdown_event.set()
            if self._heartbeat:
                self._heartbeat.stop()

        try:
            signal.signal(signal.SIGINT, _shutdown_handler)
            signal.signal(signal.SIGTERM, _shutdown_handler)
        except (OSError, AttributeError):
            # Windows or unsupported platform
            pass

    def _print_banner(self) -> None:
        """Print agent startup banner."""
        print()
        print("EVOSIA Local Agent")
        print("-" * 40)
        print(f"Version: {AGENT_VERSION}")
        print(f"Cloud: {self._config.cloud_url}")
        print()

    def _interactive_register(self) -> None:
        """Prompt user for bootstrap token and register."""
        print("This computer is not registered with EVOSIA.")
        print()
        print("Enter the one-time device registration token")
        print("shown in your EVOSIA dashboard:")
        print()
        token = input("> ").strip()
        print()

        if not token:
            print("No token provided. Exiting.")
            return

        self._register(token)

    def _register(self, bootstrap_token: str) -> None:
        """Register device with bootstrap token."""
        self._state = AgentState.CONNECTING
        print("Registering device...")

        identity = DeviceIdentity.collect()
        api = ApiClient(self._config.cloud_url)

        try:
            response = api.exchange_bootstrap_token(
                bootstrap_token=bootstrap_token,
                device_token="",  # Not used in exchange
            )

            device_id = response.get("device_id")
            credential = response.get("access_token")

            if not device_id or not credential:
                print("Registration failed: invalid server response")
                self._state = AgentState.UNREGISTERED
                return

            # Store credential
            cred = DeviceCredential(
                device_id=device_id,
                device_name=identity.device_name,
                credential=credential,
                cloud_url=self._config.cloud_url,
            )
            self._store.save(cred)

            self._state = AgentState.REGISTERED
            print("Device registered successfully.")
            print()
            print(f"Device: {identity.device_name}")
            print(f"Status: Connected")
            print(f"Authority: Device connection only")
            print()
            print("No project folders have been authorised.")
            print()

        except ApiError as exc:
            if exc.status_code == 401:
                print(f"Registration failed: {exc.detail}")
                self._state = AgentState.AUTH_REQUIRED
            else:
                print(f"Registration failed: {exc.detail}")
                self._state = AgentState.UNREGISTERED
        except Exception as exc:
            print(f"Registration failed: connection error")
            logger.error("Registration error: %s", exc)
            self._state = AgentState.UNREGISTERED

    def _load_existing_credential(self) -> None:
        """Load existing device credential."""
        try:
            cred = self._store.load()
            self._state = AgentState.REGISTERED
            print(f"Device: {cred.device_name}")
            print(f"Device ID: {cred.device_id[:16]}...")
            print(f"Status: Connected")
            print(f"Authority: Device connection only")
            print()
        except FileNotFoundError:
            print("Credential store corrupted. Please re-register.")
            self._state = AgentState.UNREGISTERED

    def _run_heartbeat_loop(self) -> None:
        """Start heartbeat loop and block until stopped."""
        cred = self._store.load()
        api = ApiClient(self._config.cloud_url)

        def _on_job_received(job: dict) -> None:
            """Handle received job from heartbeat polling."""
            logger.info("Received job %s — executing", job.get("id"))
            try:
                execute_job(job, self._config, cred)
            except Exception as exc:
                logger.error("Job execution failed: %s", exc)

        self._heartbeat = HeartbeatLoop(
            api_client=api,
            device_id=cred.device_id,
            device_credential=cred.credential,
            agent_version=AGENT_VERSION,
            interval_seconds=HEARTBEAT_INTERVAL_SECONDS,
            on_revoked=self._on_revoked,
            on_expired=self._on_expired,
            on_job_received=_on_job_received,
        )

        # Run heartbeat in this thread (blocks until stopped)
        self._heartbeat.start()

    def _on_revoked(self) -> None:
        """Handle device revocation."""
        self._state = AgentState.REVOKED
        self._store.delete()
        self._print_revoked_message()

    def _on_expired(self) -> None:
        """Handle credential expiry."""
        self._state = AgentState.AUTH_REQUIRED
        self._store.delete()
        self._print_auth_required_message()

    def _print_revoked_message(self) -> None:
        """Print revocation message."""
        print()
        print("This EVOSIA device has been revoked.")
        print("Register this computer again from EVOSIA to reconnect.")
        print()

    def _print_auth_required_message(self) -> None:
        """Print auth required message."""
        print()
        print("Device credential has expired or is invalid.")
        print("Please re-register this computer from EVOSIA.")
        print()


def status() -> None:
    """Display agent status."""
    config = AgentConfig()
    store = CredentialStore(config.data_dir)

    print()
    print("EVOSIA Local Agent")
    print("-" * 40)

    if not store.is_registered:
        print("Status: Not registered")
        print()
        print("Run 'python -m evosia_agent' to register.")
        print()
        return

    try:
        cred = store.load()
        print(f"Device: {cred.device_name}")
        print(f"Device ID: {cred.device_id[:16]}...")
        print(f"Cloud: {cred.cloud_url}")
        print(f"Agent version: {AGENT_VERSION}")
        print(f"Authority: Device connection only")
        print(f"Projects authorised: None")
        print(f"Project access: Not enabled in LA2")
        print()
    except FileNotFoundError:
        print("Status: Credential store corrupted")
        print("Run 'python -m evosia_agent' to re-register.")


def logout() -> None:
    """Remove local device credential."""
    config = AgentConfig()
    store = CredentialStore(config.data_dir)

    if not store.is_registered:
        print("No device registered.")
        return

    try:
        cred = store.load()
        store.delete()
        print(f"Logged out from device: {cred.device_name}")
        print("Local credential removed.")
        print("The device is still registered in EVOSIA Cloud.")
        print("To fully revoke, use the EVOSIA dashboard.")
    except FileNotFoundError:
        store.delete()
        print("Credential store cleaned up.")


def project_add(path: str) -> None:
    """Add an explicitly authorized project."""
    from pathlib import Path
    from .project_registry import ProjectRegistry
    from .path_validation import (
        validate_project_root,
        has_symlink_escape,
        is_sensitive_path,
    )
    from .project_api import ProjectApiClient, ApiError

    config = AgentConfig()
    store = CredentialStore(config.data_dir)

    if not store.is_registered:
        print("Device not registered. Run 'python -m evosia_agent' first.")
        return

    try:
        cred = store.load()
    except FileNotFoundError:
        print("Credential store corrupted. Please re-register.")
        return

    # Validate and canonicalize path
    try:
        canonical = validate_project_root(path)
    except ValueError as exc:
        print(f"Invalid project path: {exc}")
        return

    # Check for symlink escapes (fail-closed)
    from .path_validation import SymlinkStatus
    symlink_results = has_symlink_escape(canonical)
    problems = [r for r in symlink_results if r.status != SymlinkStatus.SAFE_INTERNAL]
    if problems:
        print("Project contains problematic symlinks:")
        for r in problems:
            if r.status == SymlinkStatus.ESCAPES_ROOT:
                print(f"  ESCAPES ROOT: {r.path}")
            elif r.status == SymlinkStatus.BROKEN_OR_UNRESOLVABLE:
                print(f"  BROKEN/UNRESOLVABLE: {r.path}")
        print("Registration denied.")
        return

    display_name = canonical.name
    print()
    print("Project:")
    print(f"  {display_name}")
    print()
    print("Location:")
    print(f"  {canonical}")
    print()
    print("Authority:")
    print(f"  Review only")
    print()
    print("EVOSIA will be able to inspect this project only after future scan")
    print("functionality is separately authorized.")
    print("No files have been changed.")
    print()

    # Register with cloud
    api = ProjectApiClient(config.cloud_url, cred.credential)
    try:
        # Step 1: Request project authorization token (using device credential)
        auth_response = api.request_project_authorization_token(cred.device_id)
        project_auth_token = auth_response.get("project_authorization_token")

        if not project_auth_token:
            print("Failed to get project authorization token.")
            print("Project registered locally only.")
            cloud_project_id = f"local_{display_name}"
        else:
            # Step 2: Register project with authorization token
            response = api.register_project(
                device_id=cred.device_id,
                display_name=display_name,
                local_root_fingerprint="",  # Will be computed locally
                project_authorization_token=project_auth_token,
            )
            cloud_project_id = response.get("project_id", response.get("id", ""))

    except ApiError as exc:
        print(f"Cloud registration failed: {exc.detail}")
        print("Project registered locally only.")
        cloud_project_id = f"local_{display_name}"

    # Store locally
    registry = ProjectRegistry(config.data_dir)
    registry.add(
        cloud_project_id=cloud_project_id,
        canonical_local_root=canonical,
        display_name=display_name,
    )

    print("Project registered successfully.")
    print()


def project_list() -> None:
    """List all authorized projects."""
    from .project_registry import ProjectRegistry

    config = AgentConfig()
    registry = ProjectRegistry(config.data_dir)
    projects = registry.projects

    print()
    print("EVOSIA Local Agent")
    print("-" * 40)
    print()

    if not projects:
        print("No projects registered.")
        print()
        print("Use 'python -m evosia_agent project add <path>' to register a project.")
        print()
        return

    print("Authorised projects:")
    print()

    for i, proj in enumerate(projects, 1):
        from pathlib import Path
        display_path = Path(proj.canonical_local_root).name
        print(f"{i}. {proj.display_name}")
        print(f"   Path: {display_path}")
        print(f"   Authority: {proj.authority.replace('_', ' ').title()}")
        print(f"   Status: {proj.status.title()}")
        print()

    print(f"Total: {len(projects)} project(s)")
    print()


def project_remove(project_id: str) -> None:
    """Remove a project from local registry."""
    from .project_registry import ProjectRegistry

    config = AgentConfig()
    registry = ProjectRegistry(config.data_dir)

    proj = registry.get(project_id)
    if not proj:
        # Try to find by display name
        for p in registry.projects:
            if p.display_name.lower() == project_id.lower():
                proj = p
                project_id = p.cloud_project_id
                break

    if not proj:
        print(f"Project not found: {project_id}")
        return

    if registry.remove(project_id):
        print(f"Project removed: {proj.display_name}")
        print("Cloud registration unchanged. Use EVOSIA dashboard to revoke.")
    else:
        print(f"Failed to remove project.")


# ---------------------------------------------------------------------------
# LA4: Job Execution
# ---------------------------------------------------------------------------

def execute_job(job: dict, config: AgentConfig, credential: DeviceCredential) -> None:
    """Execute a governed PROJECT_SCAN job.

    This is the ONLY way the agent performs work.
    It must NEVER create jobs — only fetch and perform predefined work.
    """
    from .project_registry import ProjectRegistry
    from .scanner import scan_project, ScanLimits
    from pathlib import Path

    job_id = job.get("id")
    device_project_id = job.get("device_project_id")
    operation_type = job.get("operation_type")

    if operation_type != "PROJECT_SCAN":
        logger.warning("Unknown operation type: %s — skipping", operation_type)
        _report_job_failed(config, credential, job_id, f"Unknown operation type: {operation_type}")
        return

    # Map cloud project ID to local project root
    registry = ProjectRegistry(config.data_dir)
    local_project = registry.get(device_project_id)
    if not local_project:
        logger.warning("Project %s not found locally — skipping", device_project_id)
        _report_job_failed(config, credential, job_id, "Project not found locally")
        return

    if local_project.status != "active":
        logger.warning("Project %s is %s — skipping", device_project_id, local_project.status)
        _report_job_failed(config, credential, job_id, f"Project is {local_project.status}")
        return

    project_root = Path(local_project.canonical_local_root)
    if not project_root.exists():
        logger.warning("Project root does not exist: %s", project_root)
        _report_job_failed(config, credential, job_id, "Project root does not exist")
        return

    # Mark job as started
    api = ApiClient(config.cloud_url)
    try:
        api.mark_job_started(job_id, credential.credential, AGENT_VERSION)
    except ApiError as exc:
        logger.error("Failed to mark job started: %s", exc.detail)
        return

    # Perform bounded read-only scan
    start_time = datetime.now(timezone.utc)
    try:
        result = scan_project(project_root, ScanLimits())
    except Exception as exc:
        logger.error("Scan failed: %s", exc)
        _report_job_failed(config, credential, job_id, f"Scan failed: {exc}")
        return

    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()

    # Build evidence
    evidence = {
        "job_id": job_id,
        "device_id": credential.device_id,
        "device_project_id": device_project_id,
        "project_display_name": local_project.display_name,
        "agent_version": AGENT_VERSION,
        "started_at": start_time.isoformat(),
        "completed_at": end_time.isoformat(),
        "file_count": result.file_count,
        "languages": result.languages,
        "project_structure_summary": result.project_structure_summary,
        "git_metadata": result.git_metadata,
        "findings": result.findings,
        "truncated": result.truncated,
        "limits": result.limits,
        "sensitive_files_found": result.sensitive_files_found,
        "total_bytes_read": result.total_bytes_read,
        "provenance": "LIVE_EVOSIA_EVIDENCE",
        "evidence_source": "device_local_scan",
    }

    # Submit results
    try:
        api.submit_job_results(job_id, credential.credential, evidence, duration)
        logger.info("Job %s completed successfully", job_id)
    except ApiError as exc:
        logger.error("Failed to submit results: %s", exc.detail)


def _report_job_failed(
    config: AgentConfig, credential: DeviceCredential,
    job_id: str, reason: str,
) -> None:
    """Report job failure to cloud."""
    api = ApiClient(config.cloud_url)
    try:
        api.report_job_failed(job_id, credential.credential, reason)
    except ApiError as exc:
        logger.error("Failed to report job failure: %s", exc.detail)
