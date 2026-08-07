from __future__ import annotations

import argparse
import json
from pathlib import Path

from .runtime_state import RuntimeStateStore, load_projected_state
from .work_queue import WorkQueueManager, WorkQueueStateStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Show the canonical Hermes runtime state")
    parser.add_argument("--supervisor-state", required=True)
    parser.add_argument("--milestone")
    parser.add_argument("--write-state")
    parser.add_argument("--work-queue", help="Path to work queue state file")
    args = parser.parse_args()

    work_queue = None
    if args.work_queue:
        work_queue = WorkQueueManager(state_store=WorkQueueStateStore(Path(args.work_queue)))

    state = load_projected_state(
        Path(args.supervisor_state).expanduser().resolve(),
        current_milestone=args.milestone,
        work_queue=work_queue,
    )
    if args.write_state:
        RuntimeStateStore(Path(args.write_state).expanduser().resolve()).save(state)
    print(json.dumps(state.as_dict(), indent=2, sort_keys=True))
    return 0 if not state.blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
