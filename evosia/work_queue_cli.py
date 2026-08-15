from __future__ import annotations

import argparse
import json
from pathlib import Path

from .work_queue import WorkItem, WorkQueueManager, WorkQueueStateStore


def _load_manager(args: argparse.Namespace) -> WorkQueueManager:
    state_file = Path(args.state_file).expanduser().resolve()
    return WorkQueueManager(state_store=WorkQueueStateStore(state_file))


def cmd_list(args: argparse.Namespace) -> int:
    manager = _load_manager(args)
    summary = manager.summary()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    manager = _load_manager(args)
    item = manager.get(args.task_id)
    print(json.dumps(item.as_dict(), indent=2, sort_keys=True))
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    manager = _load_manager(args)
    item = manager.next_ready()
    if item is None:
        print("null")
        return 0
    print(json.dumps(item.as_dict(), indent=2, sort_keys=True))
    return 0


def cmd_dispatch(args: argparse.Namespace) -> int:
    manager = _load_manager(args)
    item = manager.dispatch_next()
    if item is None:
        print("null")
        return 0
    print(json.dumps(item.as_dict(), indent=2, sort_keys=True))
    return 0


def cmd_observe(args: argparse.Namespace) -> int:
    manager = _load_manager(args)
    item = manager.mark_observed(args.task_id)
    print(json.dumps(item.as_dict(), indent=2, sort_keys=True))
    return 0


def cmd_verification_pending(args: argparse.Namespace) -> int:
    manager = _load_manager(args)
    item = manager.mark_verification_pending(args.task_id)
    print(json.dumps(item.as_dict(), indent=2, sort_keys=True))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    manager = _load_manager(args)
    item = manager.record_independent_verification(args.task_id)
    print(json.dumps(item.as_dict(), indent=2, sort_keys=True))
    return 0


def cmd_complete(args: argparse.Namespace) -> int:
    manager = _load_manager(args)
    item = manager.mark_complete(args.task_id)
    print(json.dumps(item.as_dict(), indent=2, sort_keys=True))
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    manager = _load_manager(args)
    summary = manager.summary()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="EVOSIA Work Queue CLI")
    parser.add_argument("--state-file", required=True, help="Path to work queue state file")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List all tasks with their states")
    subparsers.add_parser("summary", help="Show summary of tasks by state")

    show_parser = subparsers.add_parser("show", help="Show a specific task")
    show_parser.add_argument("task_id", help="Task ID to show")

    next_parser = subparsers.add_parser("next", help="Show next READY task")

    subparsers.add_parser("dispatch", help="Dispatch next READY task to RUNNING")

    observe_parser = subparsers.add_parser("observe", help="Mark task as OBSERVED")
    observe_parser.add_argument("task_id", help="Task ID to observe")

    vp_parser = subparsers.add_parser("verification-pending", help="Mark task as VERIFICATION_PENDING")
    vp_parser.add_argument("task_id", help="Task ID")

    verify_parser = subparsers.add_parser("verify", help="Record independent verification (VERIFIED)")
    verify_parser.add_argument("task_id", help="Task ID")

    complete_parser = subparsers.add_parser("complete", help="Mark task as COMPLETE")
    complete_parser.add_argument("task_id", help="Task ID")

    args = parser.parse_args()

    handlers = {
        "list": cmd_list,
        "summary": cmd_summary,
        "show": cmd_show,
        "next": cmd_next,
        "dispatch": cmd_dispatch,
        "observe": cmd_observe,
        "verification-pending": cmd_verification_pending,
        "verify": cmd_verify,
        "complete": cmd_complete,
    }

    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())