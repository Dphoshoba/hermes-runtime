from __future__ import annotations

import argparse
import json
from pathlib import Path

from .metrics import compute_queue_metrics, compute_runtime_metrics, write_metrics_report
from .work_queue import WorkQueueManager, WorkQueueStateStore


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate EVOSIA runtime and queue metrics report"
    )
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=Path.home() / ".hermes" / "runtime",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / ".hermes" / "runtime" / "metrics",
    )
    parser.add_argument(
        "--work-queue",
        type=Path,
        help="Path to work queue state file",
    )
    args = parser.parse_args()

    runtime_metrics = compute_runtime_metrics(args.runtime_root)
    
    queue_metrics = None
    if args.work_queue:
        work_queue = WorkQueueManager(state_store=WorkQueueStateStore(args.work_queue))
        queue_metrics = compute_queue_metrics(work_queue)

    json_path, md_path = write_metrics_report(runtime_metrics, queue_metrics, args.output_dir)

    report = {"runtime_metrics": runtime_metrics.__dict__}
    if queue_metrics:
        report["queue_metrics"] = queue_metrics.__dict__
    
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    print(json_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())