"""Engineering Journal CLI — hermes-journal.

Append-only observability for the EVOSIA pipeline.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .journal_models import JournalEvent, EVENT_TYPES, STAGE_CATEGORIES
from .journal_store import JournalStore
from .journal_emitter import JournalEmitter
from .journal_summary import generate_overnight_summary


def _resolve_journal_dir(repo: str | Path) -> Path:
    return Path(repo).expanduser().resolve() / "engineering-journal"


def _open_store(journal_dir: Path, *, readonly: bool = True) -> JournalStore:
    journal_dir.mkdir(parents=True, exist_ok=True)
    store = JournalStore(journal_dir)
    store.open()
    return store


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_record(args: argparse.Namespace) -> int:
    """Record a single event from stdin or --payload."""
    journal_dir = _resolve_journal_dir(args.repo)
    store = _open_store(journal_dir, readonly=False)

    try:
        if args.payload:
            payload = json.loads(args.payload)
        else:
            payload = json.loads(sys.stdin.read())

        emitter = JournalEmitter(store, actor=args.actor or "cli")
        event = emitter._emit(
            args.event_type,
            payload,
            repository=args.repository,
        )
        print(json.dumps(event.as_dict(), indent=2, sort_keys=True))
        return 0
    finally:
        store.close()


def cmd_list(args: argparse.Namespace) -> int:
    """List events with optional filters."""
    journal_dir = _resolve_journal_dir(args.repo)
    store = _open_store(journal_dir)

    try:
        events = store.list_events(
            event_type=args.type,
            stage=args.stage,
            repository=args.repository,
            actor=args.actor,
            after=args.after,
            before=args.before,
            limit=args.limit,
        )
        if args.json:
            print(json.dumps(
                [e.as_dict() for e in events],
                indent=2, sort_keys=True,
            ))
        else:
            for e in events:
                repo_str = f"  [{e.repository}]" if e.repository else ""
                print(f"{e.timestamp}  {e.event_type:<35s}{repo_str}")
        return 0
    finally:
        store.close()


def cmd_show(args: argparse.Namespace) -> int:
    """Show a single event by ID."""
    journal_dir = _resolve_journal_dir(args.repo)
    store = _open_store(journal_dir)

    try:
        event = store.get_event(args.event_id)
        if event is None:
            print(f"Event not found: {args.event_id}", file=sys.stderr)
            return 1
        print(json.dumps(event.as_dict(), indent=2, sort_keys=True))
        return 0
    finally:
        store.close()


def cmd_summary(args: argparse.Namespace) -> int:
    """Generate an overnight summary."""
    journal_dir = _resolve_journal_dir(args.repo)
    store = _open_store(journal_dir)

    try:
        summary = generate_overnight_summary(
            store,
            after=args.after,
            before=args.before,
        )
        if args.json:
            print(json.dumps(summary.as_dict(), indent=2, sort_keys=True))
        else:
            print(summary.render_markdown())
        return 0
    finally:
        store.close()


def cmd_integrity(args: argparse.Namespace) -> int:
    """Verify journal integrity."""
    journal_dir = _resolve_journal_dir(args.repo)
    store = _open_store(journal_dir)

    try:
        errors = store.verify_integrity()
        count = store.count_events()
        if args.json:
            print(json.dumps({
                "event_count": count,
                "errors": errors,
                "valid": len(errors) == 0,
            }, indent=2, sort_keys=True))
        else:
            print(f"Events: {count}")
            if errors:
                print(f"Integrity errors: {len(errors)}")
                for err in errors:
                    print(f"  - {err}")
            else:
                print("Integrity: OK")
        return 0 if not errors else 1
    finally:
        store.close()


def cmd_types(args: argparse.Namespace) -> int:
    """List known event types."""
    if args.json:
        types_info = {}
        for et in EVENT_TYPES:
            types_info[et] = {
                "event_type": et,
                "stage": STAGE_CATEGORIES.get(et, "unknown"),
            }
        print(json.dumps(types_info, indent=2, sort_keys=True))
    else:
        for et in EVENT_TYPES:
            stage = STAGE_CATEGORIES.get(et, "unknown")
            print(f"  {et:<40s}  stage: {stage}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Export all events as JSONL."""
    journal_dir = _resolve_journal_dir(args.repo)
    store = _open_store(journal_dir)

    try:
        for event in store.events_iterator():
            line = json.dumps(event.as_dict(), sort_keys=True, ensure_ascii=False)
            print(line)
        return 0
    finally:
        store.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EVOSIA Engineering Journal — append-only pipeline observability"
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="Repository root (default: current directory)",
    )
    sub = parser.add_subparsers(dest="command")

    # record
    rec = sub.add_parser("record", help="Record an event")
    rec.add_argument("event_type", choices=EVENT_TYPES)
    rec.add_argument("--payload", default=None, help="JSON payload string")
    rec.add_argument("--repository", default=None, help="Repository identifier")
    rec.add_argument("--actor", default=None, help="Actor identity")

    # list
    lst = sub.add_parser("list", help="List events")
    lst.add_argument("--type", dest="type", default=None, help="Filter by event type")
    lst.add_argument("--stage", default=None, help="Filter by stage")
    lst.add_argument("--repository", default=None, help="Filter by repository")
    lst.add_argument("--actor", default=None, help="Filter by actor")
    lst.add_argument("--after", default=None, help="Events after timestamp")
    lst.add_argument("--before", default=None, help="Events before timestamp")
    lst.add_argument("--limit", type=int, default=None, help="Max events to return")
    lst.add_argument("--json", action="store_true", help="JSON output")

    # show
    show = sub.add_parser("show", help="Show a single event")
    show.add_argument("event_id")

    # summary
    sm = sub.add_parser("summary", help="Generate overnight summary")
    sm.add_argument("--after", default=None, help="Period start (ISO 8601)")
    sm.add_argument("--before", default=None, help="Period end (ISO 8601)")
    sm.add_argument("--json", action="store_true", help="JSON output")

    # integrity
    integ = sub.add_parser("integrity", help="Verify journal integrity")
    integ.add_argument("--json", action="store_true", help="JSON output")

    # types
    types_cmd = sub.add_parser("types", help="List known event types")
    types_cmd.add_argument("--json", action="store_true", help="JSON output")

    # export
    sub.add_parser("export", help="Export all events as JSONL")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    handlers = {
        "record": cmd_record,
        "list": cmd_list,
        "show": cmd_show,
        "summary": cmd_summary,
        "integrity": cmd_integrity,
        "types": cmd_types,
        "export": cmd_export,
    }

    try:
        return handlers[args.command](args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
