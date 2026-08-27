"""Agent — main Local Agent loop and first-run experience."""

from __future__ import annotations

import logging
import signal
import sys
import threading
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

        self._heartbeat = HeartbeatLoop(
            api_client=api,
            device_id=cred.device_id,
            device_credential=cred.credential,
            agent_version=AGENT_VERSION,
            interval_seconds=HEARTBEAT_INTERVAL_SECONDS,
            on_revoked=self._on_revoked,
            on_expired=self._on_expired,
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
