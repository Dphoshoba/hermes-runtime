from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .runtime import run_pipeline
from .work_queue import WorkQueueManager, WorkQueueStateStore


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
        "--task-id",
        help="Work queue task ID to execute",
    )
    parser.add_argument(
        "--next",
        action="store_true",
        dest="use_next",
        help="Select and execute the next READY task from the work queue",
    )
    parser.add_argument(
        "--work-queue",
        type=Path,
        help="Path to work queue state file",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
    )
    args = parser.parse_args()

    work_queue = None
    if args.work_queue:
        work_queue = WorkQueueManager(state_store=WorkQueueStateStore(args.work_queue))

    task_id = args.task_id
    if args.use_next:
        if not work_queue:
            parser.error("--next requires --work-queue")
        next_task = work_queue.next_ready()
        if next_task is None:
            print("No READY tasks available", file=sys.stderr)
            return 2
        task_id = next_task.task_id

    if task_id and not work_queue:
        parser.error("--task-id requires --work-queue")

    if not task_id and not args.command:
        parser.error("a command is required (or use --task-id/--next with --work-queue)")

    # If task_id is provided but no command, we need to get the command from somewhere
    # For now, require command to be provided
    if not args.command:
        parser.error("a command is required")

    # Build the hermes-record command with work queue args if needed
    import sys
    record_args = []
    if work_queue and task_id:
        record_args = ["--task-id", task_id, "--work-queue", str(args.work_queue)]

    # We need to inject the work queue args into the subprocess calls
    # For simplicity, let's modify the approach - we'll pass the work queue and task_id
    # to run_pipeline and let it handle the transitions, but the subprocess calls
    # to hermes-record/hermes-review need the CLI args too.
    # Actually, the current design has run_pipeline calling subprocesses.
    # The work queue transitions are done in-process via the WorkQueueManager.
    # The hermes-record/hermes-review subprocesses don't need to know about the work queue
    # for the transitions - they just do their job.
    # The in-process transitions are sufficient.

    result = run_pipeline(
        args.command,
        runtime_root=args.runtime_root,
        repository=args.repository,
        working_directory=args.cwd,
        work_queue=work_queue,
        task_id=task_id,
    )

    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
