"""EVOSIA Connector — packaged runtime launcher.

This module provides the stable entry point for the packaged Connector.
It delegates to the certified evosia_agent runtime without duplicating
business logic.
"""

from __future__ import annotations

import logging
import sys

from .version import CONNECTOR_VERSION, BUILD_CHANNEL
from .config import ConnectorConfig

logger = logging.getLogger("evosia_connector")


def _setup_packaged_logging() -> None:
    """Configure logging for packaged runtime.

    - No console output during steady-state operation
    - Logs written to dedicated EVOSIA data/log location
    - No credentials/tokens/secrets in logs
    """
    import os
    from pathlib import Path

    system = __import__("platform").system()
    home = Path.home()

    if system == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local"))
        log_dir = Path(local_app_data) / "EVOSIA" / "Connector" / "logs"
    elif system == "Darwin":
        log_dir = home / "Library" / "Application Support" / "EVOSIA" / "Connector" / "logs"
    else:
        log_dir = home / ".local" / "share" / "EVOSIA" / "Connector" / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "connector.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )

    logger.info("EVOSIA Connector starting (%s, channel=%s)", CONNECTOR_VERSION, BUILD_CHANNEL)


def _run_agent(config: ConnectorConfig) -> None:
    """Run the evosia_agent with Connector configuration.

    Delegates to the certified agent runtime. This function does NOT
    duplicate authority checks, scan logic, or credential management.
    """
    from evosia_agent.agent import LocalAgent
    from evosia_agent.config import AgentConfig

    # Bridge Connector config to agent config
    agent_config = AgentConfig(
        cloud_url=config.cloud_url,
        data_dir=config.data_dir,
    )

    agent = LocalAgent(config=agent_config)
    agent.run()


def main() -> None:
    """Connector entry point for packaged executable.

    This is the stable entry point that PyInstaller (or other packaging)
    binds to. It handles:
    1. Packaged logging initialization
    2. Configuration resolution
    3. Delegation to certified agent runtime
    """
    _setup_packaged_logging()

    config = ConnectorConfig()

    try:
        _run_agent(config)
    except KeyboardInterrupt:
        logger.info("Connector shut down by user")
        sys.exit(0)
    except Exception as exc:
        logger.error("Connector error: %s", exc, exc_info=True)
        sys.exit(1)


def cli_status() -> None:
    """Connector status command — shows packaged identity."""
    config = ConnectorConfig()
    print(f"Product: EVOSIA Connector")
    print(f"Version: {CONNECTOR_VERSION}")
    print(f"Channel: {BUILD_CHANNEL}")
    print(f"Cloud:   {config.cloud_url}")
    print(f"Data:    {config.data_dir}")

    # Delegate to agent status for device info
    from evosia_agent.agent import status
    status()


def cli_version() -> None:
    """Connector version command."""
    print(CONNECTOR_VERSION)
    print(f"Channel: {BUILD_CHANNEL}")


if __name__ == "__main__":
    main()
