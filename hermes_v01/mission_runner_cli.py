from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .mission import load_mission, MissionPlanner, load_plan
from .mission_runner import MissionRunner, save_mission_report, MissionReport
from .mission_types import MissionTypeRegistry, register_built_in_types
from .mission_constraints import ConstraintEngine
from .mission_state import MissionStateStore
from .mission_control import MissionControlStore, write_control_command, CONTROL_ACTIONS
from .mission_report import (
    MissionReportGenerator,
    generate_and_save_reports,
    mission_report_json_path,
    mission_report_md_path,
    load_report_json,
    save_report_json,
    save_report_markdown,
    render_markdown,
)


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
        mission_type_name=args.mission_type,
        max_concurrency=args.concurrency,
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


def cmd_generate_report(args) -> int:
    """Generate comprehensive mission report from existing report + mission state."""
    runtime_root = Path(args.runtime_root).expanduser().resolve()
    mission_id = args.mission_id
    repository = Path(args.repository).expanduser().resolve() if args.repository else None

    # Load base report from mission-specific path
    base_path = mission_report_json_path(runtime_root, mission_id)
    if not base_path.exists():
        # Try loading from the legacy report file path
        base_data = load_report_json(base_path)
        if base_data is None:
            print(json.dumps({"error": f"no report found for mission: {mission_id}"}), file=sys.stderr)
            return 1
    else:
        base_data = load_report_json(base_path)

    # Load mission state
    state_store = MissionStateStore(runtime_root / "state" / "mission_state.json")
    mission_state = state_store.load()

    # Reconstruct MissionReport from dict
    report_dict = base_data
    base_report = MissionReport(
        schema_version=report_dict.get("schema_version", "1"),
        mission_id=report_dict.get("mission_id", mission_id),
        mission_title=report_dict.get("mission_title", ""),
        mission_type=report_dict.get("mission_type", "generic"),
        status=report_dict.get("status", "UNKNOWN"),
        started_at=report_dict.get("started_at", ""),
        finished_at=report_dict.get("finished_at", ""),
        duration_seconds=report_dict.get("duration_seconds", 0.0),
        tasks_planned=report_dict.get("tasks_planned", 0),
        tasks_completed=report_dict.get("tasks_completed", 0),
        tasks_failed=report_dict.get("tasks_failed", 0),
        tasks_skipped=report_dict.get("tasks_skipped", 0),
        evidence_records=tuple(report_dict.get("evidence_records", [])),
        independent_reviews=tuple(report_dict.get("independent_reviews", [])),
        queue_summary={k: tuple(v) for k, v in report_dict.get("queue_summary", {}).items()},
        runtime_health=report_dict.get("runtime_health", "UNKNOWN"),
        metrics_summary=report_dict.get("metrics_summary", {}),
        warnings=tuple(report_dict.get("warnings", [])),
        errors=tuple(report_dict.get("errors", [])),
        artifacts_produced=tuple(report_dict.get("artifacts_produced", [])),
        mission_report_path=report_dict.get("mission_report_path"),
        max_concurrency=report_dict.get("max_concurrency", 1),
        peak_concurrent_tasks=report_dict.get("peak_concurrent_tasks", 0),
    )

    generator = MissionReportGenerator(
        runtime_root=runtime_root,
        repository=repository,
    )
    full_report = generator.generate(base_report, mission_state)

    json_path = mission_report_json_path(runtime_root, mission_id)
    md_path = mission_report_md_path(runtime_root, mission_id)
    save_report_json(full_report, json_path)
    save_report_markdown(full_report, md_path)

    output = {
        "status": "generated",
        "mission_id": mission_id,
        "json_path": str(json_path),
        "md_path": str(md_path),
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


def cmd_types(args) -> int:
    registry = MissionTypeRegistry.instance()
    register_built_in_types(registry)

    category = getattr(args, "category", None)
    types = registry.list_types(category=category)

    if args.json:
        output = [t.as_dict() for t in types]
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        if not types:
            print("No mission types registered.")
            return 0
        print(f"{'Name':<30} {'Category':<15} {'Version':<10} Description")
        print("-" * 100)
        for t in types:
            print(f"{t.name:<30} {t.category:<15} {t.version:<10} {t.description}")
    return 0


def cmd_type_show(args) -> int:
    registry = MissionTypeRegistry.instance()
    register_built_in_types(registry)

    name = args.type_name
    if not registry.is_registered(name):
        print(json.dumps({"error": f"mission type not found: {name}"}), file=sys.stderr)
        return 1

    metadata = registry.get_metadata(name)
    print(json.dumps(metadata.as_dict(), indent=2, sort_keys=True))
    return 0


def cmd_constraints(args) -> int:
    mission_path = Path(args.mission_file).expanduser().resolve()
    repository = Path(args.repository) if args.repository else None
    working_directory = Path(args.cwd) if args.cwd else None

    try:
        mission = load_mission(mission_path)
    except (json.JSONDecodeError, KeyError, ValueError, FileNotFoundError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1

    context: dict = {}
    if repository:
        context["repository"] = repository
    if working_directory:
        context["working_directory"] = working_directory

    engine = ConstraintEngine(context=context)
    errors, warnings = engine.validate_mission_constraints(mission)
    results = engine.validate(mission)
    summary = engine.get_results_summary(results)

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"Constraint Validation: {summary['satisfied']}/{summary['total']} satisfied")
        print()
        for r in results:
            status = "PASS" if r.satisfied else "FAIL"
            print(f"  [{status}] {r.constraint_type}: {r.message}")

    return 0 if summary["unsatisfied"] == 0 else 1


# ---------------------------------------------------------------------------
# Lifecycle CLI commands
# ---------------------------------------------------------------------------


def _resolve_runtime_root(args) -> Path:
    return Path(args.runtime_root).expanduser().resolve()


def cmd_status(args) -> int:
    runtime_root = _resolve_runtime_root(args)
    state_store = MissionStateStore(runtime_root / "state" / "mission_state.json")
    state = state_store.load()
    if state is None:
        print(json.dumps({"error": "no active mission state found"}), file=sys.stderr)
        return 1
    print(json.dumps(state.as_dict(), indent=2, sort_keys=True))
    return 0


def cmd_pause(args) -> int:
    runtime_root = _resolve_runtime_root(args)
    state_store = MissionStateStore(runtime_root / "state" / "mission_state.json")
    control_store = MissionControlStore(runtime_root / "state" / "mission_control.json")

    state = state_store.load()
    if state is None:
        print(json.dumps({"error": "no active mission to pause"}), file=sys.stderr)
        return 1

    from .mission_state import TERMINAL_MISSION_STATES
    if state.state in TERMINAL_MISSION_STATES:
        print(json.dumps({"error": f"mission in terminal state: {state.state}"}), file=sys.stderr)
        return 1

    reason = args.reason if hasattr(args, "reason") and args.reason else "CLI pause"
    cmd = write_control_command(
        control_store, state.mission_id, "pause", state.last_control_command_id, reason=reason,
    )
    print(json.dumps({
        "status": "pause_command_written",
        "command_id": cmd.command_id,
        "mission_id": state.mission_id,
        "reason": reason,
    }, indent=2, sort_keys=True))
    return 0


def cmd_resume(args) -> int:
    runtime_root = _resolve_runtime_root(args)
    state_store = MissionStateStore(runtime_root / "state" / "mission_state.json")
    control_store = MissionControlStore(runtime_root / "state" / "mission_control.json")

    state = state_store.load()
    if state is None:
        print(json.dumps({"error": "no active mission to resume"}), file=sys.stderr)
        return 1

    if state.state != "PAUSED":
        print(json.dumps({"error": f"can only resume a PAUSED mission, current: {state.state}"}), file=sys.stderr)
        return 1

    cmd = write_control_command(
        control_store, state.mission_id, "resume", state.last_control_command_id,
    )
    print(json.dumps({
        "status": "resume_command_written",
        "command_id": cmd.command_id,
        "mission_id": state.mission_id,
    }, indent=2, sort_keys=True))
    return 0


def cmd_cancel(args) -> int:
    runtime_root = _resolve_runtime_root(args)
    state_store = MissionStateStore(runtime_root / "state" / "mission_state.json")
    control_store = MissionControlStore(runtime_root / "state" / "mission_control.json")

    state = state_store.load()
    if state is None:
        print(json.dumps({"error": "no active mission to cancel"}), file=sys.stderr)
        return 1

    from .mission_state import TERMINAL_MISSION_STATES
    if state.state in TERMINAL_MISSION_STATES:
        print(json.dumps({"error": f"mission in terminal state: {state.state}"}), file=sys.stderr)
        return 1

    reason = args.reason if hasattr(args, "reason") and args.reason else "CLI cancel"
    cmd = write_control_command(
        control_store, state.mission_id, "cancel", state.last_control_command_id, reason=reason,
    )
    print(json.dumps({
        "status": "cancel_command_written",
        "command_id": cmd.command_id,
        "mission_id": state.mission_id,
        "reason": reason,
    }, indent=2, sort_keys=True))
    return 0


def cmd_abort(args) -> int:
    runtime_root = _resolve_runtime_root(args)
    state_store = MissionStateStore(runtime_root / "state" / "mission_state.json")
    control_store = MissionControlStore(runtime_root / "state" / "mission_control.json")

    state = state_store.load()
    if state is None:
        print(json.dumps({"error": "no active mission to abort"}), file=sys.stderr)
        return 1

    from .mission_state import TERMINAL_MISSION_STATES
    if state.state in TERMINAL_MISSION_STATES:
        print(json.dumps({"error": f"mission in terminal state: {state.state}"}), file=sys.stderr)
        return 1

    reason = args.reason if hasattr(args, "reason") and args.reason else "CLI abort"
    cmd = write_control_command(
        control_store, state.mission_id, "abort", state.last_control_command_id, reason=reason,
    )
    print(json.dumps({
        "status": "abort_command_written",
        "command_id": cmd.command_id,
        "mission_id": state.mission_id,
        "reason": reason,
    }, indent=2, sort_keys=True))
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
    run_parser.add_argument(
        "--mission-type",
        help="Mission type name for type-specific validation",
    )
    run_parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Maximum number of independent tasks to execute concurrently (default: 1)",
    )

    report_parser = subparsers.add_parser("report", help="Display a mission report")
    report_parser.add_argument(
        "report_file",
        help="Path to mission report JSON",
    )

    types_parser = subparsers.add_parser("types", help="List available mission types")
    types_parser.add_argument(
        "--category",
        help="Filter by category (maintenance, security, performance, documentation, release, testing)",
    )
    types_parser.add_argument(
        "--json",
        action="store_true",
        dest="json",
        help="Output as JSON",
    )

    type_show_parser = subparsers.add_parser("type-show", help="Show details of a mission type")
    type_show_parser.add_argument(
        "type_name",
        help="Mission type name",
    )

    constraints_parser = subparsers.add_parser("constraints", help="Validate mission constraints")
    constraints_parser.add_argument(
        "mission_file",
        help="Path to mission JSON file",
    )
    constraints_parser.add_argument(
        "--repository",
        help="Repository path for constraint validation",
    )
    constraints_parser.add_argument(
        "--cwd",
        help="Working directory for constraint validation",
    )
    constraints_parser.add_argument(
        "--json",
        action="store_true",
        dest="json",
        help="Output as JSON",
    )

    # Lifecycle subcommands
    status_parser = subparsers.add_parser("status", help="Show current mission lifecycle state")
    status_parser.add_argument(
        "--runtime-root",
        default=str(Path.home() / ".hermes" / "runtime"),
        help="Runtime root directory (default: ~/.hermes/runtime)",
    )

    pause_parser = subparsers.add_parser("pause", help="Write a pause command for the active mission")
    pause_parser.add_argument(
        "--runtime-root",
        default=str(Path.home() / ".hermes" / "runtime"),
        help="Runtime root directory (default: ~/.hermes/runtime)",
    )
    pause_parser.add_argument("--reason", help="Reason for pausing")

    resume_parser = subparsers.add_parser("resume", help="Write a resume command for the active mission")
    resume_parser.add_argument(
        "--runtime-root",
        default=str(Path.home() / ".hermes" / "runtime"),
        help="Runtime root directory (default: ~/.hermes/runtime)",
    )

    cancel_parser = subparsers.add_parser("cancel", help="Write a cancel command for the active mission")
    cancel_parser.add_argument(
        "--runtime-root",
        default=str(Path.home() / ".hermes" / "runtime"),
        help="Runtime root directory (default: ~/.hermes/runtime)",
    )
    cancel_parser.add_argument("--reason", help="Reason for cancelling")

    abort_parser = subparsers.add_parser("abort", help="Write an abort command for the active mission")
    abort_parser.add_argument(
        "--runtime-root",
        default=str(Path.home() / ".hermes" / "runtime"),
        help="Runtime root directory (default: ~/.hermes/runtime)",
    )
    abort_parser.add_argument("--reason", help="Reason for aborting")

    # Report generation subcommand
    gen_report_parser = subparsers.add_parser(
        "generate-report",
        help="Generate comprehensive mission report (JSON + Markdown)",
    )
    gen_report_parser.add_argument(
        "mission_id",
        help="Mission ID to generate report for",
    )
    gen_report_parser.add_argument(
        "--runtime-root",
        default=str(Path.home() / ".hermes" / "runtime"),
        help="Runtime root directory (default: ~/.hermes/runtime)",
    )
    gen_report_parser.add_argument(
        "--repository",
        help="Repository path for git revision detection",
    )

    args = parser.parse_args()

    handlers = {
        "run": cmd_run,
        "report": cmd_report,
        "types": cmd_types,
        "type-show": cmd_type_show,
        "constraints": cmd_constraints,
        "status": cmd_status,
        "pause": cmd_pause,
        "resume": cmd_resume,
        "cancel": cmd_cancel,
        "abort": cmd_abort,
        "generate-report": cmd_generate_report,
    }

    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
