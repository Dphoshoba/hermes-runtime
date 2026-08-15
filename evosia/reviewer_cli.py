from __future__ import annotations

import argparse
import json
from pathlib import Path

from .reviewer import IndependentReviewer
from .work_queue import WorkQueueManager, WorkQueueStateStore


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Review one immutable EVOSIA execution record without modifying it"
    )
    parser.add_argument("--record", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--task-id", help="Work queue task ID to mark as verified on successful review")
    parser.add_argument("--work-queue", help="Path to work queue state file")
    args = parser.parse_args()

    result = IndependentReviewer(Path(args.output_dir)).review(Path(args.record))
    print(json.dumps(result.envelope.as_dict(), indent=2, sort_keys=True))
    print(result.review_json_path)
    print(result.review_markdown_path)

    if result.envelope.outcome == "REVIEW_PASSED":
        if args.task_id and args.work_queue:
            work_queue = WorkQueueManager(state_store=WorkQueueStateStore(Path(args.work_queue)))
            work_queue.record_independent_verification(args.task_id)
        return 0
    if result.envelope.outcome == "REVIEW_INCOMPLETE":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
