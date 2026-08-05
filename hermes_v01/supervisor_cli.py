from __future__ import annotations

import argparse
from pathlib import Path

from .__main__ import DEFAULT_ARTIFACTS
from .supervisor import ExecutionSupervisor


def main() -> int:
    parser = argparse.ArgumentParser(description="Persistent read-only Hermes validation supervisor")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--artifact", action="append", dest="artifacts")
    parser.add_argument("--interval", type=float, default=60.0, help="Seconds between cycles")
    parser.add_argument("--max-cycles", type=int)
    parser.add_argument("--state-file")
    parser.add_argument("--stop-file")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve()
    supervisor = ExecutionSupervisor(
        repository=Path(args.repo),
        output_dir=output_dir,
        artifacts=args.artifacts or DEFAULT_ARTIFACTS,
        interval_seconds=args.interval,
        state_file=Path(args.state_file) if args.state_file else None,
        stop_file=Path(args.stop_file) if args.stop_file else None,
    )
    return supervisor.run(max_cycles=args.max_cycles)


if __name__ == "__main__":
    raise SystemExit(main())
