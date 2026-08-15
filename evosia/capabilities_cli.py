from __future__ import annotations

import argparse
import json
from pathlib import Path

from .capabilities import CapabilityManager, CapabilityRegistry, PluginDiscovery


def _load_manager(args: argparse.Namespace) -> CapabilityManager:
    registry = CapabilityRegistry(Path(args.state_file).expanduser().resolve())
    plugin_dirs = [Path(d).expanduser().resolve() for d in getattr(args, "plugin_dirs", [])]
    return CapabilityManager(registry, plugin_dirs)


def cmd_list(args: argparse.Namespace) -> int:
    manager = _load_manager(args)
    capabilities = manager._registry.list(
        capability_type=args.type,
        enabled_only=args.enabled_only,
    )
    print(json.dumps([c.metadata.as_dict() for c in capabilities], indent=2, sort_keys=True))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    manager = _load_manager(args)
    state = manager._registry.get(args.name)
    print(json.dumps(state.as_dict(), indent=2, sort_keys=True))
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    manager = _load_manager(args)
    registered = manager.discover_and_register()
    print(json.dumps({"registered": registered}, indent=2, sort_keys=True))
    return 0


def cmd_enable(args: argparse.Namespace) -> int:
    manager = _load_manager(args)
    state = manager._registry.enable(args.name)
    print(json.dumps(state.metadata.as_dict(), indent=2, sort_keys=True))
    return 0


def cmd_disable(args: argparse.Namespace) -> int:
    manager = _load_manager(args)
    state = manager._registry.disable(args.name)
    print(json.dumps(state.metadata.as_dict(), indent=2, sort_keys=True))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    manager = _load_manager(args)
    state = manager.check_health(args.name)
    print(json.dumps(state.as_dict(), indent=2, sort_keys=True))
    return 0


def cmd_check_all(args: argparse.Namespace) -> int:
    manager = _load_manager(args)
    results = manager.check_all_health()
    print(json.dumps([r.as_dict() for r in results], indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="EVOSIA Capability Manager")
    parser.add_argument("--state-file", required=True, help="Path to capability registry state file")
    parser.add_argument("--plugin-dirs", action="append", default=[], help="Plugin discovery directories")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List all registered capabilities")
    list_parser.add_argument("--type", choices=("executor", "validator", "provider", "notifier"))
    list_parser.add_argument("--enabled-only", action="store_true")

    show_parser = subparsers.add_parser("show", help="Show capability details")
    show_parser.add_argument("name", help="Capability name")

    subparsers.add_parser("discover", help="Discover and register plugins from plugin directories")

    enable_parser = subparsers.add_parser("enable", help="Enable a capability")
    enable_parser.add_argument("name", help="Capability name")

    disable_parser = subparsers.add_parser("disable", help="Disable a capability")
    disable_parser.add_argument("name", help="Capability name")

    check_parser = subparsers.add_parser("check", help="Run health check on a capability")
    check_parser.add_argument("name", help="Capability name")

    subparsers.add_parser("check-all", help="Run health check on all enabled capabilities")

    args = parser.parse_args()

    handlers = {
        "list": cmd_list,
        "show": cmd_show,
        "discover": cmd_discover,
        "enable": cmd_enable,
        "disable": cmd_disable,
        "check": cmd_check,
        "check-all": cmd_check_all,
    }

    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())