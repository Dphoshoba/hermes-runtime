"""EVOSIA Human Review CLI — retained for backward compatibility.

This module is preserved as part of the EVOSIA migration.
The CLI command remains `hermes-human-review` for now.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger("evosia.human_review")

_REVIEWERS_DB = Path.home() / ".evosia" / "reviewers.json"


def _ensure_reviewers_db() -> dict:
    """Load or create the reviewers database."""
    if not _REVIEWERS_DB.exists():
        _REVIEWERS_DB.parent.mkdir(parents=True, exist_ok=True)
        _REVIEWERS_DB.write_text("[]")
    import json
    return json.loads(_REVIEWERS_DB.read_text())


def _get_db():
    import os
    os.environ.setdefault("EVOSIA_DATABASE_URL", "sqlite:///./evosia_enterprise.db")
    os.environ.setdefault("EVOSIA_DATABASE_URL", "sqlite:///./hermes_enterprise.db")
    from enterprise.database import SessionLocal
    return SessionLocal()


def _load_config() -> dict:
    """Load review configuration from environment or defaults."""
    config = {
        "reviewer_email": os.environ.get("EVOSIA_REVIEWER_EMAIL", ""),
        "reviewer_name": os.environ.get("EVOSIA_REVIEWER_NAME", ""),
        "batch_size": int(os.environ.get("EVOSIA_BATCH_SIZE", "10")),
        "dry_run": os.environ.get("EVOSIA_DRY_RUN", "0") == "1",
    }
    return config


def add_reviewer(email: str, name: str, expertise: str = ""):
    """Register a human reviewer for mission adjudication."""
    db = _ensure_reviewers_db()
    existing = [r for r in db if r["email"] == email]
    if existing:
        existing[0]["name"] = name
        existing[0]["expertise"] = expertise
    else:
        db.append({"email": email, "name": name, "expertise": expertise, "added": "now"})
    _REVIEWERS_DB.write_text(str(db))
    log.info(f"Reviewer registered: {email} ({name})")


def list_reviewers():
    """List all registered human reviewers."""
    db = _ensure_reviewers_db()
    if not db:
        print("No reviewers registered.")
        return
    for r in db:
        print(f"  {r['email']} — {r['name']} ({r.get('expertise', 'general')})")


def approve_mission(mission_id: str, reviewer_email: str, decision: str):
    """Record a human adjudication on a mission.

    decision must be one of: APPROVE, REJECT, REQUEST_INFO
    """
    from enterprise.database import get_engine
    from enterprise.models import Mission, MissionAdjudication
    from sqlalchemy.orm import Session

    eng = get_engine(os.environ.get("EVOSIA_DATABASE_URL") or os.environ.get("EVOSIA_DATABASE_URL"))
    with Session(eng) as session:
        mission = session.get(Mission, mission_id)
        if not mission:
            print(f"Mission {mission_id} not found.")
            return

        adjudication = MissionAdjudication(
            mission_id=mission_id,
            reviewer_email=reviewer_email,
            decision=decision,
            notes="",
            created_at=__import__('datetime').datetime.now(),
        )
        session.add(adjudication)
        session.commit()
        print(f"Adjudication recorded: {mission_id} → {decision} by {reviewer_email}")


def review_next_batch():
    """Review the next batch of awaiting-mission items."""
    config = _load_config()
    if config["dry_run"]:
        print("[DRY RUN] Would review next batch of missions.")
        return

    from enterprise.database import get_engine
    from enterprise.models import Mission, MissionAdjudication
    from sqlalchemy.orm import Session

    eng = get_engine(os.environ.get("EVOSIA_DATABASE_URL") or os.environ.get("EVOSIA_DATABASE_URL"))
    with Session(eng) as session:
        pending = (
            session.query(Mission)
            .filter(Mission.status == "AWAITING_REVIEW")
            .order_by(Mission.created_at)
            .limit(config["batch_size"])
            .all()
        )
        if not pending:
            print("No missions awaiting review.")
            return

        for m in pending:
            print(f"\nMission: {m.title}")
            print(f"  ID: {m.mission_id}")
            print(f"  Type: {m.mission_type}")
            print(f"  Priority: {m.priority}")
            print(f"  Status: {m.status}")
            print()

        print(f"{len(pending)} mission(s) ready for review.")


def main():
    parser = argparse.ArgumentParser(
        description="EVOSIA Human Review CLI — manage reviewer registry and mission adjudications"
    )
    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser("add-reviewer", help="Register a human reviewer")
    p_add.add_argument("email", help="Reviewer email address")
    p_add.add_argument("name", help="Reviewer display name")
    p_add.add_argument("--expertise", default="", help="Area of expertise")

    p_list = sub.add_parser("list-reviewers", help="List all registered reviewers")

    p_approve = sub.add_parser("approve-mission", help="Adjudicate a mission")
    p_approve.add_argument("mission_id", help="Mission ID to adjudicate")
    p_approve.add_argument("reviewer_email", help="Reviewer email")
    p_approve.add_argument("decision", choices=["APPROVE", "REJECT", "REQUEST_INFO"], help="Adjudication decision")

    p_batch = sub.add_parser("review-next-batch", help="Review next batch of missions")

    args = parser.parse_args()

    if args.command == "add-reviewer":
        add_reviewer(args.email, args.name, args.expertise)
    elif args.command == "list-reviewers":
        list_reviewers()
    elif args.command == "approve-mission":
        approve_mission(args.mission_id, args.reviewer_email, args.decision)
    elif args.command == "review-next-batch":
        review_next_batch()
    else:
        parser.print_help()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
