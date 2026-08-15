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
        description="Run one command through the EVOSIA evidence pipeline"
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
        "--executor",
        help="Executor plugin name to use (default: local)",
    )
    parser.add_argument(
        "--plugin-dirs",
        type=Path,
        nargs="*",
        help="Directories to search for capability plugin metadata",
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
    record_args = []
    if work_queue and task_id:
        record_args = ["--task-id", task_id, "--work-queue", str(args.work_queue)]

    executor_plugin = None
    cap_manager = None
    if args.executor:
        from .capabilities import CapabilityManager, CapabilityRegistry

        plugin_dirs = args.plugin_dirs or []
        registry_path = args.runtime_root / "state" / "capabilities.json"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry = CapabilityRegistry(registry_path)
        cap_manager = CapabilityManager(registry, plugin_dirs)
        cap_manager.discover_and_register()
        executor_plugin = cap_manager.get_executor(args.executor)

    result = run_pipeline(
        args.command,
        runtime_root=args.runtime_root,
        repository=args.repository,
        working_directory=args.cwd,
        work_queue=work_queue,
        task_id=task_id,
        executor=executor_plugin,
        capability_manager=cap_manager,
        executor_name=args.executor,
    )

    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
