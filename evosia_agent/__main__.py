"""EVOSIA Local Agent — CLI entry point."""

from __future__ import annotations

import sys


def main() -> None:
    """CLI entry point for evosia_agent.

    Commands:
        python -m evosia_agent                       — Start agent (register if needed)
        python -m evosia_agent status                — Show agent status
        python -m evosia_agent logout                — Remove local credential
        python -m evosia_agent project add <path>    — Register a project
        python -m evosia_agent projects              — List registered projects
        python -m evosia_agent project remove <id>   — Remove a project
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
        project_add(args[2])
    elif args[0] == "projects" or (args[0] == "project" and len(args) == 1):
        project_list()
    elif args[0] == "project" and len(args) >= 3 and args[1] == "remove":
        project_remove(args[2])
    else:
        print(f"Unknown command: {' '.join(args)}")
        print()
        print("Usage:")
        print("  python -m evosia_agent                       Start agent")
        print("  python -m evosia_agent status                Show status")
        print("  python -m evosia_agent logout                Remove local credential")
        print("  python -m evosia_agent project add <path>    Register a project")
        print("  python -m evosia_agent projects              List registered projects")
        print("  python -m evosia_agent project remove <id>   Remove a project")
        sys.exit(1)


if __name__ == "__main__":
    main()
