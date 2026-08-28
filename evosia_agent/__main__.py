"""EVOSIA Local Agent — CLI entry point."""

from __future__ import annotations

import sys


def main() -> None:
    """CLI entry point for evosia_agent.

    Commands:
        python -m evosia_agent                                          — Start agent
        python -m evosia_agent status                                   — Show status
        python -m evosia_agent logout                                   — Remove credential
        python -m evosia_agent project add <path> --authorization-token <token>
        python -m evosia_agent projects                                 — List projects
        python -m evosia_agent project remove <id>                      — Remove project
    """
    from .agent import LocalAgent, status, logout, project_add, project_list, project_remove

    args = sys.argv[1:]

    if not args:
        agent = LocalAgent()
        agent.run()
    elif args[0] == "status":
        status()
    elif args[0] == "logout":
        logout()
    elif args[0] == "project" and len(args) >= 3 and args[1] == "add":
        path = args[2]
        token = _extract_flag(args, "--authorization-token")
        project_add(path, authorization_token=token)
    elif args[0] == "projects" or (args[0] == "project" and len(args) == 1):
        project_list()
    elif args[0] == "project" and len(args) >= 3 and args[1] == "remove":
        project_remove(args[2])
    else:
        print(f"Unknown command: {' '.join(args)}")
        print()
        print("Usage:")
        print("  python -m evosia_agent                                          Start agent")
        print("  python -m evosia_agent status                                   Show status")
        print("  python -m evosia_agent logout                                   Remove credential")
        print("  python -m evosia_agent project add <path> --authorization-token <token>")
        print("  python -m evosia_agent projects                                 List projects")
        print("  python -m evosia_agent project remove <id>                      Remove project")
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
