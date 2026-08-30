"""EVOSIA Connector — CLI entry point for packaged executable."""

from __future__ import annotations

import sys


def main() -> None:
    """CLI entry point for EVOSIA Connector.

    Commands:
        evosia-connector              — Start agent
        evosia-connector connect      — Connect via browser-assisted pairing
        evosia-connector status       — Show status
        evosia-connector version      — Show version
        evosia-connector logout       — Remove credential
        evosia-connector project add <path> --authorization-token <token>
        evosia-connector projects     — List projects
        evosia-connector project remove <id>  — Remove project
    """
    from .launcher import main as _run_connector, cli_status, cli_version

    args = sys.argv[1:]

    if not args:
        _run_connector()
    elif args[0] == "connect":
        _run_connect()
    elif args[0] == "status":
        cli_status()
    elif args[0] == "version":
        cli_version()
    elif args[0] == "logout":
        from evosia_agent.agent import logout
        logout()
    elif args[0] == "project" and len(args) >= 3 and args[1] == "add":
        from evosia_agent.agent import project_add
        path = args[2]
        token = _extract_flag(args, "--authorization-token")
        project_add(path, authorization_token=token)
    elif args[0] == "projects" or (args[0] == "project" and len(args) == 1):
        from evosia_agent.agent import project_list
        project_list()
    elif args[0] == "project" and len(args) >= 3 and args[1] == "remove":
        from evosia_agent.agent import project_remove
        project_remove(args[2])
    else:
        print(f"Unknown command: {' '.join(args)}")
        print()
        print("Usage:")
        print("  evosia-connector                                          Start agent")
        print("  evosia-connector connect                                  Connect via browser")
        print("  evosia-connector status                                   Show status")
        print("  evosia-connector version                                  Show version")
        print("  evosia-connector logout                                   Remove credential")
        print("  evosia-connector project add <path> --authorization-token <token>")
        print("  evosia-connector projects                                 List projects")
        print("  evosia-connector project remove <id>                      Remove project")
        sys.exit(1)


def _run_connect() -> None:
    """Run browser-assisted pairing flow."""
    from .config import ConnectorConfig
    from .pairing import run_pairing_flow
    from evosia_agent.device_identity import DeviceIdentity
    from evosia_agent.version import AGENT_VERSION

    config = ConnectorConfig()

    # Collect device identity
    identity = DeviceIdentity.collect()

    print("EVOSIA Connector — Connect to EVOSIA")
    print()

    result = run_pairing_flow(
        config=config,
        device_name=identity.get("hostname", "Unknown"),
        platform=identity.get("platform", "unknown"),
        agent_version=AGENT_VERSION,
    )

    if result:
        device_id, device_token = result
        # Store the credential
        from evosia_agent.credential_store import CredentialStore, DeviceCredential

        store = CredentialStore(config.data_dir)
        credential = DeviceCredential(
            device_id=device_id,
            device_name=identity.get("hostname", "Unknown"),
            credential=device_token,
            cloud_url=config.cloud_url,
        )
        store.save(credential)
        print()
        print(f"Device registered: {device_id}")
        print("You can now start the connector with: evosia-connector")
    else:
        print()
        print("Connection failed. Please try again.")
        sys.exit(1)


def _extract_flag(args: list[str], flag: str) -> str | None:
    """Extract the value following a --flag in args. Returns None if absent."""
    try:
        idx = args.index(flag)
        if idx + 1 < len(args):
            return args[idx + 1]
    except ValueError:
        pass
    return None


if __name__ == "__main__":
    main()
