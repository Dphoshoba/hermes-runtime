from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .runtime import run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one command through the Hermes evidence pipeline"
    )
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=Path.home() / ".hermes" / "runtime",
    )
    parser.add_argument(
        "--repository",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--cwd",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
    )
    args = parser.parse_args()

    if not args.command:
        parser.error("a command is required")

    result = run_pipeline(
        args.command,
        runtime_root=args.runtime_root,
        repository=args.repository,
        working_directory=args.cwd,
    )

    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
