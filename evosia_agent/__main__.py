"""EVOSIA Local Agent — CLI entry point."""

from __future__ import annotations

import sys


def main() -> None:
    """CLI entry point for evosia_agent.

    Commands:
        python -m evosia_agent           — Start agent (register if needed)
        python -m evosia_agent status    — Show agent status
        python -m evosia_agent logout    — Remove local credential
    """
    from .agent import LocalAgent, status, logout

    args = sys.argv[1:]

    if not args:
        agent = LocalAgent()
        agent.run()
    elif args[0] == "status":
        status()
    elif args[0] == "logout":
        logout()
    else:
        print(f"Unknown command: {args[0]}")
        print()
        print("Usage:")
        print("  python -m evosia_agent           Start agent")
        print("  python -m evosia_agent status    Show status")
        print("  python -m evosia_agent logout    Remove local credential")
        sys.exit(1)


if __name__ == "__main__":
    main()
