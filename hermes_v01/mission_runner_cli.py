from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .mission import load_mission, MissionPlanner, load_plan
from .mission_runner import MissionRunner, save_mission_report


def cmd_run(args) -> int:
    mission_path = Path(args.mission_file).expanduser().resolve()
    runtime_root = Path(args.runtime_root).expanduser().resolve()
    repository = Path(args.repository).expanduser().resolve()
    working_directory = Path(args.cwd).expanduser().resolve()
    queue_path = Path(args.queue_file).expanduser().resolve()
    report_path = Path(args.report_file).expanduser().resolve() if args.report_file else None

    plugin_dirs = [Path(p).expanduser().resolve() for p in (args.plugin_dirs or [])]

    runner = MissionRunner(
        runtime_root=runtime_root,
        repository=repository,
        working_directory=working_directory,
        queue_path=queue_path,
        executor_name=args.executor,
        plugin_dirs=plugin_dirs,
    )

    if mission_path.suffix == ".json":
        try:
            plan = load_plan(mission_path)
        except (json.JSONDecodeError, KeyError, ValueError):
            mission = load_mission(mission_path)
            planner = MissionPlanner()
            plan = planner.build(mission)
    else:
        print(json.dumps({"error": f"unsupported file type: {mission_path.suffix}"}), file=sys.stderr)
        return 1

    report = runner.run(plan)

    if report_path:
        save_mission_report(report, report_path)

    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))

    if report.status == "COMPLETED":
        return 0
    elif report.status == "PARTIAL":
        return 1
    else:
        return 2


def cmd_report(args) -> int:
    report_path = Path(args.report_file).expanduser().resolve()
    if not report_path.exists():
        print(json.dumps({"error": f"report not found: {report_path}"}), file=sys.stderr)
        return 1

    data = json.loads(report_path.read_text(encoding="utf-8"))
    print(json.dumps(data, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Hermes Autonomous Mission Runner"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Execute a complete mission")
    run_parser.add_argument(
        "mission_file",
        help="Path to mission JSON or plan JSON file",
    )
    run_parser.add_argument(
        "--runtime-root",
        default=str(Path.home() / ".hermes" / "runtime"),
        help="Runtime root directory (default: ~/.hermes/runtime)",
    )
    run_parser.add_argument(
        "--repository",
        required=True,
        help="Repository path",
    )
    run_parser.add_argument(
        "--cwd",
        required=True,
        help="Working directory for command execution",
    )
    run_parser.add_argument(
        "--queue-file",
        default=str(Path.home() / ".hermes" / "runtime" / "state" / "queue.json"),
        help="Work queue state file path",
    )
    run_parser.add_argument(
        "--report-file",
        help="Path to write mission report (optional)",
    )
    run_parser.add_argument(
        "--executor",
        help="Executor plugin name (default: local)",
    )
    run_parser.add_argument(
        "--plugin-dirs",
        nargs="*",
        help="Plugin directories for capability discovery",
    )

    report_parser = subparsers.add_parser("report", help="Display a mission report")
    report_parser.add_argument(
        "report_file",
        help="Path to mission report JSON",
    )

    args = parser.parse_args()

    handlers = {
        "run": cmd_run,
        "report": cmd_report,
    }

    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
