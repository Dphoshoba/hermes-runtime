"""Desktop tray application — EVOSIA Connector customer-facing UI."""

from __future__ import annotations

import logging
import sys
import threading
import webbrowser
from typing import Callable

from .state_machine import ConnectorState, get_initial_state

logger = logging.getLogger(__name__)

# Product identity
PRODUCT_NAME = "EVOSIA Connector"
PUBLISHER = "Echoes & Visions"


class ConnectorApp:
    """Desktop tray application for EVOSIA Connector.

    Provides system tray icon, context menu, and state management.
    Uses tkinter for UI and pystray for system tray integration.
    """

    def __init__(self) -> None:
        self._state = ConnectorState.STARTING
        self._state_lock = threading.Lock()
        self._projects: list[dict] = []
        self._device_name: str = "Unknown"
        self._cloud_url: str = ""
        self._version: str = "0.1.0"
        self._last_heartbeat: str = "Never"
        self._last_review_status: str = "None"
        self._tray = None
        self._window = None
        self._polling = False
        self._poll_thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the desktop tray application."""
        try:
            self._detect_environment()
            self._initialize_state()
            self._create_tray()
            self._start_background_tasks()
            logger.info("Connector started")
        except Exception as exc:
            logger.error("Failed to start connector: %s", exc)
            self._transition(ConnectorState.ERROR)

    def _detect_environment(self) -> None:
        """Detect runtime environment."""
        from .config import ConnectorConfig
        config = ConnectorConfig()
        self._cloud_url = config.cloud_url
        self._version = getattr(config, "version", "0.1.0")

    def _initialize_state(self) -> None:
        """Initialize state from stored credentials and projects."""
        try:
            from evosia_agent.credential_store import CredentialStore
            from .config import ConnectorConfig

            config = ConnectorConfig()
            store = CredentialStore(config.data_dir)
            credential = store.load()

            has_credential = credential is not None

            # Load projects
            from evosia_agent.project_registry import ProjectRegistry
            registry = ProjectRegistry(config.data_dir)
            self._projects = registry.list_projects()

            has_projects = len(self._projects) > 0

            if has_credential:
                self._device_name = credential.device_name

            initial = get_initial_state(has_credential, has_projects)
            self._transition(initial)

        except Exception as exc:
            logger.warning("Failed to initialize state: %s", exc)
            self._transition(ConnectorState.NOT_CONNECTED)

    def _transition(self, new_state: ConnectorState) -> None:
        """Thread-safe state transition."""
        with self._state_lock:
            from .state_machine import can_transition
            if can_transition(self._state, new_state):
                old_state = self._state
                self._state = new_state
                logger.info("State: %s -> %s", old_state.value, new_state.value)
                self._update_tray_menu()
            else:
                logger.warning("Invalid transition: %s -> %s", self._state.value, new_state.value)

    def _create_tray(self) -> None:
        """Create system tray icon."""
        try:
            import pystray
            from PIL import Image, ImageDraw

            # Create a simple icon
            icon = self._create_icon_image()

            menu = self._build_menu()

            self._tray = pystray.Icon(
                name="EVOSIA Connector",
                icon=icon,
                title=f"{PRODUCT_NAME} - {self._get_status_text()}",
                menu=menu,
            )

            # Start tray in background thread
            threading.Thread(target=self._tray.run, daemon=True).start()

        except ImportError:
            logger.warning("pystray not available, using tkinter only")
            self._create_tkinter_window()

    def _create_icon_image(self):
        """Create a simple tray icon image."""
        try:
            from PIL import Image, ImageDraw

            # Create a 64x64 icon with EVOSIA branding
            image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)

            # Draw a circle (connection indicator)
            if self._state == ConnectorState.CONNECTED or self._state == ConnectorState.READY:
                color = (76, 175, 80)  # Green
            elif self._state == ConnectorState.NOT_CONNECTED:
                color = (244, 67, 54)  # Red
            else:
                color = (255, 152, 0)  # Orange

            draw.ellipse([8, 8, 56, 56], fill=color)
            draw.text((20, 20), "E", fill=(255, 255, 255))

            return image

        except ImportError:
            # Fallback to default icon
            return None

    def _build_menu(self):
        """Build context menu based on current state."""
        try:
            import pystray

            items = []

            # State-dependent actions
            if self._state == ConnectorState.NOT_CONNECTED:
                items.append(pystray.MenuItem(
                    "Connect this computer",
                    self._on_connect,
                    enabled=True,
                ))
            elif self._state == ConnectorState.CONNECTED:
                items.append(pystray.MenuItem(
                    "Add Project",
                    self._on_add_project,
                    enabled=True,
                ))
            elif self._state == ConnectorState.READY:
                items.append(pystray.MenuItem(
                    "Review Project",
                    self._on_review_project,
                    enabled=True,
                ))
                items.append(pystray.MenuItem(
                    "Add Project",
                    self._on_add_project,
                    enabled=True,
                ))
            elif self._state == ConnectorState.REVIEW_QUEUED:
                items.append(pystray.MenuItem(
                    "Review queued...",
                    enabled=False,
                ))
            elif self._state == ConnectorState.REVIEW_IN_PROGRESS:
                items.append(pystray.MenuItem(
                    "Review in progress...",
                    enabled=False,
                ))
            elif self._state == ConnectorState.REVIEW_COMPLETE:
                items.append(pystray.MenuItem(
                    "Review complete",
                    enabled=False,
                ))
                items.append(pystray.MenuItem(
                    "Open EVOSIA",
                    self._on_open_evosia,
                    enabled=True,
                ))
            elif self._state == ConnectorState.REVIEW_FAILED:
                items.append(pystray.MenuItem(
                    "Review failed - try again",
                    self._on_review_project,
                    enabled=True,
                ))

            # Common items
            items.append(pystray.Menu.SEPARATOR)
            items.append(pystray.MenuItem(
                "Open EVOSIA",
                self._on_open_evosia,
                enabled=True,
            ))
            items.append(pystray.MenuItem(
                "Diagnostics",
                self._on_diagnostics,
                enabled=True,
            ))
            items.append(pystray.Menu.SEPARATOR)
            items.append(pystray.MenuItem(
                "Exit",
                self._on_exit,
                enabled=True,
            ))

            return pystray.Menu(*items)

        except ImportError:
            return None

    def _get_status_text(self) -> str:
        """Get human-readable status text."""
        status_map = {
            ConnectorState.STARTING: "Starting...",
            ConnectorState.NOT_CONNECTED: "Not connected",
            ConnectorState.CONNECTING: "Connecting...",
            ConnectorState.CONNECTED: "Connected - No projects",
            ConnectorState.NO_PROJECTS: "Connected - No projects",
            ConnectorState.READY: "Ready",
            ConnectorState.REVIEW_QUEUED: "Review queued",
            ConnectorState.REVIEW_IN_PROGRESS: "Review in progress",
            ConnectorState.REVIEW_COMPLETE: "Review complete",
            ConnectorState.REVIEW_FAILED: "Review failed",
            ConnectorState.OFFLINE: "Offline",
            ConnectorState.ERROR: "Error",
        }
        return status_map.get(self._state, "Unknown")

    def _update_tray_menu(self) -> None:
        """Update tray icon and menu."""
        if self._tray is not None:
            try:
                self._tray.title = f"{PRODUCT_NAME} - {self._get_status_text()}"
                self._tray.menu = self._build_menu()
            except Exception as exc:
                logger.warning("Failed to update tray: %s", exc)

    def _on_connect(self, icon=None, item=None) -> None:
        """Handle Connect action — invoke P3c pairing flow."""
        self._transition(ConnectorState.CONNECTING)

        def do_connect():
            try:
                from .config import ConnectorConfig
                from .pairing import run_pairing_flow
                from evosia_agent.device_identity import DeviceIdentity
                from evosia_agent.version import AGENT_VERSION
                from evosia_agent.credential_store import CredentialStore, DeviceCredential

                config = ConnectorConfig()
                identity = DeviceIdentity.collect()

                result = run_pairing_flow(
                    config=config,
                    device_name=identity.get("hostname", "Unknown"),
                    platform=identity.get("platform", "unknown"),
                    agent_version=AGENT_VERSION,
                )

                if result:
                    device_id, device_token = result
                    store = CredentialStore(config.data_dir)
                    credential = DeviceCredential(
                        device_id=device_id,
                        device_name=identity.get("hostname", "Unknown"),
                        credential=device_token,
                        cloud_url=config.cloud_url,
                    )
                    store.save(credential)
                    self._device_name = identity.get("hostname", "Unknown")
                    self._transition(ConnectorState.CONNECTED)
                else:
                    self._transition(ConnectorState.NOT_CONNECTED)

            except Exception as exc:
                logger.error("Pairing failed: %s", exc)
                self._transition(ConnectorState.NOT_CONNECTED)

        threading.Thread(target=do_connect, daemon=True).start()

    def _on_add_project(self, icon=None, item=None) -> None:
        """Handle Add Project action — invoke P3d project authorization."""
        def do_add_project():
            try:
                from .config import ConnectorConfig
                from .folder_picker import select_folder_native
                from evosia_agent.credential_store import CredentialStore

                config = ConnectorConfig()
                store = CredentialStore(config.data_dir)
                credential = store.load()

                if not credential:
                    self._transition(ConnectorState.NOT_CONNECTED)
                    return

                # Open native folder picker
                folder_path = select_folder_native("Select project folder")

                if folder_path is None:
                    # User cancelled
                    return

                # Run project authorization flow
                from .project_authorization import run_project_authorization_flow
                from evosia_agent.device_identity import DeviceIdentity
                from evosia_agent.version import AGENT_VERSION

                identity = DeviceIdentity.collect()

                result = run_project_authorization_flow(
                    config=config,
                    folder_path=folder_path,
                    device_credential=credential.credential,
                    device_name=identity.get("hostname", "Unknown"),
                    platform=identity.get("platform", "unknown"),
                    agent_version=AGENT_VERSION,
                )

                if result:
                    # Refresh projects
                    from evosia_agent.project_registry import ProjectRegistry
                    registry = ProjectRegistry(config.data_dir)
                    self._projects = registry.list_projects()
                    self._transition(ConnectorState.READY)
                else:
                    # Authorization failed or cancelled
                    pass

            except Exception as exc:
                logger.error("Project authorization failed: %s", exc)

        threading.Thread(target=do_add_project, daemon=True).start()

    def _on_review_project(self, icon=None, item=None) -> None:
        """Handle Review Project action — invoke certified PROJECT_SCAN flow."""
        if self._state not in (ConnectorState.READY, ConnectorState.REVIEW_FAILED):
            return

        self._transition(ConnectorState.REVIEW_QUEUED)

        def do_review():
            try:
                from .config import ConnectorConfig
                from evosia_agent.credential_store import CredentialStore
                from evosia_agent.project_registry import ProjectRegistry
                import json
                import urllib.request

                config = ConnectorConfig()
                store = CredentialStore(config.data_dir)
                credential = store.load()

                if not credential:
                    self._transition(ConnectorState.NOT_CONNECTED)
                    return

                registry = ProjectRegistry(config.data_dir)
                projects = registry.list_projects()

                if not projects:
                    self._transition(ConnectorState.READY)
                    return

                # Use first authorized project
                project = projects[0]
                project_id = project.get("cloud_project_id")

                if not project_id:
                    self._transition(ConnectorState.REVIEW_FAILED)
                    return

                # Create PROJECT_SCAN via backend API
                url = f"{config.cloud_url}/api/device-projects/{project_id}/scans"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {credential.credential}",
                }
                data = json.dumps({"operation_type": "PROJECT_SCAN"}).encode("utf-8")

                req = urllib.request.Request(url, data=data, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    job_id = result.get("job_id")

                if job_id:
                    self._transition(ConnectorState.REVIEW_IN_PROGRESS)
                    # Poll for completion
                    self._poll_review_status(job_id, credential.credential, config.cloud_url)
                else:
                    self._transition(ConnectorState.REVIEW_FAILED)

            except Exception as exc:
                logger.error("Review failed: %s", exc)
                self._transition(ConnectorState.REVIEW_FAILED)

        threading.Thread(target=do_review, daemon=True).start()

    def _poll_review_status(self, job_id: str, credential: str, cloud_url: str) -> None:
        """Poll review status until completion."""
        import time
        import json
        import urllib.request

        max_attempts = 300  # 10 minutes with 2-second intervals
        for attempt in range(max_attempts):
            time.sleep(2)

            try:
                url = f"{cloud_url}/api/agent/jobs/{job_id}"
                headers = {"Authorization": f"Bearer {credential}"}
                req = urllib.request.Request(url, headers=headers, method="GET")

                with urllib.request.urlopen(req, timeout=10) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    status = result.get("status", "")

                    if status == "COMPLETED":
                        self._last_review_status = "Complete"
                        self._transition(ConnectorState.REVIEW_COMPLETE)
                        return
                    elif status == "FAILED":
                        self._last_review_status = "Failed"
                        self._transition(ConnectorState.REVIEW_FAILED)
                        return

            except Exception as exc:
                logger.warning("Poll error (attempt %d): %s", attempt + 1, exc)

        # Timeout
        self._last_review_status = "Timeout"
        self._transition(ConnectorState.REVIEW_FAILED)

    def _on_open_evosia(self, icon=None, item=None) -> None:
        """Open EVOSIA Cloud in browser."""
        try:
            webbrowser.open(self._cloud_url)
        except Exception as exc:
            logger.warning("Failed to open browser: %s", exc)

    def _on_diagnostics(self, icon=None, item=None) -> None:
        """Show diagnostics window."""
        def show_diagnostics():
            try:
                import tkinter as tk
                from tkinter import ttk

                root = tk.Tk()
                root.title(f"{PRODUCT_NAME} - Diagnostics")
                root.geometry("400x300")

                # Diagnostics content
                frame = ttk.Frame(root, padding="10")
                frame.pack(fill=tk.BOTH, expand=True)

                # Version
                ttk.Label(frame, text=f"Version: {self._version}").pack(anchor=tk.W)
                ttk.Label(frame, text=f"Cloud: {self._cloud_url}").pack(anchor=tk.W)
                ttk.Label(frame, text=f"Device: {self._device_name}").pack(anchor=tk.W)
                ttk.Label(frame, text=f"Status: {self._get_status_text()}").pack(anchor=tk.W)
                ttk.Label(frame, text=f"Projects: {len(self._projects)}").pack(anchor=tk.W)
                ttk.Label(frame, text=f"Last heartbeat: {self._last_heartbeat}").pack(anchor=tk.W)
                ttk.Label(frame, text=f"Last review: {self._last_review_status}").pack(anchor=tk.W)

                # Log location
                ttk.Label(frame, text="Logs: ~/.evosia/logs/").pack(anchor=tk.W)

                # Close button
                ttk.Button(frame, text="Close", command=root.destroy).pack(pady="10")

                root.mainloop()

            except Exception as exc:
                logger.error("Failed to show diagnostics: %s", exc)

        threading.Thread(target=show_diagnostics, daemon=True).start()

    def _on_exit(self, icon=None, item=None) -> None:
        """Exit the application cleanly."""
        self._polling = False
        if self._tray is not None:
            self._tray.stop()
        logger.info("Connector exited")

    def _start_background_tasks(self) -> None:
        """Start background tasks (heartbeat, polling)."""
        self._polling = True

        def heartbeat_loop():
            while self._polling:
                try:
                    self._send_heartbeat()
                except Exception as exc:
                    logger.warning("Heartbeat failed: %s", exc)
                import time
                time.sleep(30)

        self._poll_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        self._poll_thread.start()

    def _send_heartbeat(self) -> None:
        """Send heartbeat to cloud."""
        try:
            from .config import ConnectorConfig
            from evosia_agent.credential_store import CredentialStore
            import json
            import urllib.request

            config = ConnectorConfig()
            store = CredentialStore(config.data_dir)
            credential = store.load()

            if not credential:
                return

            url = f"{config.cloud_url}/api/agent/heartbeat"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {credential.credential}",
            }
            data = json.dumps({"status": "active"}).encode("utf-8")

            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                self._last_heartbeat = "OK"

        except Exception as exc:
            self._last_heartbeat = "Failed"

    def _create_tkinter_window(self) -> None:
        """Create tkinter window as fallback when pystray is not available."""
        def run_tkinter():
            try:
                import tkinter as tk
                from tkinter import ttk

                root = tk.Tk()
                root.title(PRODUCT_NAME)
                root.geometry("300x200")

                frame = ttk.Frame(root, padding="10")
                frame.pack(fill=tk.BOTH, expand=True)

                # Status
                status_label = ttk.Label(frame, text=self._get_status_text())
                status_label.pack(pady="5")

                # Actions
                if self._state == ConnectorState.NOT_CONNECTED:
                    ttk.Button(frame, text="Connect", command=self._on_connect).pack(pady="5")
                elif self._state == ConnectorState.READY:
                    ttk.Button(frame, text="Review Project", command=self._on_review_project).pack(pady="5")
                    ttk.Button(frame, text="Add Project", command=self._on_add_project).pack(pady="5")

                ttk.Button(frame, text="Exit", command=lambda: [root.quit(), root.destroy()]).pack(pady="5")

                root.mainloop()

            except Exception as exc:
                logger.error("Failed to create tkinter window: %s", exc)

        threading.Thread(target=run_tkinter, daemon=True).start()


def main() -> None:
    """Main entry point for desktop tray application."""
    app = ConnectorApp()
    app.start()


if __name__ == "__main__":
    main()
