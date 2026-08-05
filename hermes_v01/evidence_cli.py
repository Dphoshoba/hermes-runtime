from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evidence import EvidenceRecorder


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute one command and publish an immutable Hermes evidence record"
    )
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--trigger", default="LOCAL_TERMINAL")
    parser.add_argument("--artifact", action="append", default=[])
    parser.add_argument("--repository")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("a command is required after --")

    result = EvidenceRecorder(Path(args.evidence_dir)).execute(
        command,
        working_directory=Path(args.cwd),
        trigger=args.trigger,
        artifacts=[Path(path) for path in args.artifact],
        repository=Path(args.repository) if args.repository else None,
    )
    print(json.dumps(result.envelope.as_dict(), indent=2, sort_keys=True))
    print(result.record_path)
    return result.envelope.execution_record.exit_code or 0


if __name__ == "__main__":
    raise SystemExit(main())
