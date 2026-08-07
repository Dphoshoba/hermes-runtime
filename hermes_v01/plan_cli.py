"""hermes-plan CLI — validate, build, show, and enqueue mission plans."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .mission import (
    MissionPlanner,
    enqueue_plan,
    load_mission,
    load_plan,
    save_plan,
)


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate a mission definition file."""
    mission_path = Path(args.mission_file).expanduser().resolve()
    try:
        mission = load_mission(mission_path)
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}, indent=2), file=sys.stderr)
        return 1

    planner = MissionPlanner()
    errors, warnings = planner.validate(mission)
    valid = len(errors) == 0
    result = {
        "valid": valid,
        "mission_id": mission.mission_id,
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if valid else 1


def cmd_build(args: argparse.Namespace) -> int:
    """Build a plan artifact from a mission definition."""
    mission_path = Path(args.mission_file).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve() if args.output else None

    try:
        mission = load_mission(mission_path)
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    planner = MissionPlanner()
    plan = planner.build(mission)

    if output_path is not None:
        save_plan(plan, output_path)
        print(json.dumps({"plan_file": str(output_path), "valid": plan.valid}, indent=2))
    else:
        print(json.dumps(plan.as_dict(), indent=2, sort_keys=True))

    return 0 if plan.valid else 1


def cmd_show(args: argparse.Namespace) -> int:
    """Show a plan artifact."""
    plan_path = Path(args.plan_file).expanduser().resolve()
    try:
        plan = load_plan(plan_path)
    except (json.JSONDecodeError, KeyError, ValueError, FileNotFoundError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    print(json.dumps(plan.as_dict(), indent=2, sort_keys=True))
    return 0


def cmd_enqueue(args: argparse.Namespace) -> int:
    """Enqueue a validated plan into the work queue."""
    plan_path = Path(args.plan_file).expanduser().resolve()
    queue_path = Path(args.queue_file).expanduser().resolve()

    try:
        plan = load_plan(plan_path)
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    try:
        enqueued = enqueue_plan(plan, queue_path)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    print(json.dumps({"enqueued": enqueued, "count": len(enqueued)}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Hermes Mission Planner — validate, build, show, and enqueue plans"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate a mission definition")
    validate_parser.add_argument("mission_file", help="Path to mission JSON file")

    build_parser = subparsers.add_parser("build", help="Build a plan from a mission")
    build_parser.add_argument("mission_file", help="Path to mission JSON file")
    build_parser.add_argument("-o", "--output", help="Output plan file path")

    show_parser = subparsers.add_parser("show", help="Show a plan artifact")
    show_parser.add_argument("plan_file", help="Path to plan JSON file")

    enqueue_parser = subparsers.add_parser("enqueue", help="Enqueue a plan into the work queue")
    enqueue_parser.add_argument("plan_file", help="Path to plan JSON file")
    enqueue_parser.add_argument("--queue-file", required=True, help="Path to work queue state file")

    args = parser.parse_args()

    handlers = {
        "validate": cmd_validate,
        "build": cmd_build,
        "show": cmd_show,
        "enqueue": cmd_enqueue,
    }

    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
